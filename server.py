"""RepoSense HTTP API — Flask mission control with SSE streaming."""

from __future__ import annotations

import json
import threading
import time

from flask import Flask, Response, jsonify, request, send_from_directory

from config import FRONTEND_DIR, HOST, PORT, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW
from orchestrator import (
    answer_query,
    create_analysis,
    get_session,
    resolve_approval,
    run_analysis,
)
from utils.rate_limiter import allow_request

app = Flask(__name__, static_folder=None)


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "127.0.0.1"


def _rate_limit() -> tuple[Response | None, str]:
    ok, msg = allow_request(
        _client_ip(),
        max_requests=RATE_LIMIT_MAX,
        window_seconds=RATE_LIMIT_WINDOW,
    )
    if ok:
        return None, ""
    return jsonify({"error": msg}), msg


@app.after_request
def cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/")
@app.route("/index.html")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/style.css")
def style_css():
    return send_from_directory(FRONTEND_DIR, "style.css")


@app.route("/app.js")
def app_js():
    return send_from_directory(FRONTEND_DIR, "app.js")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "RepoSense"})


@app.route("/session/<session_id>")
def session_state(session_id: str):
    session = get_session(session_id)
    if not session:
        return jsonify({"error": "session not found"}), 404
    export = {k: v for k, v in session.items() if not k.startswith("_")}
    return jsonify(export)


@app.route("/stream/<session_id>")
def stream(session_id: str):
    def generate():
        last_count = 0
        for _ in range(240):
            session = get_session(session_id)
            if not session:
                yield f"data: {json.dumps({'type': 'error', 'data': 'no session'})}\n\n"
                break

            logs = session.get("logs", [])
            if len(logs) > last_count:
                for entry in logs[last_count:]:
                    yield f"data: {json.dumps({'type': 'log', 'data': entry})}\n\n"
                last_count = len(logs)

            payload = {
                "type": "state",
                "data": {
                    "agents": session.get("agents"),
                    "status": session.get("status"),
                    "summary": session.get("summary"),
                    "graph": session.get("graph"),
                    "findings": session.get("findings"),
                    "fixes": session.get("fixes"),
                    "approvals": session.get("approvals"),
                    "impact": session.get("impact"),
                },
            }
            yield f"data: {json.dumps(payload)}\n\n"

            if session.get("status") in ("completed", "failed"):
                break
            time.sleep(0.5)

    return Response(generate(), mimetype="text/event-stream")


@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return "", 204

    blocked, _ = _rate_limit()
    if blocked:
        return blocked, 429

    body = request.get_json(silent=True) or {}
    repo_url = (body.get("repo_url") or "").strip()
    mode = body.get("execution_mode", "autonomous")

    if not repo_url:
        return jsonify({"error": "repo_url required"}), 400

    try:
        sid = create_analysis(repo_url, mode)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    threading.Thread(target=run_analysis, args=(sid,), daemon=True).start()
    return jsonify({"session_id": sid, "status": "started"}), 202


@app.route("/approve", methods=["POST", "OPTIONS"])
def approve():
    if request.method == "OPTIONS":
        return "", 204

    blocked, _ = _rate_limit()
    if blocked:
        return blocked, 429

    body = request.get_json(silent=True) or {}
    result = resolve_approval(
        body.get("session_id"),
        body.get("approval_id"),
        bool(body.get("approved", False)),
        body.get("reason", ""),
    )
    return jsonify(result)


@app.route("/query", methods=["POST", "OPTIONS"])
def query():
    if request.method == "OPTIONS":
        return "", 204

    blocked, _ = _rate_limit()
    if blocked:
        return blocked, 429

    body = request.get_json(silent=True) or {}
    answer = answer_query(body.get("session_id"), body.get("query", ""))
    return jsonify({"answer": answer})


def main() -> None:
    print(f"RepoSense API → http://{HOST}:{PORT}")
    print("Endpoints: POST /analyze, GET /session/:id, GET /stream/:id, POST /query")
    app.run(host=HOST, port=PORT, threaded=True)


if __name__ == "__main__":
    main()
