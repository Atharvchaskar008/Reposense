"""
RepoSense production API — Flask + SSE + static frontend.
JacCloud-ready: PORT env, dotenv, CORS, real analysis via orchestrator.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv()

from config import PORT  # noqa: E402
from orchestrator import answer_query, resolve_approval, run_analysis  # noqa: E402
from utils import snapshot  # noqa: E402
from utils.repo_validate import validate_github_url  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("reposense")

BASE_DIR = Path(__file__).resolve().parent
FRONTEND = BASE_DIR / "frontend"

app = Flask(__name__, static_folder=None)
CORS(app, resources={r"/*": {"origins": "*"}})


def _public_state(session: dict) -> dict:
    return {
        "status": session.get("status"),
        "lifecycle": session.get("lifecycle"),
        "progress": session.get("progress", 0),
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
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
            "github_token": bool(os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_KEY")),
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
    return jsonify(session)


@app.route("/stream/<session_id>")
def stream(session_id):
    def generate():
        last_logs = 0
        idle = 0
        max_idle = 150

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
            time.sleep(0.35)

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
