# Sermon Assist — Build Guide

A SaaS for churches: offline scripture projection + fuzzy quote matching
+ AI-generated sermon notes (via Groq).

## Architecture recap
- **Local client** (runs on a laptop at the church): offline speech-to-text
  + offline Bible matching. Works with zero internet.
- **Cloud backend** (Flask on Render): accounts, billing (Paystack),
  sermon archive, and Groq-powered note summarization. The local client
  syncs to this whenever it has a connection — nothing is lost offline.

## Step 1 — Get the pieces you need
1. A [Groq API key](https://console.groq.com) — free tier, sign up and generate a key.
2. A [Paystack](https://paystack.com) account (test mode keys to start).
3. PostgreSQL running locally (or use Render's free Postgres for early testing).
4. Python 3.11+.

## Step 2 — Backend setup
```bash
cd sermon-assist
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: add your GROQ_API_KEY, PAYSTACK keys, DATABASE_URL,
# and — once you have them — DranyTech's real BRAND_PRIMARY/BRAND_ACCENT hex codes
```

## Step 3 — Database
```bash
flask --app run.py db init
flask --app run.py db migrate -m "initial schema"
flask --app run.py db upgrade
```

## Step 4 — Run the backend
```bash
python run.py
# visit http://localhost:5000/signup to create your first church account
```

## Step 5 — Build the offline Bible database (local client)
```bash
cd local-client
pip install -r requirements.txt

# Get a public-domain KJV text file in "Book|Chapter|Verse|Text" format
# (search "KJV bible text file plain text", verify license), then:
python build_bible_db.py kjv.txt KJV
```
This creates `bible.db` — a local SQLite file with the full Bible. This
file lives on the church's device and needs no internet to query.

Repeat for any other version, checking that version's license terms
before bundling (KJV is public domain; NIV/ESV are not — you'll need
API access or a license for those).

## Step 6 — Try the matching engine
```python
from bible_matcher import lookup_reference, fuzzy_match_quote

# Explicit reference
print(lookup_reference("Turn with me to John 3:16"))

# Partial quote, no reference given
print(fuzzy_match_quote("I can do all things through Christ which strengtheneth me"))
```

## Step 7 — Wire up live speech-to-text
The local client needs a streaming STT loop. `pywhispercpp` runs
Whisper fully offline. Skeleton:

```python
from pywhispercpp.model import Model
from bible_matcher import lookup_reference, fuzzy_match_quote, should_auto_project

model = Model('base.en')  # downloads once, then fully offline

def on_transcribed_chunk(text: str):
    ref_match = lookup_reference(text)
    if ref_match:
        project(ref_match)          # explicit reference -> always safe to show
        return

    for match in fuzzy_match_quote(text):
        if should_auto_project(match):   # only in autonomous mode
            project(match)
        # else: log it for the optional supervisor view, don't display

# model.transcribe(...) streaming loop feeds chunks into on_transcribed_chunk
```

## Step 8 — Sync to the cloud after each service
Once the local client has internet again, POST the transcript and
detected verses to your Flask backend:

```python
import requests

requests.post(
    "https://your-app.onrender.com/api/sync/sermon",
    headers={"X-Church-Api-Key": "the-church-id-issued-at-signup"},
    json={
        "title": "Sunday Service",
        "preached_at": "2026-09-27T09:00:00",
        "transcript": full_transcript_text,
        "verses": list_of_detected_verses,
    },
)
```
This is what triggers Groq to generate the final sermon summary and
key points, stored in the dashboard.

## Step 9 — Deploy the backend
1. Push this repo to GitHub.
2. On Render: New → Web Service → connect the repo.
3. Add a Render PostgreSQL instance, copy its URL into `DATABASE_URL`.
4. Add your real `GROQ_API_KEY`, `PAYSTACK_SECRET_KEY`, `BRAND_PRIMARY`,
   `BRAND_ACCENT` as environment variables in Render's dashboard.
5. Build command: `pip install -r requirements.txt`
   Start command: `gunicorn run:app`

## Step 10 — Apply DranyTech's real branding
Everything reads from two variables — `BRAND_PRIMARY` and `BRAND_ACCENT`
in `.env` (or Render's environment settings). Drop in the exact hex
codes from the logo and the whole app (navbar, buttons, verse badges)
restyles with no template edits needed.

## What's still a prototype vs production-ready here
- **Fuzzy matching** uses `difflib.SequenceMatcher` for simplicity —
  swap for `rapidfuzz` + a proper phrase-index once you're past testing
  with real sermon audio; it'll be faster and more accurate at scale.
- **Paystack webhook** doesn't verify the signature yet — required
  before going live so people can't fake renewal events.
- **API-key auth** on the sync endpoint is intentionally simple
  (church ID as the key) — fine for prototyping, upgrade to per-device
  tokens before real churches are on it.
