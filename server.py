"""
RepoSense production API - Flask + SSE + static frontend.
JacCloud-ready: PORT env, CORS, real analysis via orchestrator.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

from config import GEMINI_API_KEY, GITHUB_TOKEN, OPENAI_API_KEY, PORT
from orchestrator import answer_query, resolve_approval, run_analysis
from utils import snapshot
from utils.repo_validate import validate_github_url

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("reposense")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=None)
CORS(app, resources={r"/*": {"origins": "*"}})


def _derive_phase(session: dict) -> str:
    status = (session.get("status") or "").lower()
    lifecycle = (session.get("lifecycle") or "").lower()
    progress = session.get("progress", 0) or 0

    if status == "completed":
        return "Finalizing report"
    if status == "failed":
        return "Execution interrupted"
    if lifecycle == "cloning":
        return "Cloning repository"
    if lifecycle == "analyzing" and progress < 55:
        return "Analyzing architecture"
    if lifecycle == "analyzing":
        return "Running AI agents"
    if lifecycle == "generating" and progress < 88:
        return "Generating recommendations"
    if lifecycle == "generating":
        return "Finalizing report"
    return "Preparing analysis"


def _active_agents(session: dict) -> list[dict]:
    active = []
    for name, data in (session.get("agents") or {}).items():
        state = data.get("state", "IDLE")
        if state in ("RUNNING", "THINKING", "WAITING"):
            active.append(
                {
                    "name": name,
                    "state": state,
                    "action": data.get("last_action", ""),
                }
            )
    return active


def _public_state(session: dict) -> dict:
    return {
        "status": session.get("status"),
        "lifecycle": session.get("lifecycle"),
        "progress": session.get("progress", 0),
        "phase": _derive_phase(session),
        "active_agents": _active_agents(session),
        "log_count": len(session.get("logs", [])),
        "agents": session.get("agents"),
        "github": session.get("github"),
        "contributors": session.get("contributors"),
        "summary": session.get("summary"),
        "graph": session.get("graph"),
        "findings": session.get("findings"),
        "fixes": session.get("fixes"),
        "approvals": session.get("approvals"),
        "impact": session.get("impact"),
        "code_quality": session.get("code_quality"),
        "maintainability": session.get("maintainability"),
        "structure": session.get("structure"),
        "recommendations": session.get("recommendations"),
        "readme": session.get("readme"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


@app.route("/")
def index():
    return send_from_directory(FRONTEND, "index.html")


@app.route("/style.css")
def style_css():
    return send_from_directory(FRONTEND, "style.css")


@app.route("/app.js")
def app_js():
    return send_from_directory(FRONTEND, "app.js")


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": "RepoSense",
            "gemini": bool(GEMINI_API_KEY),
            "openai": bool(OPENAI_API_KEY),
            "github_token": bool(GITHUB_TOKEN),
        }
    )


@app.route("/analyze", methods=["POST"])
def analyze():
    body = request.get_json(force=True, silent=True) or {}
    repo_url = (body.get("repo_url") or "").strip()
    mode = body.get("execution_mode", "autonomous")

    ok, err, normalized = validate_github_url(repo_url)
    if not ok:
        return jsonify({"error": err}), 400

    session_id = str(uuid.uuid4())[:8]
    snapshot.init_session(session_id, normalized, mode)
    log.info("Analysis started session=%s repo=%s", session_id, normalized)

    threading.Thread(
        target=run_analysis,
        args=(session_id, normalized, mode),
        daemon=True,
    ).start()

    return jsonify({"session_id": session_id, "status": "queued"}), 202


@app.route("/session/<session_id>")
def get_session_route(session_id):
    session = snapshot.get_session(session_id)
    if not session:
        return jsonify({"error": "session not found"}), 404
    payload = dict(session)
    payload["phase"] = _derive_phase(session)
    payload["active_agents"] = _active_agents(session)
    payload["log_count"] = len(session.get("logs", []))
    return jsonify(payload)


@app.route("/stream/<session_id>")
def stream(session_id):
    try:
        start_from_log = max(0, int(request.args.get("from_log", "0")))
    except ValueError:
        start_from_log = 0

    def generate():
        last_logs = start_from_log
        idle = 0
        max_idle = 1200

        yield "retry: 2000\n\n"

        while idle < max_idle:
            session = snapshot.get_session(session_id)
            if not session:
                yield f"data: {json.dumps({'type': 'error', 'data': {'message': 'session not found'}})}\n\n"
                return

            logs = session.get("logs", [])
            if len(logs) > last_logs:
                for entry in logs[last_logs:]:
                    yield f"data: {json.dumps({'type': 'log', 'data': entry})}\n\n"
                last_logs = len(logs)
                idle = 0

            yield f"data: {json.dumps({'type': 'state', 'data': _public_state(session)})}\n\n"

            if session.get("status") in ("completed", "failed"):
                yield f"data: {json.dumps({'type': 'done', 'data': {'status': session['status']}})}\n\n"
                return

            idle += 1
            yield ": keep-alive\n\n"
            time.sleep(0.5)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/approve", methods=["POST"])
@app.route("/approve_fix", methods=["POST"])
def approve_fix():
    body = request.get_json(force=True, silent=True) or {}
    sid = body.get("session_id")
    aid = body.get("approval_id")
    approved = bool(body.get("approved", False))
    result = resolve_approval(sid, aid, approved)
    if result.get("error"):
        return jsonify(result), 404
    return jsonify(result)


@app.route("/query", methods=["POST"])
@app.route("/chat", methods=["POST"])
def chat():
    body = request.get_json(force=True, silent=True) or {}
    sid = body.get("session_id")
    q = body.get("query") or body.get("message") or ""
    if not q.strip():
        return jsonify({"error": "query required"}), 400
    answer = answer_query(sid, q.strip())
    return jsonify({"answer": answer})


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = PORT
    log.info("RepoSense listening on http://%s:%s", host, port)
    app.run(host=host, port=port, threaded=True, debug=False)
