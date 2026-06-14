"""Centralized configuration for the AI backend."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Resolve paths relative to this file so the backend works from any cwd.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent

# ---------------------------------------------------------------------------
# .env loader (lightweight, no dependency on python-dotenv at import time)
# ---------------------------------------------------------------------------


def load_env(env_path: Optional[str] = None) -> None:
    """Load KEY=VALUE pairs from a .env file into ``os.environ``.

    Existing env vars take precedence over file values.
    """
    if env_path is None:
        # Try ai_backend/.env first, then project root .env
        candidates = [_THIS_DIR / ".env", _PROJECT_ROOT / ".env"]
    else:
        candidates = [Path(env_path)]

    for p in candidates:
        if not p.exists():
            continue
        with open(p, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ.setdefault(key, value)
        break  # stop after first file found


# ---------------------------------------------------------------------------
# Settings (read once, import everywhere)
# ---------------------------------------------------------------------------

class Settings:
    """Simple settings container — reads from env vars after load_env()."""

    @property
    def google_api_key(self) -> str:
        key = os.environ.get("GOOGLE_API_KEY", "")
        if not key:
            raise RuntimeError("GOOGLE_API_KEY is not set.")
        return key

    @property
    def database_path(self) -> Path:
        raw = os.environ.get("DATABASE_PATH", "")
        if raw:
            p = Path(raw)
            if not p.is_absolute():
                p = _THIS_DIR / p
            return p.resolve()
        # Default: sibling backend/emails.db
        return (_PROJECT_ROOT / "backend" / "emails.db").resolve()

    @property
    def vector_store_dir(self) -> Path:
        raw = os.environ.get("VECTOR_STORE_DIR", "")
        if raw:
            p = Path(raw)
            if not p.is_absolute():
                p = _THIS_DIR / p
            return p.resolve()
        return (_THIS_DIR / "vector_store").resolve()

    @property
    def processed_emails_path(self) -> Path:
        return self.vector_store_dir / "processed_emails.json"

    @property
    def processed_chunks_path(self) -> Path:
        return self.vector_store_dir / "processed_chunks.json"

    @property
    def chunks_index_path(self) -> Path:
        return self.vector_store_dir / "chunks_index.faiss"

    @property
    def chunks_metadata_path(self) -> Path:
        return self.vector_store_dir / "chunks_metadata.json"

    @property
    def chunks_index_config_path(self) -> Path:
        return self.vector_store_dir / "chunks_index_config.json"

    @property
    def bm25_path(self) -> Path:
        return self.vector_store_dir / "bm25_chunks.pkl"

    @property
    def gemini_model(self) -> str:
        return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    @property
    def embedding_model(self) -> str:
        return os.environ.get("EMBEDDING_MODEL", "models/gemini-embedding-001")

    @property
    def index_metric(self) -> str:
        return os.environ.get("INDEX_METRIC", "cosine").strip().lower()


settings = Settings()
