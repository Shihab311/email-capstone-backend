"""RAG v2 Engine — the main orchestrator.

Holds loaded indexes in memory and provides query methods.
Adapted from AI-Backend-Extended/rag/rag_v2.py.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chunking import normalize_subject
from .config import settings
from .embeddings import build_query_embedding
from .indexing import (
    Candidate,
    ChunkKey,
    ensure_bm25_index,
    load_faiss_index,
)
from .reranker import llm_rerank_chunks
from .retrieval import (
    bm25_retrieve_chunks,
    faiss_retrieve_chunks,
    merge_hybrid_candidates,
)

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _parse_email_date(d: str) -> Optional[date]:
    if not d:
        return None
    try:
        return parsedate_to_datetime(d).date()
    except Exception:
        return None


def _parse_ymd(d: str) -> Optional[date]:
    if not d:
        return None
    try:
        y, m, dd = d.strip().split("-", 2)
        return date(int(y), int(m), int(dd))
    except Exception:
        return None


def apply_filters(
    cands: List[Candidate],
    *,
    from_contains: Optional[str] = None,
    to_contains: Optional[str] = None,
    subject_contains: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Candidate]:
    """Filter candidates by metadata."""
    out: List[Candidate] = []
    from_q = (from_contains or "").strip().lower()
    to_q = (to_contains or "").strip().lower()
    subj_q = (subject_contains or "").strip().lower()
    d_from = _parse_ymd(date_from or "")
    d_to = _parse_ymd(date_to or "")

    for c in cands:
        meta = c.meta or {}
        sender = str(meta.get("sender") or "").lower()
        receiver = str(meta.get("receiver") or "").lower()
        subject = str(meta.get("subject") or "").lower()
        d = _parse_email_date(str(meta.get("date") or ""))
        if from_q and from_q not in sender:
            continue
        if to_q and to_q not in receiver:
            continue
        if subj_q and subj_q not in subject:
            continue
        if d_from and (d is None or d < d_from):
            continue
        if d_to and (d is None or d > d_to):
            continue
        out.append(c)
    return out


def expand_thread_candidates(
    selected: List[Candidate],
    all_chunks: List[Dict[str, Any]],
    *,
    max_extra: int = 10,
) -> List[Candidate]:
    """Pull in sibling chunks from the same email thread."""
    if max_extra <= 0:
        return selected

    thread_keys = set()
    for c in selected:
        tk = (c.meta or {}).get("thread_key") or normalize_subject(
            (c.meta or {}).get("subject") or ""
        )
        if tk:
            thread_keys.add(tk)

    if not thread_keys:
        return selected

    existing = {(c.key.filename, c.key.chunk_id) for c in selected}
    added: List[Candidate] = []
    for r in all_chunks:
        if len(added) >= max_extra:
            break
        tk = r.get("thread_key") or normalize_subject(r.get("subject") or "")
        if tk not in thread_keys:
            continue
        fn = r.get("filename")
        cid = r.get("chunk_id")
        if not isinstance(fn, str) or not isinstance(cid, int):
            continue
        if (fn, cid) in existing:
            continue
        added.append(
            Candidate(
                key=ChunkKey(filename=fn, chunk_id=cid),
                chunk_preview=str(r.get("chunk_preview") or ""),
                meta=r,
            )
        )
        existing.add((fn, cid))

    return selected + added


def build_context(
    chunks: List[Candidate], *, max_chars_per_chunk: int = 900
) -> str:
    """Format chunks into a text context block for the LLM."""
    blocks: List[str] = []
    for i, c in enumerate(chunks, start=1):
        meta = c.meta or {}
        text = str(meta.get("chunk_text") or "")
        if len(text) > max_chars_per_chunk:
            text = text[:max_chars_per_chunk].rstrip() + "... [truncated]"
        subj = meta.get("subject") or "(no subject)"
        sender = meta.get("sender") or "(unknown)"
        d = meta.get("date") or "(no date)"
        blocks.append(
            f"[CHUNK {i}]\n"
            f"File: {meta.get('filename', '')}\n"
            f"Chunk: {meta.get('chunk_id', '')}\n"
            f"Subject: {subj}\n"
            f"From: {sender}\n"
            f"Date: {d}\n"
            f"FAISS Score: {'' if c.faiss_score is None else f'{c.faiss_score:.4f}'}\n"
            f"BM25 Score: {'' if c.bm25_score is None else f'{c.bm25_score:.4f}'}\n"
            f"Text:\n{text}"
        )
    return "\n\n".join(blocks)


def build_prompt(query: str, context: str) -> str:
    return f"""You are an email assistant. Answer the USER QUESTION using ONLY the CHUNK CONTEXT below.

Output format:
1) Evidence (bullets). Each bullet MUST end with one or more citations like [CHUNK 1].
2) Answer (short paragraph). Every paragraph MUST include at least one citation like [CHUNK 2].

Rules:
- Use ONLY the context. No outside knowledge.
- If the context does not contain enough info, say: "The retrieved chunks do not contain enough information to answer this question." and cite the most relevant chunks.
- Do not invent names/dates/numbers.

CHUNK CONTEXT:
{context}

USER QUESTION:
{query}
"""


def generate_answer(
    prompt: str,
    *,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    max_retries: int = 3,
) -> str:
    """Generate a grounded answer using Gemini."""
    if genai is None:
        raise ImportError(
            "google-genai not installed. Run: pip install google-genai"
        )

    api_key = api_key or settings.google_api_key
    model_name = model_name or settings.gemini_model
    client = genai.Client(api_key=api_key)

    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(temperature=0.2),
            )
            return (resp.text or "").strip()
        except Exception as e:
            last_err = e
            msg = str(e)
            retriable = any(
                s in msg
                for s in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")
            )
            if not retriable or attempt >= max_retries:
                raise
            time.sleep(2.0 + attempt * 2.0)
    raise last_err  # pragma: no cover


# ---------------------------------------------------------------------------
# RAG Engine
# ---------------------------------------------------------------------------


class RAGEngine:
    """Holds loaded indexes in memory and orchestrates RAG queries."""

    def __init__(self):
        self.chunk_records: List[Dict[str, Any]] = []
        self.faiss_index: Optional[Any] = None
        self.bm25_index: Optional[Any] = None
        self.bm25_keys: List[ChunkKey] = []
        self._ready = False

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "ready": self._ready,
            "chunk_count": len(self.chunk_records),
            "faiss_vectors": (
                int(self.faiss_index.ntotal) if self.faiss_index else 0
            ),
            "bm25_documents": len(self.bm25_keys),
        }

    def load(self) -> bool:
        """Try to load existing indexes from disk into memory."""
        chunks_path = settings.processed_chunks_path
        if not chunks_path.exists():
            logger.warning("No processed_chunks.json found at %s", chunks_path)
            self._ready = False
            return False

        with open(chunks_path, encoding="utf-8") as f:
            self.chunk_records = json.load(f)

        if not self.chunk_records:
            logger.warning("processed_chunks.json is empty")
            self._ready = False
            return False

        # FAISS
        try:
            self.faiss_index = load_faiss_index()
            logger.info("FAISS index loaded: %d vectors", self.faiss_index.ntotal)
        except FileNotFoundError:
            logger.warning("FAISS index not found")
            self._ready = False
            return False

        # BM25
        try:
            self.bm25_index, self.bm25_keys = ensure_bm25_index(
                self.chunk_records
            )
            logger.info("BM25 index ready: %d documents", len(self.bm25_keys))
        except Exception as e:
            logger.warning("BM25 index failed: %s", e)
            self._ready = False
            return False

        self._ready = True
        return True

    def reload(self) -> bool:
        """Force reload all indexes from disk."""
        return self.load()

    def query(
        self,
        query_text: str,
        *,
        # Retrieval params
        faiss_top_n: int = 50,
        bm25_top_n: int = 50,
        merge_top: int = 80,
        final_k: int = 10,
        # Filters
        from_contains: Optional[str] = None,
        to_contains: Optional[str] = None,
        subject_contains: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        # Options
        use_rerank: bool = False,
        expand_thread: bool = False,
        max_thread_extra: int = 10,
        generate: bool = True,
        api_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the full RAG v2 pipeline and return answer + sources."""
        if not self._ready:
            raise RuntimeError("RAG engine is not ready. Run /ingest first.")

        api_key = api_key or settings.google_api_key
        metric = settings.index_metric

        # 1. Build query embedding
        qvec, _info = build_query_embedding(
            query_text, api_key=api_key, metric=metric
        )

        # 2. Hybrid retrieve
        faiss_hits = faiss_retrieve_chunks(
            qvec, index=self.faiss_index, top_n=faiss_top_n
        )
        bm25_hits = bm25_retrieve_chunks(
            query_text, self.bm25_index, self.bm25_keys, top_n=bm25_top_n
        )
        merged = merge_hybrid_candidates(
            chunk_records=self.chunk_records,
            faiss_hits=faiss_hits,
            bm25_hits=bm25_hits,
            bm25_keys=self.bm25_keys,
        )

        # 3. Apply filters
        merged = apply_filters(
            merged,
            from_contains=from_contains,
            to_contains=to_contains,
            subject_contains=subject_contains,
            date_from=date_from,
            date_to=date_to,
        )
        merged = merged[:merge_top]

        if not merged:
            return {
                "answer": "No matching email chunks found for your query.",
                "sources": [],
                "query": query_text,
                "model_used": settings.gemini_model,
            }

        # 4. Optional rerank
        if use_rerank:
            ranked = llm_rerank_chunks(query_text, merged, api_key=api_key)
            id_to_candidate = {i + 1: c for i, c in enumerate(merged)}
            ordered = [
                id_to_candidate[r["candidate_id"]]
                for r in ranked
                if r.get("candidate_id") in id_to_candidate
            ]
            selected = ordered[:final_k]
        else:
            selected = merged[:final_k]

        # 5. Expand thread
        if expand_thread:
            selected = expand_thread_candidates(
                selected, self.chunk_records, max_extra=max_thread_extra
            )

        # 6. Build sources
        sources = []
        for i, c in enumerate(selected, start=1):
            meta = c.meta or {}
            sources.append(
                {
                    "chunk_index": i,
                    "filename": meta.get("filename", ""),
                    "chunk_id": meta.get("chunk_id", ""),
                    "subject": meta.get("subject", "(no subject)"),
                    "sender": meta.get("sender", ""),
                    "receiver": meta.get("receiver", ""),
                    "date": meta.get("date", ""),
                    "faiss_score": c.faiss_score,
                    "bm25_score": c.bm25_score,
                    "preview": meta.get("chunk_preview", ""),
                }
            )

        if not generate:
            return {
                "answer": None,
                "sources": sources,
                "query": query_text,
                "model_used": None,
            }

        # 7. Generate answer
        context = build_context(selected)
        prompt = build_prompt(query_text, context)
        answer = generate_answer(prompt, api_key=api_key)

        return {
            "answer": answer,
            "sources": sources,
            "query": query_text,
            "model_used": settings.gemini_model,
        }
