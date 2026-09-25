"""
One-time script to build bible.db from a text source.
Run this once per version you want to ship offline (KJV is public
domain and easiest to start with; NIV/ESV require checking license
terms with their publishers before bundling).

Expects a plain-text file with one verse per line in the format:
    Book|Chapter|Verse|Text
e.g.
    John|3|16|For God so loved the world...

Public-domain KJV text in this format is widely available — search
for "KJV bible text file" and verify the source's license before use.
"""
import sqlite3
import sys

DB_PATH = "bible.db"


def build(source_txt_path: str, version_code: str):
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

    with open(source_txt_path, encoding="utf-8") as f:
        rows = []
        for line in f:
            parts = line.strip().split("|", 3)
            if len(parts) != 4:
                continue
            book, chapter, verse, text = parts
            rows.append((version_code, book, int(chapter), int(verse), text))

    cur.executemany(
        "INSERT INTO verses (version, book, chapter, verse, text) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"Loaded {len(rows)} verses for version '{version_code}' into {DB_PATH}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python build_bible_db.py <source.txt> <VERSION_CODE>")
        print("Example: python build_bible_db.py kjv.txt KJV")
        sys.exit(1)
    build(sys.argv[1], sys.argv[2])
