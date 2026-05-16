"""Embedding generation via Google Gemini API.

Uses the modern google-genai package (not the deprecated google-generativeai).
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

import numpy as np

try:
    from google import genai
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]

from .config import settings

# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

_ALLOWED_METRICS = frozenset({"l2", "cosine"})


def validate_metric(metric: str) -> str:
    m = metric.strip().lower()
    if m not in _ALLOWED_METRICS:
        raise ValueError(f"Invalid metric {metric!r}. Allowed: 'l2', 'cosine'.")
    return m


def generate_embedding(
    text: str,
    *,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> List[float]:
    """Generate an embedding vector using the Gemini embedding API."""
    if genai is None:
        raise ImportError(
            "google-genai not installed. Run: pip install google-genai"
        )

    api_key = api_key or settings.google_api_key
    model = model or settings.embedding_model

    max_chars = 20_000
    if len(text) > max_chars:
        text = text[:max_chars] + " [truncated]"

    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(
        model=model,
        contents=text,
    )

    # Extract embedding from response
    if hasattr(result, "embeddings") and result.embeddings:
        raw = result.embeddings[0].values
    elif hasattr(result, "embedding"):
        raw = result.embedding
    else:
        raise ValueError(
            f"Cannot extract embedding. Response type: {type(result)}, "
            f"repr: {repr(result)[:200]}"
        )

    if not isinstance(raw, (list, tuple)):
        raise ValueError(f"Unexpected embedding type: {type(raw)}")

    vec = list(raw)
    if not vec:
        raise ValueError("API returned empty embedding vector")
    return vec


def build_query_embedding(
    query_text: str,
    *,
    api_key: Optional[str] = None,
    metric: Optional[str] = None,
) -> Tuple[np.ndarray, dict]:
    """Build a (1, dim) float32 query vector, optionally L2-normalized."""
    metric = validate_metric(metric or settings.index_metric)

    vec_list = generate_embedding(query_text, api_key=api_key)
    arr = np.asarray(vec_list, dtype=np.float32)
    if arr.ndim != 1 or arr.size == 0:
        raise ValueError(f"Bad embedding shape {arr.shape}")
    arr = arr.reshape(1, -1)

    normalized = False
    if metric == "cosine":
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)
        arr = arr / norms
        normalized = True

    info = {
        "dimension": int(arr.shape[1]),
        "shape": tuple(arr.shape),
        "dtype": str(arr.dtype),
        "normalized": normalized,
        "metric": metric,
    }
    return arr, info
