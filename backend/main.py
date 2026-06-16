from fastapi import FastAPI
from pydantic import BaseModel
from backend.database import get_conn, init_db

import imaplib
import email
from email.header import decode_header
from io import BytesIO
from pypdf import PdfReader

app = FastAPI()


class EmailCreate(BaseModel):
    sender: str
    receiver: str = ""
    cc: str = ""
    subject: str
    date: str
    snippet: str
    body: str = ""


class AccountCreate(BaseModel):
    provider: str
    imap_host: str
    imap_port: int
    email: str


class IMAPTestRequest(BaseModel):
    imap_host: str
    imap_port: int
    email: str
    password: str


class SyncRequest(BaseModel):
    imap_host: str
    imap_port: int
    email: str
    password: str
    limit: int = 20


def _decode_maybe(value: str | None) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            out += text.decode(enc or "utf-8", errors="ignore")
        else:
            out += text
    return out


def _get_body_text(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")

            if ctype == "text/plain" and "attachment" not in disp.lower():
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="ignore")

        for part in msg.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                html = payload.decode(charset, errors="ignore")
                return " ".join(html.replace("<", " <").split())

    payload = msg.get_payload(decode=True) or b""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="ignore")


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n".join(parts).strip()
    except Exception:
        return ""


@app.get("/")
def home():
    return {"message": "Server is running"}


@app.get("/emails")
def list_emails():
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM emails ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "imap_uid": row["imap_uid"],
            "from": row["sender"],
            "to": row["receiver"],
            "cc": row["cc"],
            "subject": row["subject"],
            "date": row["date"],
            "snippet": row["snippet"],
            "body": row["body"],
        }
        for row in rows
    ]


@app.post("/emails")
def create_email(email_in: EmailCreate):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO emails (imap_uid, sender, receiver, cc, subject, date, snippet, body)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        None,
        email_in.sender,
        email_in.receiver,
        email_in.cc,
        email_in.subject,
        email_in.date,
        email_in.snippet,
        email_in.body,
    ))

    conn.commit()
    conn.close()
    return {"message": "Email added successfully"}


@app.delete("/emails")
def clear_emails():
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM attachments")
    cur.execute("DELETE FROM emails")
    deleted = cur.rowcount

    conn.commit()
    conn.close()

    return {"status": "ok", "deleted": deleted}


@app.get("/accounts")
def list_accounts():
    init_db()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM accounts ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "provider": row["provider"],
            "imap_host": row["imap_host"],
            "imap_port": row["imap_port"],
            "email": row["email"],
        }
        for row in rows
    ]


@app.post("/accounts")
def create_account(account: AccountCreate):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO accounts (provider, imap_host, imap_port, email)
        VALUES (?, ?, ?, ?)
    """, (account.provider, account.imap_host, account.imap_port, account.email))

    conn.commit()
    conn.close()

    return {"message": "Account saved"}


@app.post("/imap/test")
def test_imap_connection(data: IMAPTestRequest):
    try:
        mail = imaplib.IMAP4_SSL(data.imap_host, data.imap_port)
        mail.login(data.email, data.password)
        mail.logout()
        return {"status": "Connection successful"}
    except Exception as e:
        return {"status": "Connection failed", "error": str(e)}


@app.post("/sync")
def sync_emails(req: SyncRequest):
    init_db()

    try:
        mail = imaplib.IMAP4_SSL(req.imap_host, req.imap_port)
        mail.login(req.email, req.password)
        mail.select("INBOX")

        status, data = mail.uid("search", None, "ALL")
        if status != "OK":
            mail.logout()
            return {"status": "failed", "error": "IMAP search failed"}

        all_uids = data[0].split()
        latest_uids = all_uids[-req.limit:] if req.limit > 0 else all_uids

        conn = get_conn()
        cur = conn.cursor()

        inserted = 0
        skipped = 0
        pdf_attachments_saved = 0

        for uid in reversed(latest_uids):
            uid_str = uid.decode() if isinstance(uid, (bytes, bytearray)) else str(uid)

            cur.execute("SELECT 1 FROM emails WHERE imap_uid = ? LIMIT 1", (uid_str,))
            if cur.fetchone():
                skipped += 1
                continue

            status, msg_data = mail.uid("fetch", uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            sender = _decode_maybe(msg.get("From"))
            receiver = _decode_maybe(msg.get("To"))
            cc_val = _decode_maybe(msg.get("Cc"))
            subject = _decode_maybe(msg.get("Subject"))
            date = _decode_maybe(msg.get("Date"))

            body = _get_body_text(msg)
            snippet = (body or "").strip().replace("\n", " ")
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."

            try:
                cur.execute("""
                    INSERT INTO emails (imap_uid, sender, receiver, cc, subject, date, snippet, body)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    uid_str,
                    sender or "(unknown)",
                    receiver or "",
                    cc_val or "",
                    subject or "(no subject)",
                    date or "",
                    snippet or "",
                    (body or "").strip(),
                ))

                email_id = cur.lastrowid

                for part in msg.walk():
                    filename = part.get_filename()
                    content_type = part.get_content_type()

                    if filename and filename.lower().endswith(".pdf"):
                        pdf_bytes = part.get_payload(decode=True)

                        if pdf_bytes:
                            extracted_text = _extract_pdf_text(pdf_bytes)

                            cur.execute("""
                                INSERT INTO attachments (email_id, filename, content_type, extracted_text)
                                VALUES (?, ?, ?, ?)
                            """, (
                                email_id,
                                filename,
                                content_type,
                                extracted_text,
                            ))

                            pdf_attachments_saved += 1

                inserted += 1

            except Exception:
                skipped += 1

        conn.commit()
        conn.close()
        mail.logout()

        return {
            "status": "ok",
            "inserted": inserted,
            "skipped": skipped,
            "pdf_attachments_saved": pdf_attachments_saved,
        }

    except Exception as e:
        return {"status": "failed", "error": str(e)}


@app.get("/attachments")
def list_attachments():
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT attachments.*, emails.subject, emails.sender
        FROM attachments
        JOIN emails ON attachments.email_id = emails.id
        ORDER BY attachments.id DESC
    """)

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "email_id": row["email_id"],
            "filename": row["filename"],
            "content_type": row["content_type"],
            "subject": row["subject"],
            "from": row["sender"],
            "extracted_text_preview": (row["extracted_text"] or "")[:500],
        }
        for row in rows
    ]


@app.get("/emails/{email_id}/attachments")
def get_email_attachments(email_id: int):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM attachments
        WHERE email_id = ?
        ORDER BY id DESC
    """, (email_id,))

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "email_id": row["email_id"],
            "filename": row["filename"],
            "content_type": row["content_type"],
            "extracted_text": row["extracted_text"],
        }
        for row in rows
    ]