from fastapi import FastAPI
from pydantic import BaseModel
from backend.database import get_conn, init_db
print("✅ LOADED NEW MAIN.PY")
import imaplib
import email
from email.header import decode_header

app = FastAPI()

# -----------------------
# Models
# -----------------------
class EmailCreate(BaseModel):
    sender: str
    subject: str
    date: str
    snippet: str

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


# -----------------------
# Helpers
# -----------------------
def _decode_maybe(value):
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

def _get_body_text(msg):
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


# -----------------------
# Basic endpoint
# -----------------------
@app.get("/")
def home():
    return {"message": "Server is running"}


# -----------------------
# Emails endpoints
# -----------------------
@app.get("/emails")
def list_emails():
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM emails ORDER BY id DESC")
    rows = cur.fetchall()

    emails = []
    for row in rows:
        emails.append({
            "id": row["id"],
            "from": row["sender"],
            "subject": row["subject"],
            "date": row["date"],
            "snippet": row["snippet"],
        })

    conn.close()
    return emails


@app.post("/emails")
def create_email(email_in: EmailCreate):
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO emails (sender, subject, date, snippet)
        VALUES (?, ?, ?, ?)
    """, (email_in.sender, email_in.subject, email_in.date, email_in.snippet))

    conn.commit()
    conn.close()

    return {"message": "Email added successfully"}


# -----------------------
# Accounts endpoints
# -----------------------
@app.get("/accounts")
def list_accounts():
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM accounts ORDER BY id DESC")
    rows = cur.fetchall()

    accounts = []
    for row in rows:
        accounts.append({
            "id": row["id"],
            "provider": row["provider"],
            "imap_host": row["imap_host"],
            "imap_port": row["imap_port"],
            "email": row["email"],
        })

    conn.close()
    return accounts


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


# -----------------------
# IMAP test
# -----------------------
@app.post("/imap/test")
def test_imap_connection(data: IMAPTestRequest):
    try:
        mail = imaplib.IMAP4_SSL(data.imap_host, data.imap_port)
        mail.login(data.email, data.password)
        mail.logout()
        return {"status": "Connection successful"}
    except Exception as e:
        return {"status": "Connection failed", "error": str(e)}


# -----------------------
# Sync emails into SQLite
# -----------------------
@app.post("/sync")
def sync_emails(req: SyncRequest):
    init_db()

    try:
        mail = imaplib.IMAP4_SSL(req.imap_host, req.imap_port)
        mail.login(req.email, req.password)
        mail.select("INBOX")

        status, data = mail.search(None, "ALL")
        if status != "OK":
            return {"status": "failed", "error": "IMAP search failed"}

        all_ids = data[0].split()
        latest_ids = all_ids[-req.limit:] if req.limit > 0 else all_ids

        conn = get_conn()
        cur = conn.cursor()

        inserted = 0

        for mid in reversed(latest_ids):
            status, msg_data = mail.fetch(mid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            sender = _decode_maybe(msg.get("From"))
            subject = _decode_maybe(msg.get("Subject"))
            date = _decode_maybe(msg.get("Date"))

            body = _get_body_text(msg)
            snippet = (body or "").strip().replace("\n", " ")
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."

            cur.execute("""
                INSERT INTO emails (sender, subject, date, snippet)
                VALUES (?, ?, ?, ?)
            """, (sender or "(unknown)", subject or "(no subject)", date or "", snippet or ""))

            inserted += 1

        conn.commit()
        conn.close()
        mail.logout()

        return {"status": "ok", "inserted": inserted}

    except Exception as e:
        return {"status": "failed", "error": str(e)}