from database import init_db, get_conn
print("seed.py started")
def seed():
    init_db()
    conn = get_conn()
    cur = conn.cursor()

    # clear old data (so it doesn't duplicate)
    cur.execute("DELETE FROM emails")

    cur.execute("""
        INSERT INTO emails (sender, subject, date, snippet)
        VALUES (?, ?, ?, ?)
    """, (
        "boss@example.com",
        "Project deadline update",
        "2026-01-10",
        "The deadline was moved to next week..."
    ))

    conn.commit()
    conn.close()
    print("Seeded database with 1 email ✅")

if __name__ == "__main__":
    seed()