"""
This is the bridge between the offline local client and the cloud
SaaS. The local client captures everything (transcript, detected
verses) regardless of connectivity, then calls these endpoints
whenever it regains internet access.
"""
from datetime import datetime
from flask import Blueprint, request, jsonify

from app.models import db, Church, Sermon, SermonVerse
from app.groq_notes import generate_full_sermon_summary

sync_bp = Blueprint("sync", __name__, url_prefix="/api/sync")


def _authenticate_church(req):
    """Simple API-key auth for the local client — swap for something
    stronger (per-device tokens) before production."""
    api_key = req.headers.get("X-Church-Api-Key")
    return Church.query.filter_by(id=api_key).first() if api_key else None


@sync_bp.route("/sermon", methods=["POST"])
def upload_sermon():
    church = _authenticate_church(request)
    if not church:
        return jsonify({"error": "unauthorized"}), 401

    data = request.json
    transcript = data.get("transcript", "")
    verses = data.get("verses", [])  # list of {reference, version, text, offset_seconds, confidence, auto_projected}

    summary = generate_full_sermon_summary(transcript) if transcript else {}

    sermon = Sermon(
        church_id=church.id,
        title=summary.get("title") or data.get("title", "Untitled sermon"),
        preached_at=datetime.fromisoformat(data["preached_at"]) if data.get("preached_at") else datetime.utcnow(),
        transcript=transcript,
        notes=str(summary.get("key_points", [])),
        synced_at=datetime.utcnow(),
    )
    db.session.add(sermon)
    db.session.flush()

    for v in verses:
        db.session.add(SermonVerse(
            sermon_id=sermon.id,
            reference=v.get("reference"),
            version=v.get("version"),
            text=v.get("text"),
            detected_at_seconds=v.get("offset_seconds"),
            match_confidence=v.get("confidence"),
            was_auto_projected=v.get("auto_projected", False),
        ))

    db.session.commit()
    return jsonify({"status": "synced", "sermon_id": sermon.id}), 201
