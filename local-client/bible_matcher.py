"""
Offline scripture engine. Runs entirely on the church's local device —
no network call, no cloud dependency. Two jobs:
  1. Exact reference lookup ("John 3:16" -> verse text)
  2. Fuzzy matching of spoken/quoted text against the full Bible,
     to catch quotes where the pastor doesn't give the reference.

Bible text is loaded from a local SQLite DB (one row per verse per
version) that ships with the app install — see build_bible_db.py
for how to populate it from a public-domain source (e.g. KJV) or a
licensed API you've cached locally.
"""
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher

DB_PATH = "bible.db"

# Auto-projection threshold in "no operator" / autonomous mode.
# Anything below this never displays automatically — silence is the
# safe failure mode, not a low-confidence guess on the big screen.
AUTO_PROJECT_THRESHOLD = 0.90


@dataclass
class VerseMatch:
    reference: str
    version: str
    text: str
    confidence: float  # 1.0 for explicit reference matches


REFERENCE_PATTERN = re.compile(
    r"\b([1-3]?\s?[A-Za-z]+)\s+(\d{1,3})[:\.](\d{1,3})(?:-(\d{1,3}))?\b"
)


def _connect():
    return sqlite3.connect(DB_PATH)


def lookup_reference(text: str, version: str = "KJV") -> VerseMatch | None:
    """Feature 1: pastor gives an explicit reference like 'Romans 8:28'."""
    match = REFERENCE_PATTERN.search(text)
    if not match:
        return None
    book, chapter, verse_start, verse_end = match.groups()

    conn = _connect()
    cur = conn.cursor()
    cur.execute(
        """SELECT text FROM verses
           WHERE book LIKE ? AND chapter = ? AND verse = ? AND version = ?""",
        (f"%{book.strip()}%", chapter, verse_start, version),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return VerseMatch(
        reference=f"{book.strip()} {chapter}:{verse_start}",
        version=version,
        text=row[0],
        confidence=1.0,
    )


def fuzzy_match_quote(spoken_text: str, version: str = "KJV", top_n: int = 1) -> list[VerseMatch]:
    """
    Feature 2: pastor quotes scripture without giving the reference.
    Simple, fast, fully local approach: compare the spoken phrase
    against a pre-built n-gram index of verse text, ranked by
    similarity. Good enough for fixed-wording translations like KJV/
    NIV; for production, swap SequenceMatcher for a proper local
    fuzzy-search index (e.g. rapidfuzz + a phrase n-gram table) once
    you're past prototyping — this keeps the demo dependency-free.
    """
    spoken_clean = spoken_text.strip().lower()
    if len(spoken_clean.split()) < 4:
        return []  # too short a phrase to match reliably — avoid false positives

    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT book, chapter, verse, text FROM verses WHERE version = ?", (version,))
    rows = cur.fetchall()
    conn.close()

    scored = []
    for book, chapter, verse, verse_text in rows:
        ratio = SequenceMatcher(None, spoken_clean, verse_text.lower()).ratio()
        if ratio > 0.55:  # cheap pre-filter before ranking
            scored.append((ratio, book, chapter, verse, verse_text))

    scored.sort(reverse=True, key=lambda r: r[0])
    return [
        VerseMatch(
            reference=f"{book} {chapter}:{verse}",
            version=version,
            text=verse_text,
            confidence=round(ratio, 2),
        )
        for ratio, book, chapter, verse, verse_text in scored[:top_n]
    ]


def should_auto_project(match: VerseMatch) -> bool:
    """Gate for autonomous/no-operator mode (see product discussion)."""
    return match.confidence >= AUTO_PROJECT_THRESHOLD
