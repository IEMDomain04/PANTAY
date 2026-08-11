from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .gemini_service import GeminiService
from .rag import RagService
from .schemas import ChatRequest, ChatResponse, HealthResponse, Source


load_dotenv()
logger = logging.getLogger("katwiran")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.rag = None
    app.state.gemini = None
    app.state.startup_errors = []

    try:
        app.state.rag = await asyncio.to_thread(RagService, settings)
    except Exception as exc:
        logger.exception("RAG initialization failed")
        app.state.startup_errors.append(f"RAG: {exc}")

    try:
        app.state.gemini = GeminiService(settings)
    except Exception as exc:
        logger.exception("Gemini initialization failed")
        app.state.startup_errors.append(f"Gemini: {exc}")

    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Citation-first Philippine legal retrieval and generation API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    rag: RagService | None = request.app.state.rag
    gemini: GeminiService | None = request.app.state.gemini
    errors: list[str] = request.app.state.startup_errors
    ready = rag is not None and gemini is not None
    return HealthResponse(
        status="ready" if ready else "degraded",
        rag_ready=rag is not None,
        gemini_ready=gemini is not None,
        reranker_ready=bool(rag and rag.reranker_ready),
        detail="; ".join(errors) or (rag.reranker_error if rag else None),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    rag: RagService | None = request.app.state.rag
    gemini: GeminiService | None = request.app.state.gemini
    if rag is None:
        raise HTTPException(status_code=503, detail="The legal knowledge base is not ready. Check RAG_INDEX_DIR and the backend logs.")
    if gemini is None:
        raise HTTPException(status_code=503, detail="Gemini is not ready. Add GEMINI_API_KEY to backend/.env and restart the API.")

    try:
        results, retrieved_count = await asyncio.to_thread(rag.retrieve, payload.message)
        if not results:
            raise HTTPException(status_code=503, detail="No matching passages could be recovered from the metadata store.")

        context, included = rag.make_context(results)
        answer = await gemini.answer(payload.message, payload.history, context)
        sources = [
            Source(
                citation=item["citation"],
                chunk_id=item["chunk_id"],
                title=item["title"],
                source=item["source"],
                url=item["url"],
                excerpt=item["text"][:320].strip() + ("…" if len(item["text"]) > 320 else ""),
                retrieval_score=round(item["retrieval_score"], 6),
                rerank_score=round(item["rerank_score"], 6) if item["rerank_score"] is not None else None,
            )
            for item in included
        ]
        return ChatResponse(
            answer=answer,
            sources=sources,
            model=settings.gemini_model,
            retrieved_count=retrieved_count,
            reranked=rag.reranker_ready,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat request failed")
        raise HTTPException(status_code=500, detail=f"The legal search failed: {exc}") from exc
