"""
Scripture lookup + projection, now running in the cloud app.
Speech is captured in the operator's browser using the Web Speech API
(built into Chrome/Edge, no install needed) and sent here as text.

Automation applies ONLY to deciding whether to show a verse. Sermon
notes are never touched here — those stay a separate, post-service
Groq summary triggered by app/routes/sync.py.

State is kept in memory per church (fine for a single web process;
if you scale to multiple server instances later, move `state_store`
to Redis or the database instead).
"""
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user

from app.bible_matcher import lookup_reference, fuzzy_match_quote, should_auto_project

present_bp = Blueprint("present", __name__, url_prefix="/present")

# church_id -> state dict
state_store = {}


def _state():
    cid = current_user.church_id
    if cid not in state_store:
        state_store[cid] = {
            "mode": "assisted",
            "version": current_user.church.default_bible_version or "KJV",
            "transcript_tail": "",
            "pending_match": None,
            "projected": None,
        }
    return state_store[cid]


@present_bp.route("/control")
@login_required
def control():
    return render_template("present_control.html")


@present_bp.route("/stage")
@login_required
def stage():
    """Convenience redirect for the operator, who IS logged in — sends
    them to their own church's public stage link."""
    from flask import redirect, url_for
    return redirect(url_for("present.stage_public", church_id=current_user.church_id))


@present_bp.route("/stage/<int:church_id>")
def stage_public(church_id):
    """Public, no-login page — this is what actually runs on the
    projector's browser, which obviously can't log in to your account."""
    return render_template("present_stage.html", church_id=church_id)


@present_bp.route("/api/state/public/<int:church_id>")
def api_state_public(church_id):
    """Public read-only state for the stage screen. Only ever exposes
    the currently projected verse — never the transcript or anything
    else from the operator's control screen."""
    s = state_store.get(church_id)
    if not s:
        return jsonify({"projected": None})
    return jsonify({"projected": s["projected"]})


@present_bp.route("/api/state")
@login_required
def api_state():
    return jsonify(_state())


@present_bp.route("/api/mode", methods=["POST"])
@login_required
def set_mode():
    mode = request.json.get("mode")
    if mode in ("assisted", "autonomous"):
        _state()["mode"] = mode
    return jsonify(_state())


@present_bp.route("/api/version", methods=["POST"])
@login_required
def set_version():
    _state()["version"] = request.json.get("version", _state()["version"])
    return jsonify(_state())


@present_bp.route("/api/approve", methods=["POST"])
@login_required
def approve():
    s = _state()
    if s["pending_match"]:
        s["projected"] = s["pending_match"]
        s["pending_match"] = None
    return jsonify(s)


@present_bp.route("/api/dismiss", methods=["POST"])
@login_required
def dismiss():
    _state()["pending_match"] = None
    return jsonify(_state())


@present_bp.route("/api/clear", methods=["POST"])
@login_required
def clear():
    _state()["projected"] = None
    return jsonify(_state())


@present_bp.route("/api/manual", methods=["POST"])
@login_required
def manual_lookup():
    """Operator types a reference directly and projects it immediately —
    bypasses speech/confidence entirely, since a human typed it on purpose."""
    query = request.json.get("query", "")
    s = _state()
    match = lookup_reference(query, version=s["version"])
    if not match:
        return jsonify({**s, "manual_error": "Couldn't find that reference. Try e.g. 'John 3:16'."})

    s["projected"] = {
        "reference": match.reference, "version": match.version,
        "text": match.text, "confidence": 1.0,
    }
    s["pending_match"] = None
    return jsonify(s)


@present_bp.route("/api/process", methods=["POST"])
@login_required
def process_speech():
    """
    Called from the browser every time the Web Speech API finishes a
    phrase. This is the ONLY automated decision point in the app — it
    only ever decides whether to project a verse, nothing about notes.
    """
    text = request.json.get("text", "")
    s = _state()
    s["transcript_tail"] = (s["transcript_tail"] + " " + text)[-400:]

    ref_match = lookup_reference(text, version=s["version"])
    if ref_match:
        s["projected"] = {
            "reference": ref_match.reference, "version": ref_match.version,
            "text": ref_match.text, "confidence": ref_match.confidence,
        }
        s["pending_match"] = None
        return jsonify(s)

    matches = fuzzy_match_quote(text, version=s["version"])
    if matches:
        best = matches[0]
        match_dict = {
            "reference": best.reference, "version": best.version,
            "text": best.text, "confidence": best.confidence,
        }
        if s["mode"] == "autonomous" and should_auto_project(best):
            s["projected"] = match_dict
        elif s["mode"] == "assisted":
            s["pending_match"] = match_dict
        # autonomous + below threshold -> silence, never guess on screen

    return jsonify(s)
