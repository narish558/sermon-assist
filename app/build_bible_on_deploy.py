"""
Builds app/bible.db automatically on Railway during deploy, if it
doesn't already exist. Downloads the public-domain KJV text directly
from the scrollmapper/bible_databases GitHub repo (2024 branch, which
has the simple per-verse CSV layout) and converts it — no local
download step needed, nothing committed to git.

See railpack.json's startCommand for where this runs.
"""
import csv
import io
import os
import sqlite3
import urllib.request

DB_PATH = os.path.join(os.path.dirname(__file__), "bible.db")

VERSES_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/2024/csv/t_kjv.csv"
BOOKS_URL = "https://raw.githubusercontent.com/scrollmapper/bible_databases/2024/csv/key_english.csv"


def _fetch_csv_rows(url):
    with urllib.request.urlopen(url) as resp:
        text = resp.read().decode("utf-8-sig")  # handles BOM if present
    return list(csv.DictReader(io.StringIO(text)))


def _find_key(row, candidates):
    """CSV column names vary slightly between forks/branches — try a
    few likely options rather than hardcoding one that might not match."""
    for c in candidates:
        if c in row:
            return c
    raise KeyError(f"None of {candidates} found in CSV columns: {list(row.keys())}")


def build():
    if os.path.exists(DB_PATH):
        print("bible.db already exists, skipping build.")
        return

    print("Downloading book name lookup...")
    book_rows = _fetch_csv_rows(BOOKS_URL)
    book_key = _find_key(book_rows[0], ["b", "book_id", "id"])
    name_key = _find_key(book_rows[0], ["n", "name", "book_name"])
    books = {row[book_key]: row[name_key] for row in book_rows}

    print("Downloading KJV verse text...")
    verse_rows = _fetch_csv_rows(VERSES_URL)
    book_col = _find_key(verse_rows[0], ["b", "book_id"])
    chap_col = _find_key(verse_rows[0], ["c", "chapter"])
    verse_col = _find_key(verse_rows[0], ["v", "verse"])
    text_col = _find_key(verse_rows[0], ["t", "text"])

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
    for row in verse_rows:
        book_name = books.get(row[book_col], row[book_col])
        rows.append(("KJV", book_name, int(row[chap_col]), int(row[verse_col]), row[text_col]))

    cur.executemany(
        "INSERT INTO verses (version, book, chapter, verse, text) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"Built bible.db with {len(rows)} verses.")


if __name__ == "__main__":
    try:
        build()
    except Exception as e:
        # Never let a Bible-build hiccup prevent the app from starting —
        # scripture lookup just stays empty until this is fixed/retried.
        print(f"WARNING: bible.db build failed ({e}). App will start without scripture data.")
