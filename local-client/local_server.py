"""
Local server for the church's own device. Serves two pages over the
local network:
  /control -> operator/pastor screen (or none, in autonomous mode)
  /stage   -> projection screen (open fullscreen on the projector output)

Everything here is offline — no cloud call, no internet dependency.
Automation applies ONLY to scripture detection + projection. Sermon
notes are NOT generated live; they're produced once, after the
service, when local_sync.py uploads the transcript to the cloud
backend (see app/groq_notes.py generate_full_sermon_summary).
"""
from flask import Flask, render_template, jsonify, request
from bible_matcher import lookup_reference, fuzzy_match_quote, should_auto_project, VerseMatch

app = Flask(__name__)

# ---- in-memory live state (single sermon, single device) ----
state = {
    "mode": "assisted",          # "assisted" (operator approves) or "autonomous" (no operator)
    "version": "KJV",
    "transcript_tail": "",       # last few seconds of speech, for the operator to see
    "pending_match": None,       # dict, awaiting operator approval (assisted mode only)
    "projected": None,           # dict, currently shown on stage — or None to clear
}


def _match_to_dict(m: VerseMatch):
    return {"reference": m.reference, "version": m.version, "text": m.text, "confidence": m.confidence}


@app.route("/control")
def control():
    return render_template("control.html")


@app.route("/stage")
def stage():
    return render_template("stage.html")


@app.route("/api/state")
def api_state():
    """Polled by both screens every second — keeps this simple (no websockets needed)."""
    return jsonify(state)


@app.route("/api/mode", methods=["POST"])
def set_mode():
    mode = request.json.get("mode")
    if mode in ("assisted", "autonomous"):
        state["mode"] = mode
    return jsonify(state)


@app.route("/api/version", methods=["POST"])
def set_version():
    state["version"] = request.json.get("version", state["version"])
    return jsonify(state)


@app.route("/api/approve", methods=["POST"])
def approve():
    """Operator clicks 'Project now' on the pending match."""
    if state["pending_match"]:
        state["projected"] = state["pending_match"]
        state["pending_match"] = None
    return jsonify(state)


@app.route("/api/dismiss", methods=["POST"])
def dismiss():
    state["pending_match"] = None
    return jsonify(state)


@app.route("/api/clear", methods=["POST"])
def clear():
    """Manual clear button — always available on both modes."""
    state["projected"] = None
    return jsonify(state)


def on_transcribed_chunk(text: str):
    """
    Called by the speech-to-text loop (see README Step 7) for every
    new chunk of speech. This is the ONLY automated decision point in
    the whole app — it decides whether a verse gets shown, and never
    touches notes.
    """
    state["transcript_tail"] = (state["transcript_tail"] + " " + text)[-400:]

    ref_match = lookup_reference(text, version=state["version"])
    if ref_match:
        # Explicit reference ("John 3:16") is unambiguous -> always safe to project directly
        state["projected"] = _match_to_dict(ref_match)
        state["pending_match"] = None
        return

    matches = fuzzy_match_quote(text, version=state["version"])
    if not matches:
        return
    best = matches[0]

    if state["mode"] == "autonomous":
        if should_auto_project(best):
            state["projected"] = _match_to_dict(best)
        # below threshold -> silence, never guess on the big screen
    else:
        # assisted mode: surface it for the operator to approve/dismiss
        state["pending_match"] = _match_to_dict(best)


if __name__ == "__main__":
    # Runs on the local network only; open http://<this-device-ip>:5001/control
    # from the operator's device and http://<this-device-ip>:5001/stage on the
    # projector's browser.
    app.run(host="0.0.0.0", port=5001, debug=False)
