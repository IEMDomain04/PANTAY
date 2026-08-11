from __future__ import annotations

import bisect
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import faiss
import numpy as np
import pyarrow.parquet as pq
from sentence_transformers import CrossEncoder, SentenceTransformer

from .config import Settings


TITLE_KEYS = ("title", "case_title", "document_title", "name", "heading")
SOURCE_KEYS = ("source", "court", "document_type", "category", "collection", "dataset")
URL_KEYS = ("url", "source_url", "link", "uri")


def _first(metadata: dict[str, Any], keys: tuple[str, ...], fallback: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return fallback


class MetadataStore:
    """Maps the numeric FAISS result IDs back to OmniCorpus Parquet rows."""

    def __init__(self, metadata_dir: Path) -> None:
        self.paths = sorted(metadata_dir.glob("*.parquet"))
        if not self.paths:
            raise FileNotFoundError(f"No Parquet metadata shards found in {metadata_dir}")

        self.ranges: list[tuple[int, int, int]] = []
        for path_index, path in enumerate(self.paths):
            chunk_ids = pq.read_table(path, columns=["chunk_id"])["chunk_id"]
            if len(chunk_ids):
                self.ranges.append((int(chunk_ids[0].as_py()), int(chunk_ids[-1].as_py()), path_index))
        self.starts = [item[0] for item in self.ranges]

    @lru_cache(maxsize=16)
    def _read_shard(self, path_index: int) -> dict[int, dict[str, Any]]:
        rows = pq.read_table(self.paths[path_index]).to_pylist()
        return {int(row["chunk_id"]): row for row in rows}

    def get_many(self, chunk_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
        requested = {int(item) for item in chunk_ids if int(item) >= 0}
        grouped: dict[int, list[int]] = {}
        for chunk_id in requested:
            range_index = bisect.bisect_right(self.starts, chunk_id) - 1
            if range_index < 0:
                continue
            start, end, path_index = self.ranges[range_index]
            if start <= chunk_id <= end:
                grouped.setdefault(path_index, []).append(chunk_id)

        result: dict[int, dict[str, Any]] = {}
        for path_index, ids in grouped.items():
            shard = self._read_shard(path_index)
            result.update({chunk_id: shard[chunk_id] for chunk_id in ids if chunk_id in shard})
        return result


class RagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        index_dir = settings.rag_index_dir
        manifest_path = index_dir / "manifest.json"
        faiss_path = index_dir / "omnicorpus.faiss"

        if not manifest_path.exists() or not faiss_path.exists():
            raise FileNotFoundError(
                "RAG files are incomplete. Expected manifest.json, omnicorpus.faiss, "
                f"and metadata/*.parquet under {index_dir}"
            )

        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.index = faiss.read_index(str(faiss_path))
        if hasattr(self.index, "nprobe") and hasattr(self.index, "nlist"):
            self.index.nprobe = min(32, self.index.nlist)

        model_name = self.manifest.get("model", "intfloat/multilingual-e5-base")
        self.query_prefix = self.manifest.get("query_prefix", "query: ")
        self.embedder = SentenceTransformer(model_name, device=settings.embedding_device)
        self.metadata = MetadataStore(index_dir / "metadata")

        self.reranker: CrossEncoder | None = None
        self.reranker_error: str | None = None
        if settings.reranker_enabled:
            try:
                self.reranker = CrossEncoder(
                    settings.reranker_model,
                    device=settings.reranker_device,
                    max_length=512,
                )
            except Exception as exc:  # Retrieval can still work without reranking.
                self.reranker_error = str(exc)

    @property
    def reranker_ready(self) -> bool:
        return self.reranker is not None

    def retrieve(self, question: str) -> tuple[list[dict[str, Any]], int]:
        vector = self.embedder.encode(
            [self.query_prefix + question],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).astype(np.float32)

        scores, ids = self.index.search(vector, self.settings.retrieval_candidates)
        valid = [(int(chunk_id), float(score)) for chunk_id, score in zip(ids[0], scores[0]) if chunk_id >= 0]
        rows = self.metadata.get_many(chunk_id for chunk_id, _ in valid)

        candidates: list[dict[str, Any]] = []
        for chunk_id, score in valid:
            row = rows.get(chunk_id)
            if not row:
                continue
            try:
                metadata = json.loads(row.get("metadata_json") or "{}")
            except json.JSONDecodeError:
                metadata = {}

            title = _first(metadata, TITLE_KEYS, f"OmniCorpus document {row.get('doc_id', '')[:8]}")
            source = _first(metadata, SOURCE_KEYS, str(row.get("split") or "Philippine OmniCorpus"))
            url = _first(metadata, URL_KEYS, "") or None
            candidates.append({
                "chunk_id": chunk_id,
                "text": str(row.get("text", "")),
                "title": title,
                "source": source,
                "url": url,
                "retrieval_score": score,
                "rerank_score": None,
            })

        if self.reranker and candidates:
            pairs = [(question, item["text"]) for item in candidates]
            rerank_scores = self.reranker.predict(pairs, show_progress_bar=False)
            for candidate, score in zip(candidates, rerank_scores):
                candidate["rerank_score"] = float(score)
            candidates.sort(key=lambda item: item["rerank_score"], reverse=True)

        return candidates[: self.settings.final_sources], len(valid)

    def make_context(self, results: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        blocks: list[str] = []
        included: list[dict[str, Any]] = []
        characters = 0

        for citation, item in enumerate(results, start=1):
            block = (
                f"[SOURCE {citation}]\n"
                f"Title: {item['title']}\n"
                f"Origin: {item['source']}\n"
                f"URL: {item['url'] or 'Not provided'}\n"
                f"Passage:\n{item['text'].strip()}"
            )
            remaining = self.settings.max_context_chars - characters
            if remaining <= 300:
                break
            if len(block) > remaining:
                block = block[:remaining].rsplit(" ", 1)[0] + "…"
            blocks.append(block)
            included.append({**item, "citation": citation})
            characters += len(block)

        return "\n\n---\n\n".join(blocks), included
