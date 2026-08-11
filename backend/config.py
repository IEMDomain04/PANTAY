from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _boolean(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _integer(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_environment: str
    gemini_api_key: str
    gemini_model: str
    rag_index_dir: Path
    embedding_device: str
    reranker_enabled: bool
    reranker_model: str
    reranker_device: str
    retrieval_candidates: int
    final_sources: int
    max_context_chars: int
    allowed_origins: tuple[str, ...]


def get_settings() -> Settings:
    backend_dir = Path(__file__).resolve().parent
    default_index = backend_dir / "data" / "ph_omnicorpus_index"
    origins = tuple(
        item.strip()
        for item in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if item.strip()
    )

    return Settings(
        app_name="Katwiran Legal RAG API",
        app_environment=os.getenv("APP_ENVIRONMENT", "development"),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        rag_index_dir=Path(os.getenv("RAG_INDEX_DIR", default_index)).expanduser().resolve(),
        embedding_device=os.getenv("EMBEDDING_DEVICE", "cpu").strip(),
        reranker_enabled=_boolean("RERANKER_ENABLED", True),
        reranker_model=os.getenv(
            "RERANKER_MODEL",
            "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        ).strip(),
        reranker_device=os.getenv("RERANKER_DEVICE", "cpu").strip(),
        retrieval_candidates=max(5, _integer("RETRIEVAL_CANDIDATES", 24)),
        final_sources=max(1, _integer("FINAL_SOURCES", 6)),
        max_context_chars=max(2_000, _integer("MAX_CONTEXT_CHARS", 18_000)),
        allowed_origins=origins,
    )
