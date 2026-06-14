"""Hybrid retrieval: FAISS + BM25 merge.

Adapted from AI-Backend-Extended/rag/hybrid_retrieval.py.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .indexing import (
    Candidate,
    ChunkKey,
    load_faiss_index,
    simple_tokenize,
)
from .config import settings


def faiss_retrieve_chunks(
    query_vector: np.ndarray,
    *,
    index: Optional[Any] = None,
    index_path: Optional[str] = None,
    top_n: int = 50,
) -> List[Tuple[int, float]]:
    """Search the FAISS chunk index and return (row_idx, score) pairs."""
    if index is None:
        index = load_faiss_index(index_path)
    k = min(int(index.ntotal), int(top_n))
    if k <= 0:
        return []
    distances, indices = index.search(query_vector, k)
    out: List[Tuple[int, float]] = []
    for i in range(len(indices[0])):
        row = int(indices[0][i])
        if row == -1:
            continue
        out.append((row, float(distances[0][i])))
    return out


def bm25_retrieve_chunks(
    query_text: str,
    bm25: Any,
    keys: List[ChunkKey],
    *,
    top_n: int = 50,
    tokenizer=simple_tokenize,
) -> List[Tuple[int, float]]:
    """Score all chunks via BM25 and return the top results."""
    tokens = tokenizer(query_text)
    if not tokens:
        return []
    scores = bm25.get_scores(tokens)
    if len(scores) == 0:
        return []
    idxs = np.argsort(scores)[::-1]
    out: List[Tuple[int, float]] = []
    for j in idxs[:top_n]:
        s = float(scores[j])
        if s <= 0.0:
            continue
        out.append((int(j), s))
    return out


def merge_hybrid_candidates(
    *,
    chunk_records: List[Dict[str, Any]],
    faiss_hits: List[Tuple[int, float]],
    bm25_hits: List[Tuple[int, float]],
    bm25_keys: List[ChunkKey],
) -> List[Candidate]:
    """Merge FAISS and BM25 results into a unified candidate list."""
    by_key: Dict[ChunkKey, Candidate] = {}

    def upsert(key: ChunkKey) -> Candidate:
        if key in by_key:
            return by_key[key]
        rec = next(
            (
                r
                for r in chunk_records
                if r.get("filename") == key.filename
                and r.get("chunk_id") == key.chunk_id
            ),
            None,
        )
        meta = rec if isinstance(rec, dict) else {}
        cand = Candidate(
            key=key,
            chunk_preview=str(meta.get("chunk_preview") or ""),
            meta=meta,
        )
        by_key[key] = cand
        return cand

    for row, score in faiss_hits:
        if row < 0 or row >= len(chunk_records):
            continue
        r = chunk_records[row]
        fn = r.get("filename")
        cid = r.get("chunk_id")
        if not isinstance(fn, str) or not isinstance(cid, int):
            continue
        cand = upsert(ChunkKey(fn, cid))
        cand.faiss_score = score

    for idx, score in bm25_hits:
        if idx < 0 or idx >= len(bm25_keys):
            continue
        key = bm25_keys[idx]
        cand = upsert(key)
        cand.bm25_score = score

    def sort_key(c: Candidate):
        both = int(c.faiss_score is not None and c.bm25_score is not None)
        fa = c.faiss_score if c.faiss_score is not None else float("-inf")
        bm = c.bm25_score if c.bm25_score is not None else float("-inf")
        return (both, fa, bm)

    out = list(by_key.values())
    out.sort(key=sort_key, reverse=True)
    return out
