"""Paragraph-based email chunking.

Adapted from AI-Backend-Extended/rag/rag_chunks.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class EmailChunk:
    filename: str
    chunk_id: int
    chunk_text: str
    subject: str = ""
    sender: str = ""
    receiver: str = ""
    cc: str = ""
    date: str = ""
    thread_key: str = ""


_PREFIX_RE = re.compile(r"^(re|fw|fwd)\s*:\s*", flags=re.IGNORECASE)


def normalize_subject(subject: str) -> str:
    """Strip reply/forward prefixes and normalize whitespace."""
    s = (subject or "").strip()
    while True:
        new = _PREFIX_RE.sub("", s).strip()
        if new == s:
            break
        s = new
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def build_thread_key(subject: str) -> str:
    return normalize_subject(subject)


def _split_paragraphs(text: str) -> List[str]:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = [p.strip() for p in re.split(r"\n\s*\n+", t) if p.strip()]
    return parts


def chunk_text_by_paragraphs(
    text: str,
    max_chars: int = 1800,
    min_chars: int = 200,
) -> List[str]:
    """Split text into chunks respecting paragraph boundaries."""
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: List[str] = []
    buf: List[str] = []
    size = 0

    def flush():
        nonlocal buf, size
        if buf:
            chunk = "\n\n".join(buf).strip()
            if chunk:
                chunks.append(chunk)
        buf = []
        size = 0

    for p in paragraphs:
        if len(p) > max_chars:
            flush()
            step = max_chars
            for i in range(0, len(p), step):
                sub = p[i : i + step].strip()
                if sub:
                    chunks.append(sub)
            continue

        next_size = size + (2 if buf else 0) + len(p)
        if next_size > max_chars:
            flush()
        buf.append(p)
        size = size + (2 if len(buf) > 1 else 0) + len(p)

    flush()

    # Merge tiny trailing chunks back into the previous one
    merged: List[str] = []
    for ch in chunks:
        if (
            merged
            and len(ch) < min_chars
            and (len(merged[-1]) + 2 + len(ch) <= max_chars)
        ):
            merged[-1] = (merged[-1] + "\n\n" + ch).strip()
        else:
            merged.append(ch)
    return merged


def email_record_to_chunks(
    record: Dict[str, Any],
    *,
    include_headers: bool = True,
    max_chars: int = 1800,
    min_chars: int = 200,
) -> List[EmailChunk]:
    """Convert an email record dict into a list of EmailChunk objects."""
    filename = str(record.get("filename") or "")
    subject = str(record.get("subject") or "")
    sender = str(record.get("sender") or "")
    receiver = str(record.get("receiver") or "")
    cc = str(record.get("cc") or "")
    date = str(record.get("date") or "")
    extracted = str(record.get("extracted_text") or "")

    if not filename or not extracted.strip():
        return []

    header_lines: List[str] = []
    if include_headers:
        if subject:
            header_lines.append(f"Subject: {subject}")
        if sender:
            header_lines.append(f"From: {sender}")
        if receiver:
            header_lines.append(f"To: {receiver}")
        if cc:
            header_lines.append(f"Cc: {cc}")
        if date:
            header_lines.append(f"Date: {date}")

    header = "\n".join(header_lines).strip()
    thread_key = build_thread_key(subject)

    body = extracted.strip()
    body_chunks = chunk_text_by_paragraphs(
        body, max_chars=max_chars, min_chars=min_chars
    )

    out: List[EmailChunk] = []
    for i, ch in enumerate(body_chunks, start=1):
        chunk_text = (header + "\n\n" + ch).strip() if header else ch.strip()
        out.append(
            EmailChunk(
                filename=filename,
                chunk_id=i,
                chunk_text=chunk_text,
                subject=subject,
                sender=sender,
                receiver=receiver,
                cc=cc,
                date=date,
                thread_key=thread_key,
            )
        )
    return out


def chunk_preview(text: str, max_chars: int = 220) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    t = re.sub(r"\s+", " ", t)
    return t if len(t) <= max_chars else t[:max_chars].rstrip() + "…"
