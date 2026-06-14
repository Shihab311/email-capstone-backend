"""Pydantic request/response schemas for the AI backend API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    """Payload for the /search endpoint."""

    query: str = Field(..., min_length=1, description="Search query text")

    # Optional metadata filters
    from_contains: Optional[str] = Field(
        None, description="Filter: sender must contain this string"
    )
    to_contains: Optional[str] = Field(
        None, description="Filter: receiver must contain this string"
    )
    subject_contains: Optional[str] = Field(
        None, description="Filter: subject must contain this string"
    )
    date_from: Optional[str] = Field(
        None, description="Filter: earliest date (YYYY-MM-DD)"
    )
    date_to: Optional[str] = Field(
        None, description="Filter: latest date (YYYY-MM-DD)"
    )

    # Retrieval options
    top_k: int = Field(10, ge=1, le=50, description="Final number of chunks to use")
    use_rerank: bool = Field(False, description="Use LLM reranking")
    expand_thread: bool = Field(False, description="Expand to sibling thread chunks")


class IngestRequest(BaseModel):
    """Payload for the /ingest endpoint."""

    max_new_emails: Optional[int] = Field(
        None, description="Max new emails to embed (None = all)"
    )
    max_new_chunks: Optional[int] = Field(
        None, description="Max new chunks to embed (None = all)"
    )


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class SourceChunk(BaseModel):
    """A single source chunk returned with the search answer."""

    chunk_index: int
    filename: str
    chunk_id: Any
    subject: str
    sender: str
    receiver: str
    date: str
    faiss_score: Optional[float] = None
    bm25_score: Optional[float] = None
    preview: str = ""


class SearchResponse(BaseModel):
    """Response from the /search endpoint."""

    answer: Optional[str] = None
    sources: List[SourceChunk] = []
    query: str
    model_used: Optional[str] = None


class IndexStatus(BaseModel):
    """Current index readiness status."""

    ready: bool
    chunk_count: int
    faiss_vectors: int
    bm25_documents: int
    database_path: str
    vector_store_dir: str


class IngestResponse(BaseModel):
    """Response from the /ingest endpoint."""

    status: str
    emails_in_db: int
    emails_embedded: int
    chunks_created: int
    faiss_vectors: int
    bm25_documents: int


class HealthResponse(BaseModel):
    """Response from the / health check."""

    status: str
    service: str
    ai_ready: bool
