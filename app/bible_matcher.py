"""
Scripture matching engine, now running server-side in the cloud app.
Two jobs:
  1. Exact reference lookup ("John 3:16" -> verse text)
  2. Fuzzy matching of spoken/quoted text against the full Bible,
     to catch quotes where the pastor doesn't give the reference.

Bible text is loaded from a SQLite DB bundled alongside this file
(app/bible.db) — see local-client/build_bible_db.py to generate it,
then copy the resulting bible.db into app/.

NOTE: this is the SAME engine local-client/bible_matcher.py used for
the offline version. Automation still applies ONLY to scripture
detection/projection here — never to sermon notes, which remain a
separate, post-service Groq summary (see app/groq_notes.py).
"""
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher

import os
DB_PATH = os.path.join(os.path.dirname(__file__), "bible.db")

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

# Matches how references actually get SPOKEN, e.g. "John chapter 10 verse 30",
# "First Corinthians chapter 13 verse 4" — no colon, since nobody says one aloud.
SPOKEN_REFERENCE_PATTERN = re.compile(
    r"\b([1-3]?\s?[A-Za-z]+)\s+chapter\s+(\d{1,3})\s+verse\s+(\d{1,3})\b",
    re.IGNORECASE,
)


def _connect():
    return sqlite3.connect(DB_PATH)


def lookup_reference(text: str, version: str = "KJV") -> VerseMatch | None:
    """Feature 1: pastor gives an explicit reference, spoken or typed —
    'Romans 8:28' or 'Romans chapter 8 verse 28' both work."""
    match = REFERENCE_PATTERN.search(text)
    if match:
        book, chapter, verse_start, verse_end = match.groups()
    else:
        match = SPOKEN_REFERENCE_PATTERN.search(text)
        if not match:
            return None
        book, chapter, verse_start = match.groups()

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
