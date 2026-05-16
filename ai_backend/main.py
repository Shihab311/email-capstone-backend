"""AI Backend — FastAPI application.

Endpoints:
  GET  /                  Health check
  GET  /status            Index readiness status
  POST /ingest            Ingest emails from DB → embed → build indexes
  POST /search            RAG v2 search (answer + sources)
  POST /search/retrieve   Retrieve chunks only (no answer generation)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import load_env, settings
from .db_ingest import (
    build_all_indexes,
    fetch_emails_from_db,
    process_and_embed_chunks,
    process_and_embed_emails,
)
from .rag_engine import RAGEngine
from .schemas import (
    HealthResponse,
    IndexStatus,
    IngestRequest,
    IngestResponse,
    SearchRequest,
    SearchResponse,
    SourceChunk,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ai_backend")

# ---------------------------------------------------------------------------
# Global RAG engine (lives for the lifetime of the process)
# ---------------------------------------------------------------------------
rag = RAGEngine()

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    load_env()
    logger.info("AI Backend starting up...")

    # Try to load existing indexes
    if rag.load():
        logger.info("RAG engine loaded successfully: %s", rag.status)
    else:
        logger.warning(
            "RAG engine not ready — run POST /ingest to build indexes."
        )

    yield  # app runs here

    logger.info("AI Backend shutting down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Email AI Backend",
    description="FastAPI service for email RAG search using FAISS + BM25 + Gemini.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        service="email-ai-backend",
        ai_ready=rag.is_ready,
    )


@app.get("/status", response_model=IndexStatus)
def get_status():
    """Return current index readiness status."""
    s = rag.status
    return IndexStatus(
        ready=s["ready"],
        chunk_count=s["chunk_count"],
        faiss_vectors=s["faiss_vectors"],
        bm25_documents=s["bm25_documents"],
        database_path=str(settings.database_path),
        vector_store_dir=str(settings.vector_store_dir),
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest_emails(req: IngestRequest = IngestRequest()):
    """Read emails from the database, embed, chunk, and build indexes.

    This can take a while depending on how many emails need embedding.
    """
    try:
        # 1. Count emails in DB
        db_records = fetch_emails_from_db()
        emails_in_db = len(db_records)
        logger.info("Found %d email(s) in database", emails_in_db)

        # 2. Embed emails
        email_records = process_and_embed_emails(
            max_new=req.max_new_emails,
        )
        emails_embedded = len(email_records)

        # 3. Chunk and embed
        chunk_records = process_and_embed_chunks(
            email_records,
            max_new=req.max_new_chunks,
        )
        chunks_created = len(chunk_records)

        # 4. Build indexes
        idx_info = build_all_indexes(chunk_records)

        # 5. Reload RAG engine
        rag.reload()

        return IngestResponse(
            status="ok",
            emails_in_db=emails_in_db,
            emails_embedded=emails_embedded,
            chunks_created=chunks_created,
            faiss_vectors=idx_info["faiss_vectors"],
            bm25_documents=idx_info["bm25_documents"],
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Ingest failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse)
def search_emails(req: SearchRequest):
    """RAG v2 search: hybrid retrieve → optional rerank → generate answer."""
    if not rag.is_ready:
        raise HTTPException(
            status_code=503,
            detail="AI engine not ready. Run POST /ingest first.",
        )

    try:
        result = rag.query(
            req.query,
            final_k=req.top_k,
            from_contains=req.from_contains,
            to_contains=req.to_contains,
            subject_contains=req.subject_contains,
            date_from=req.date_from,
            date_to=req.date_to,
            use_rerank=req.use_rerank,
            expand_thread=req.expand_thread,
            generate=True,
        )
        return SearchResponse(
            answer=result["answer"],
            sources=[SourceChunk(**s) for s in result["sources"]],
            query=result["query"],
            model_used=result["model_used"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search/retrieve", response_model=SearchResponse)
def retrieve_only(req: SearchRequest):
    """Retrieve matching chunks without generating an answer."""
    if not rag.is_ready:
        raise HTTPException(
            status_code=503,
            detail="AI engine not ready. Run POST /ingest first.",
        )

    try:
        result = rag.query(
            req.query,
            final_k=req.top_k,
            from_contains=req.from_contains,
            to_contains=req.to_contains,
            subject_contains=req.subject_contains,
            date_from=req.date_from,
            date_to=req.date_to,
            use_rerank=req.use_rerank,
            expand_thread=req.expand_thread,
            generate=False,
        )
        return SearchResponse(
            answer=result["answer"],
            sources=[SourceChunk(**s) for s in result["sources"]],
            query=result["query"],
            model_used=result["model_used"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Retrieve failed")
        raise HTTPException(status_code=500, detail=str(e))
