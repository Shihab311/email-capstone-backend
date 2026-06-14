"""FAISS and BM25 index building, loading, and saving.

Adapted from AI-Backend-Extended/build_faiss_index.py,
scripts/build_faiss_chunks_index.py, and rag/hybrid_retrieval.py.
"""

from __future__ import annotations

import json
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import faiss
except ImportError:  # pragma: no cover
    faiss = None  # type: ignore[assignment]

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover
    BM25Okapi = None  # type: ignore[assignment]

from .config import settings

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChunkKey:
    filename: str
    chunk_id: int


@dataclass
class Candidate:
    key: ChunkKey
    chunk_preview: str
    meta: Dict[str, Any]
    faiss_score: Optional[float] = None
    bm25_score: Optional[float] = None


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

_ALLOWED_METRICS = frozenset({"l2", "cosine"})


def validate_metric(metric: str) -> str:
    m = metric.strip().lower()
    if m not in _ALLOWED_METRICS:
        raise ValueError(f"Invalid metric {metric!r}. Allowed: l2, cosine.")
    return m


def l2_normalize_rows(vectors: np.ndarray) -> np.ndarray:
    """Return row-normalized vectors for cosine/IP search."""
    if vectors.ndim != 2:
        raise ValueError(f"Expected 2D vectors, got shape {vectors.shape}")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return vectors / norms


# ---------------------------------------------------------------------------
# FAISS index
# ---------------------------------------------------------------------------


def build_and_save_faiss_index(
    chunk_records: List[Dict[str, Any]],
    *,
    output_dir: Optional[str] = None,
    metric: Optional[str] = None,
) -> Optional[Any]:
    """Build a FAISS index over chunk embeddings and save to disk.

    Returns the FAISS index object, or None if no valid embeddings.
    """
    if faiss is None:
        raise ImportError("faiss-cpu not installed. Run: pip install faiss-cpu")

    metric = validate_metric(metric or settings.index_metric)
    out = Path(output_dir or str(settings.vector_store_dir))
    out.mkdir(parents=True, exist_ok=True)

    # Filter to records with embeddings
    valid = [
        r
        for r in chunk_records
        if isinstance(r.get("embedding"), (list, tuple)) and len(r["embedding"]) > 0
    ]
    if not valid:
        return None

    vectors = np.array([r["embedding"] for r in valid], dtype=np.float32)
    if vectors.ndim != 2:
        raise ValueError(f"Expected 2D embedding array, got shape {vectors.shape}")

    dim = int(vectors.shape[1])
    normalized = False

    if metric == "cosine":
        vectors = l2_normalize_rows(vectors)
        index = faiss.IndexFlatIP(dim)
        index_type = "IndexFlatIP"
        normalized = True
    else:
        index = faiss.IndexFlatL2(dim)
        index_type = "IndexFlatL2"

    index.add(vectors)

    # Save index
    idx_path = out / "chunks_index.faiss"
    faiss.write_index(index, str(idx_path))

    # Save metadata (without embeddings)
    meta = []
    for r in valid:
        meta.append(
            {
                "filename": r.get("filename", ""),
                "chunk_id": r.get("chunk_id", 0),
                "subject": r.get("subject", ""),
                "sender": r.get("sender", ""),
                "receiver": r.get("receiver", ""),
                "cc": r.get("cc", ""),
                "date": r.get("date", ""),
                "thread_key": r.get("thread_key", ""),
                "chunk_preview": r.get("chunk_preview", ""),
            }
        )
    meta_path = out / "chunks_metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    # Save config
    cfg_path = out / "chunks_index_config.json"
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(
            {"metric": metric, "index_type": index_type, "normalized": normalized},
            f,
            indent=2,
        )

    return index


def load_faiss_index(path: Optional[str] = None) -> Any:
    """Load a FAISS index from disk."""
    if faiss is None:
        raise ImportError("faiss-cpu not installed. Run: pip install faiss-cpu")
    p = Path(path or str(settings.chunks_index_path))
    if not p.exists():
        raise FileNotFoundError(f"FAISS index not found: {p}")
    return faiss.read_index(str(p))


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------


def simple_tokenize(text: str) -> List[str]:
    t = (text or "").lower()
    return re.findall(r"[a-z0-9]+", t)


def build_bm25_index(
    chunk_records: List[Dict[str, Any]],
    *,
    tokenizer=simple_tokenize,
) -> Tuple[Any, List[ChunkKey]]:
    """Build a BM25 index over chunk text."""
    if BM25Okapi is None:
        raise ImportError("rank-bm25 not installed. Run: pip install rank-bm25")

    keys: List[ChunkKey] = []
    corpus_tokens: List[List[str]] = []

    for r in chunk_records:
        fn = r.get("filename")
        cid = r.get("chunk_id")
        if not isinstance(fn, str) or not isinstance(cid, int):
            continue
        text = r.get("chunk_text") or ""
        tokens = tokenizer(str(text))
        if not tokens:
            continue
        keys.append(ChunkKey(filename=fn, chunk_id=cid))
        corpus_tokens.append(tokens)

    bm25 = BM25Okapi(corpus_tokens)
    return bm25, keys


def _signature_from_keys(
    keys: List[ChunkKey],
) -> Tuple[int, str, int, str, int]:
    if not keys:
        return (0, "", 0, "", 0)
    ordered = sorted(keys, key=lambda k: (k.filename, k.chunk_id))
    first, last = ordered[0], ordered[-1]
    return (len(ordered), first.filename, first.chunk_id, last.filename, last.chunk_id)


def save_bm25(path: str, bm25: Any, keys: List[ChunkKey]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    sig = _signature_from_keys(keys)
    with open(p, "wb") as f:
        pickle.dump({"bm25": bm25, "keys": keys, "sig": sig}, f)


def load_bm25(path: Optional[str] = None) -> Tuple[Any, List[ChunkKey]]:
    p = Path(path or str(settings.bm25_path))
    if not p.exists():
        raise FileNotFoundError(str(p))
    with open(p, "rb") as f:
        obj = pickle.load(f)
    return obj["bm25"], obj["keys"]


def ensure_bm25_index(
    chunk_records: List[Dict[str, Any]],
    *,
    bm25_path: Optional[str] = None,
) -> Tuple[Any, List[ChunkKey]]:
    """Build or load BM25 index, rebuilding if stale."""
    bm25_path_str = bm25_path or str(settings.bm25_path)

    expected_bm25, expected_keys = build_bm25_index(chunk_records)
    expected_sig = _signature_from_keys(expected_keys)

    p = Path(bm25_path_str)
    if p.exists():
        try:
            with open(p, "rb") as f:
                obj = pickle.load(f)
            keys = obj.get("keys")
            sig = obj.get("sig")
            bm25 = obj.get("bm25")
            if (
                isinstance(keys, list)
                and isinstance(sig, tuple)
                and bm25 is not None
                and sig == expected_sig
            ):
                return bm25, keys
        except Exception:
            pass

    # Rebuild
    save_bm25(bm25_path_str, expected_bm25, expected_keys)
    return expected_bm25, expected_keys
