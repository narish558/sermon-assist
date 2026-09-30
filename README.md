# Sermon Assist — Build Guide

A SaaS for churches: offline scripture projection + fuzzy quote matching
+ AI-generated sermon notes (via Groq).

## Architecture recap (updated — now fully online)
Everything now runs in one deployed Flask app:
- **Scripture lookup + projection** (`/present/control`, `/present/stage`):
  the operator's browser captures speech using the Web Speech API (built
  into Chrome/Edge — no install, no offline model), sends recognized text
  to the server, which matches it against the Bible database and updates
  what's projected. Automation applies **only** to this — deciding
  whether a verse gets shown. It never touches notes.
- **Sermon notes**: unchanged — generated once, after the service, by
  Groq, when a sermon transcript is uploaded via `/api/sync/sermon`.
- **Billing, accounts, archive**: unchanged.

The original offline local-client (Whisper + on-device matching) still
exists under `local-client/` if you ever want a no-internet fallback for
a venue with unreliable WiFi — but the primary path now is fully online,
inside the same app you already have deployed.

## One extra setup step: bundle the Bible database
The matching engine needs `app/bible.db` to exist (the previous section
never required this since it lived only in the offline client):
```bash
cd local-client
python build_bible_db.py kjv.txt KJV
cp bible.db ../app/bible.db
```
Commit `app/bible.db` to your repo (it's a few MB, fine for git) so it
deploys along with the rest of the app.

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

## Step 7 — Run the control + projection screens
`local_server.py` is a small local Flask server with two pages:
- **`/control`** — operator screen (skip entirely in autonomous mode): live
  transcript, a detected-verse approval card, version switcher, clear button
- **`/stage`** — the clean projection screen, opened fullscreen on the
  projector's display/browser

Both poll an in-memory `state` dict once a second — no websockets, no cloud
call, nothing leaves the building. **Automation applies only to scripture
detection/projection.** Sermon notes are never generated live; they're
produced once, after the service, when Step 8 syncs the transcript to the
cloud (Groq runs there, not on this local server).

```bash
cd local-client
python local_server.py
# Operator device: http://<this-device-local-ip>:5001/control
# Projector browser (fullscreen):  http://<this-device-local-ip>:5001/stage
```

Wire real speech-to-text into it with `pywhispercpp` (fully offline):
```python
from pywhispercpp.model import Model
from local_server import on_transcribed_chunk

model = Model('base.en')  # downloads once, then fully offline
# feed each transcribed chunk into on_transcribed_chunk(text) as it arrives —
# that's the ONLY automated decision point in the app, and it only ever
# decides whether to show a verse, never anything about notes.
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
