"""
Sermon note generation using Groq's free/fast inference.
Groq hosts open models (Llama 3.3 etc.) at very low latency, which
suits chunked "every 30-60s" summarization well, and is free within
generous rate limits at the time of writing — confirm current
limits at https://console.groq.com/docs/rate-limits before scaling.
"""
import os
import json
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

NOTES_SYSTEM_PROMPT = """You are assisting a church note-taking system.
Given a chunk of a live sermon transcript, extract 0-3 concise bullet
points capturing new ideas, themes, or scripture references introduced
in THIS chunk only. Do not repeat earlier points. Return strict JSON:
{"points": ["point one", "point two"]}
If nothing new/substantive was said (e.g. just transition words), return
{"points": []}.
"""


def summarize_chunk(transcript_chunk: str) -> list[str]:
    """Call Groq on a ~30-60s transcript chunk, return new bullet points."""
    if not transcript_chunk.strip():
        return []

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": NOTES_SYSTEM_PROMPT},
            {"role": "user", "content": transcript_chunk},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(response.choices[0].message.content)
        return data.get("points", [])
    except (json.JSONDecodeError, KeyError, IndexError):
        return []


def generate_full_sermon_summary(full_transcript: str) -> dict:
    """Run once at end of sermon for a polished final summary + title suggestion."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": (
                "Summarize this full sermon transcript into: a suggested title, "
                "3-6 key points, and the main scripture references used. "
                'Return strict JSON: {"title": "...", "key_points": ["..."], '
                '"scriptures": ["..."]}'
            )},
            {"role": "user", "content": full_transcript},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, KeyError, IndexError):
        return {"title": "", "key_points": [], "scriptures": []}
