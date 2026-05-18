"""Session snapshot persistence for SSE transport."""

import json
import threading
from datetime import datetime, timezone

from config import OUTPUTS_DIR

_lock = threading.Lock()


def _path(session_id: str):
    return OUTPUTS_DIR / f"{session_id}_live.json"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_session(session_id: str) -> dict:
    return {
        "id": session_id,
        "status": "queued",
        "lifecycle": "queued",
        "agents": {},
        "logs": [],
        "github": {},
        "graph": {"nodes": [], "edges": []},
        "findings": [],
        "fixes": [],
        "impact": {},
        "summary": {},
        "approvals": [],
        "code_quality": {},
        "recommendations": [],
        "readme": {},
        "maintainability": {},
        "structure": {},
        "contributors": [],
        "progress": 0,
        "created_at": _iso(),
        "updated_at": _iso(),
    }


def init_session(session_id: str, repo_url: str, execution_mode: str) -> None:
    with _lock:
        s = _default_session(session_id)
        s["repo_url"] = repo_url
        s["execution_mode"] = execution_mode
        _write_file(session_id, s)


def get_session(session_id: str) -> dict | None:
    with _lock:
        path = _path(session_id)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return None
    return None


def _read(session_id: str) -> dict:
    path = _path(session_id)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return _default_session(session_id)


def merge_session(session_id: str, patch: dict) -> None:
    with _lock:
        base = _read(session_id)
        for key, val in patch.items():
            if key == "agents" and isinstance(val, dict):
                base.setdefault("agents", {}).update(val)
            elif key == "logs" and isinstance(val, list):
                base.setdefault("logs", []).extend(val)
            else:
                base[key] = val
        base["updated_at"] = _iso()
        _write_file(session_id, base)


def set_lifecycle(session_id: str, lifecycle: str, progress: int | None = None) -> None:
    patch = {"lifecycle": lifecycle, "status": lifecycle}
    if progress is not None:
        patch["progress"] = progress
    merge_session(session_id, patch)


def emit_log(session_id: str, message: str, level: str = "info", agent: str = "") -> None:
    with _lock:
        base = _read(session_id)
        entry = {
            "ts": _ts(),
            "message": message,
            "level": level,
            "agent": agent,
            "display": f"[{_ts()}] {message}",
        }
        base.setdefault("logs", []).append(entry)
        base["updated_at"] = _iso()
        _write_file(session_id, base)


def emit_agent(session_id: str, name: str, state: str, last_action: str = "") -> None:
    merge_session(
        session_id,
        {"agents": {name: {"name": name, "state": state, "last_action": last_action}}},
    )


def emit_progress(session_id: str, percent: int) -> None:
    merge_session(session_id, {"progress": min(100, max(0, percent))})


def finalize_session(session_id: str, status: str) -> None:
    merge_session(session_id, {"status": status, "lifecycle": status, "progress": 100})


def _write_file(session_id: str, data: dict) -> None:
    path = _path(session_id)
    export = {k: v for k, v in data.items() if not str(k).startswith("_")}
    path.write_text(json.dumps(export, indent=2), encoding="utf-8")
