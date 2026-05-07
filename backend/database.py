import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "emails.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imap_uid TEXT,
            sender TEXT NOT NULL,
            subject TEXT NOT NULL,
            date TEXT NOT NULL,
            snippet TEXT NOT NULL
        )
    """)

    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            imap_host TEXT NOT NULL,
            imap_port INTEGER NOT NULL,
            email TEXT NOT NULL
        )
    """)

    
    try:
        cur.execute("ALTER TABLE emails ADD COLUMN imap_uid TEXT")
    except Exception:
        pass

    
    try:
        cur.execute("CREATE UNIQUE INDEX idx_emails_imap_uid ON emails(imap_uid)")
    except Exception:
        pass

    conn.commit()
    conn.close()