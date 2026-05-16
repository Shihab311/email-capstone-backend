"""LLM-based chunk reranking via Gemini.

Adapted from AI-Backend-Extended/rag/chunk_rerank.py.
"""

from __future__ import annotations

import json
import re
import sys
import time
from typing import Any, Dict, List, Optional

from .indexing import Candidate
from .config import settings

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]


def _format_chunk_for_prompt(candidate_id: int, c: Candidate) -> str:
    meta = c.meta or {}
    subj = meta.get("subject") or "(no subject)"
    sender = meta.get("sender") or "(unknown)"
    date = meta.get("date") or "(no date)"
    preview = meta.get("chunk_preview") or c.chunk_preview or ""
    fa = "" if c.faiss_score is None else f"{c.faiss_score:.4f}"
    bm = "" if c.bm25_score is None else f"{c.bm25_score:.4f}"
    return (
        f"[CANDIDATE {candidate_id}]\n"
        f"File: {c.key.filename}\n"
        f"Chunk: {c.key.chunk_id}\n"
        f"Subject: {subj}\n"
        f"From: {sender}\n"
        f"Date: {date}\n"
        f"FAISS Score: {fa}\n"
        f"BM25 Score: {bm}\n"
        f"Preview: {preview}\n"
    )


def build_chunk_rerank_prompt(query: str, candidates: List[Candidate]) -> str:
    blocks = "\n\n".join(
        _format_chunk_for_prompt(i + 1, c) for i, c in enumerate(candidates)
    )
    return f"""You are an email search assistant.

A hybrid retrieval system retrieved the candidate email chunks below.
Rerank them by true relevance to the USER QUERY.

Return a JSON array sorted by relevance_score descending. Each element must have:
  - "candidate_id": integer (the [CANDIDATE N] number)
  - "relevance_score": float between 0.0 and 1.0
  - "reason": one sentence

Include ALL candidates, even if score is 0. Respond with ONLY the JSON array.

USER QUERY:
{query}

CANDIDATES:
{blocks}
"""


def llm_rerank_chunks(
    query: str,
    candidates: List[Candidate],
    *,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    max_retries: int = 2,
) -> List[Dict[str, Any]]:
    """Use Gemini to rerank candidates by relevance."""
    if genai is None:
        raise ImportError(
            "google-genai not installed. Run: pip install google-genai"
        )

    api_key = api_key or settings.google_api_key
    model_name = model_name or settings.gemini_model
    client = genai.Client(api_key=api_key)
    prompt = build_chunk_rerank_prompt(query, candidates)

    def fallback(reason: str) -> List[Dict[str, Any]]:
        return [
            {"candidate_id": i + 1, "relevance_score": 0.0, "reason": reason}
            for i in range(len(candidates))
        ]

    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            raw = (response.text or "").strip()
            if not raw:
                return fallback("(empty LLM response)")

            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            ranked = json.loads(raw)
            if not isinstance(ranked, list):
                return fallback("(unexpected LLM format)")

            valid_ids = set(range(1, len(candidates) + 1))
            out: List[Dict[str, Any]] = []
            for entry in ranked:
                if not isinstance(entry, dict):
                    continue
                cid = entry.get("candidate_id")
                if cid not in valid_ids:
                    continue
                out.append(
                    {
                        "candidate_id": int(cid),
                        "relevance_score": float(
                            entry.get("relevance_score", 0.0)
                        ),
                        "reason": str(entry.get("reason", "")),
                    }
                )
            if not out:
                return fallback("(no valid rerank entries)")
            out.sort(key=lambda r: r["relevance_score"], reverse=True)
            return out
        except Exception as e:
            last_err = e
            msg = str(e)
            retriable = any(
                s in msg
                for s in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE")
            )
            if not retriable or attempt >= max_retries:
                print(
                    f"Warning: rerank failed: {type(e).__name__}: {e}",
                    file=sys.stderr,
                )
                return fallback(f"({type(e).__name__}: rerank unavailable)")
            time.sleep(2.0 + attempt * 2.0)

    print(f"Warning: rerank failed: {last_err}", file=sys.stderr)
    return fallback("(rerank failed)")
