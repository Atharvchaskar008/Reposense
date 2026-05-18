"""RepoSense HTTP API — mission control backend."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from orchestrator import (
    answer_query,
    create_analysis,
    get_session,
    resolve_approval,
    run_analysis,
)

PORT = 8000


class RepoSenseHandler(BaseHTTPRequestHandler):
    def _serve_static(self, rel_path: str, content_type: str) -> None:
        from pathlib import Path

        file_path = Path(__file__).parent / rel_path
        if not file_path.exists():
            self._json(404, {"error": "not found"})
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self._cors()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._serve_static("frontend/index.html", "text/html")
            return
        if path.endswith(".css"):
            self._serve_static(f"frontend{path}", "text/css")
            return
        if path.endswith(".js"):
            self._serve_static(f"frontend{path}", "application/javascript")
            return

        if path == "/health":
            self._json(200, {"status": "ok", "service": "RepoSense"})
            return

        if path.startswith("/session/"):
            sid = path.split("/")[-1]
            session = get_session(sid)
            if not session:
                self._json(404, {"error": "session not found"})
                return
            export = {k: v for k, v in session.items() if not k.startswith("_")}
            self._json(200, export)
            return

        if path.startswith("/stream/"):
            sid = path.split("/")[-1]
            self._sse_stream(sid)
            return

        self._json(404, {"error": "not found"})

    def _sse_stream(self, session_id: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()

        last_count = 0
        for _ in range(120):
            session = get_session(session_id)
            if not session:
                self.wfile.write(b"data: {\"error\":\"no session\"}\n\n")
                break
            logs = session.get("logs", [])
            if len(logs) > last_count:
                for entry in logs[last_count:]:
                    payload = json.dumps({"type": "log", "data": entry})
                    self.wfile.write(f"data: {payload}\n\n".encode())
                last_count = len(logs)
            payload = json.dumps(
                {
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
            )
            self.wfile.write(f"data: {payload}\n\n".encode())
            self.wfile.flush()
            if session.get("status") in ("completed", "failed"):
                break
            time.sleep(0.5)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return

        path = urlparse(self.path).path

        if path == "/analyze":
            repo_url = body.get("repo_url", "")
            mode = body.get("execution_mode", "autonomous")
            if not repo_url:
                self._json(400, {"error": "repo_url required"})
                return
            sid = create_analysis(repo_url, mode)
            threading.Thread(target=run_analysis, args=(sid,), daemon=True).start()
            self._json(202, {"session_id": sid, "status": "started"})
            return

        if path == "/approve":
            sid = body.get("session_id")
            aid = body.get("approval_id")
            approved = body.get("approved", False)
            reason = body.get("reason", "")
            result = resolve_approval(sid, aid, approved, reason)
            self._json(200, result)
            return

        if path == "/query":
            sid = body.get("session_id")
            query = body.get("query", "")
            answer = answer_query(sid, query)
            self._json(200, {"answer": answer})
            return

        self._json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args) -> None:
        pass


def main() -> None:
    server = HTTPServer(("localhost", PORT), RepoSenseHandler)
    print(f"RepoSense API running at http://localhost:{PORT}")
    print("Endpoints: POST /analyze, GET /session/:id, GET /stream/:id")
    server.serve_forever()


if __name__ == "__main__":
    main()
