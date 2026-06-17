"""Database ingestion bridge.

Reads emails from the existing backend SQLite database, converts them
into the format expected by the chunking/embedding pipeline, and builds
all indexes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .chunking import chunk_preview, email_record_to_chunks
from .config import settings
from .embeddings import generate_embedding
from .indexing import build_and_save_faiss_index, ensure_bm25_index

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Read from the SQLite database
# ---------------------------------------------------------------------------


def fetch_emails_from_db(
    db_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read all emails from the backend's SQLite database.

    Returns a list of dicts with keys matching the AI pipeline format:
    filename, subject, sender, receiver, cc, date, extracted_text.
    """
    p = Path(db_path or str(settings.database_path))
    if not p.exists():
        raise FileNotFoundError(f"Database not found: {p}")

    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM emails ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    records: List[Dict[str, Any]] = []
    for row in rows:
        email_id = row["id"]
        sender = row["sender"] or ""
        subject = row["subject"] or ""
        date = row["date"] or ""
        snippet = row["snippet"] or ""

        # Stable index key: prefer imap_uid (e.g. "enron_00001.eml" or the IMAP
        # UID of a synced personal email) so re-ingesting skips emails already in
        # the index and only embeds genuinely new ones. Fall back to the row id.
        try:
            imap_uid = row["imap_uid"]
        except (IndexError, KeyError):
            imap_uid = None
        filename = str(imap_uid).strip() if imap_uid else f"db_email_{email_id}"

        # Use body if available, fall back to snippet
        try:
            body = row["body"] or ""
        except (IndexError, KeyError):
            body = ""

        try:
            receiver = row["receiver"] or ""
        except (IndexError, KeyError):
            receiver = ""

        try:
            cc = row["cc"] or ""
        except (IndexError, KeyError):
            cc = ""

        # Build extracted_text (same format as the .eml pipeline)
        text_parts = []
        if subject:
            text_parts.append(f"Subject: {subject}")
        if sender:
            text_parts.append(f"From: {sender}")
        if receiver:
            text_parts.append(f"To: {receiver}")
        if cc:
            text_parts.append(f"Cc: {cc}")
        if date:
            text_parts.append(f"Date: {date}")

        # Body or snippet
        content = body.strip() if body.strip() else snippet.strip()
        if content:
            text_parts.append(content)

        extracted_text = "\n\n".join(text_parts).strip()

        records.append(
            {
                "filename": filename,
                "subject": subject,
                "sender": sender,
                "receiver": receiver,
                "cc": cc,
                "date": date,
                "extracted_text": extracted_text,
            }
        )

    return records


# ---------------------------------------------------------------------------
# Embed emails
# ---------------------------------------------------------------------------


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return [x for x in data if isinstance(x, dict)]


def _save_json_list(path: Path, data: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def process_and_embed_emails(
    *,
    db_path: Optional[str] = None,
    api_key: Optional[str] = None,
    max_new: Optional[int] = None,
    save_every: int = 5,
) -> List[Dict[str, Any]]:
    """Fetch emails from the DB, embed them, save to processed_emails.json."""
    api_key = api_key or settings.google_api_key
    out_path = settings.processed_emails_path

    # Fetch from database
    db_records = fetch_emails_from_db(db_path)
    logger.info("Fetched %d email(s) from database", len(db_records))

    # Load existing (resume support)
    existing_by_fn: Dict[str, Dict[str, Any]] = {}
    existing = _load_json_list(out_path)
    for rec in existing:
        fn = rec.get("filename")
        if fn:
            existing_by_fn[fn] = rec

    results: List[Dict[str, Any]] = list(existing_by_fn.values())
    new_done = 0
    since_save = 0

    for rec in db_records:
        fn = rec["filename"]
        if fn in existing_by_fn and existing_by_fn[fn].get("embedding"):
            continue
        if max_new is not None and new_done >= max_new:
            break

        text = rec["extracted_text"]
        if not text.strip():
            continue

        try:
            embedding = generate_embedding(text, api_key=api_key)
        except Exception as e:
            msg = str(e)
            is_quota = any(
                s in msg
                for s in ("RESOURCE_EXHAUSTED", "exceeded your current quota", "429")
            )
            logger.warning("Embedding failed for %s: %s", fn, e)
            if is_quota:
                _save_json_list(out_path, results)
                logger.warning("Stopping early due to quota. Progress saved.")
                return results
            time.sleep(2.0)
            continue

        record = {**rec, "embedding": embedding}
        if fn in existing_by_fn:
            # Update in-place
            idx = next(
                i for i, r in enumerate(results) if r.get("filename") == fn
            )
            results[idx] = record
        else:
            results.append(record)
        existing_by_fn[fn] = record
        new_done += 1
        since_save += 1

        if save_every > 0 and since_save >= save_every:
            _save_json_list(out_path, results)
            since_save = 0
            logger.info("Progress: %d new embeddings so far", new_done)

    _save_json_list(out_path, results)
    logger.info(
        "Email embedding complete: %d total records, %d new", len(results), new_done
    )
    return results


# ---------------------------------------------------------------------------
# Chunk and embed
# ---------------------------------------------------------------------------


def process_and_embed_chunks(
    email_records: List[Dict[str, Any]],
    *,
    api_key: Optional[str] = None,
    max_new: Optional[int] = None,
    save_every: int = 10,
) -> List[Dict[str, Any]]:
    """Chunk email records, embed chunks, save to processed_chunks.json."""
    api_key = api_key or settings.google_api_key
    out_path = settings.processed_chunks_path

    # Load existing (resume support)
    existing: Dict[tuple, Dict[str, Any]] = {}
    for rec in _load_json_list(out_path):
        fn = rec.get("filename")
        cid = rec.get("chunk_id")
        if isinstance(fn, str) and isinstance(cid, int):
            existing[(fn, cid)] = rec

    results: Dict[tuple, Dict[str, Any]] = dict(existing)
    new_done = 0
    since_save = 0

    # Only process records that have embeddings (were successfully embedded)
    valid_records = [
        r
        for r in email_records
        if isinstance(r.get("embedding"), (list, tuple)) and len(r["embedding"]) > 0
    ]

    for rec in valid_records:
        chunks = email_record_to_chunks(rec)
        for ch in chunks:
            key = (ch.filename, ch.chunk_id)
            if key in results and results[key].get("embedding"):
                continue
            if max_new is not None and new_done >= max_new:
                _save_json_list(out_path, list(results.values()))
                return list(results.values())

            try:
                embedding = generate_embedding(ch.chunk_text, api_key=api_key)
            except Exception as e:
                msg = str(e)
                is_quota = any(
                    s in msg
                    for s in (
                        "RESOURCE_EXHAUSTED",
                        "exceeded your current quota",
                        "429",
                    )
                )
                logger.warning(
                    "Chunk embedding failed for %s#%d: %s",
                    ch.filename,
                    ch.chunk_id,
                    e,
                )
                if is_quota:
                    _save_json_list(out_path, list(results.values()))
                    logger.warning("Stopping early due to quota. Progress saved.")
                    return list(results.values())
                time.sleep(2.0)
                continue

            results[key] = {
                "filename": ch.filename,
                "chunk_id": ch.chunk_id,
                "subject": ch.subject,
                "sender": ch.sender,
                "receiver": ch.receiver,
                "cc": ch.cc,
                "date": ch.date,
                "thread_key": ch.thread_key,
                "chunk_text": ch.chunk_text,
                "chunk_preview": chunk_preview(ch.chunk_text),
                "embedding": embedding,
            }
            new_done += 1
            since_save += 1

            if save_every > 0 and since_save >= save_every:
                _save_json_list(out_path, list(results.values()))
                since_save = 0
                logger.info("Chunks progress: %d new embeddings so far", new_done)

    final = list(results.values())
    _save_json_list(out_path, final)
    logger.info(
        "Chunk embedding complete: %d total chunks, %d new", len(final), new_done
    )
    return final


# ---------------------------------------------------------------------------
# Build all indexes
# ---------------------------------------------------------------------------


def build_all_indexes(
    chunk_records: List[Dict[str, Any]],
    *,
    metric: Optional[str] = None,
) -> Dict[str, Any]:
    """Build FAISS and BM25 indexes from chunk records."""
    metric = metric or settings.index_metric

    faiss_index = build_and_save_faiss_index(chunk_records, metric=metric)
    faiss_count = faiss_index.ntotal if faiss_index is not None else 0

    bm25, bm25_keys = ensure_bm25_index(chunk_records)
    bm25_count = len(bm25_keys)

    logger.info(
        "Indexes built: FAISS=%d vectors, BM25=%d documents",
        faiss_count,
        bm25_count,
    )

    return {
        "faiss_vectors": faiss_count,
        "bm25_documents": bm25_count,
    }
