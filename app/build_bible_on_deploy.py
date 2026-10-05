"""
Builds app/bible.db automatically if it doesn't already exist — meant
to run once before the app starts (see railpack.json). This avoids
committing a binary database file to git; Railway downloads the
public-domain KJV text and builds the SQLite file itself on deploy.

Set BIBLE_SOURCE_URL as an env var pointing to a plain-text KJV file
in "Book|Chapter|Verse|Text" format, one verse per line. Search
"KJV bible text file plain text pipe delimited" to find one, verify
it's public domain, and host it somewhere raw-fetchable (e.g. a
raw.githubusercontent.com link) — then set that URL in Railway's
environment variables.
"""
import os
import sqlite3
import urllib.request

DB_PATH = os.path.join(os.path.dirname(__file__), "bible.db")
SOURCE_URL = os.environ.get("BIBLE_SOURCE_URL", "")


def build():
    if os.path.exists(DB_PATH):
        print("bible.db already exists, skipping build.")
        return

    if not SOURCE_URL:
        print("WARNING: BIBLE_SOURCE_URL not set — scripture lookup will have no data.")
        return

    print(f"Downloading Bible text from {SOURCE_URL} ...")
    with urllib.request.urlopen(SOURCE_URL) as resp:
        lines = resp.read().decode("utf-8").splitlines()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS verses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            book TEXT NOT NULL,
            chapter INTEGER NOT NULL,
            verse INTEGER NOT NULL,
            text TEXT NOT NULL
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lookup ON verses(version, book, chapter, verse)")

    rows = []
    for line in lines:
        parts = line.strip().split("|", 3)
        if len(parts) != 4:
            continue
        book, chapter, verse, text = parts
        rows.append(("KJV", book, int(chapter), int(verse), text))

    cur.executemany(
        "INSERT INTO verses (version, book, chapter, verse, text) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"Built bible.db with {len(rows)} verses.")


if __name__ == "__main__":
    build()
