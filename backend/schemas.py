from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4_000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=12)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("The question cannot be empty.")
        return value


class Source(BaseModel):
    citation: int
    chunk_id: int
    title: str
    source: str
    url: str | None = None
    excerpt: str
    retrieval_score: float
    rerank_score: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    model: str
    retrieved_count: int
    reranked: bool


class HealthResponse(BaseModel):
    status: Literal["ready", "degraded"]
    rag_ready: bool
    gemini_ready: bool
    reranker_ready: bool
    detail: str | None = None
