"""Python orchestration engine — powers live mission-control API."""

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import AGENT_IDS, OUTPUTS_DIR
from utils.graph_builder import build_dependency_graph, impact_analysis
from utils.llm_fixer import generate_fix
from utils.parser import scan_repo
from utils.repo_cloner import clone_repo
from utils.security_scanner import scan_repository
from utils.summarizer import generate_summary

_sessions: dict[str, dict] = {}


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(session: dict, message: str, level: str = "info") -> None:
    entry = {"ts": _ts(), "message": message, "level": level}
    session["logs"].append(entry)
    session["timeline"].append(entry)


def _set_agent(session: dict, name: str, state: str, action: str = "") -> None:
    session["agents"][name] = {
        "name": name,
        "state": state,
        "last_action": action,
        "updated_at": _ts(),
    }


def get_session(session_id: str) -> dict | None:
    return _sessions.get(session_id)


def create_analysis(repo_url: str, execution_mode: str = "autonomous") -> str:
    session_id = str(uuid.uuid4())[:8]
    _sessions[session_id] = {
        "id": session_id,
        "repo_url": repo_url,
        "execution_mode": execution_mode,
        "status": "running",
        "agents": {a: {"name": a, "state": "IDLE", "last_action": ""} for a in AGENT_IDS},
        "logs": [],
        "timeline": [],
        "graph": {"nodes": [], "edges": []},
        "findings": [],
        "fixes": [],
        "impact": {},
        "summary": {},
        "approvals": [],
        "repo_path": "",
        "repo_name": "",
    }
    return session_id


def run_analysis(session_id: str) -> None:
    session = _sessions.get(session_id)
    if not session:
        return

    mode = session["execution_mode"]
    url = session["repo_url"]

    try:
        _set_agent(session, "MonitorAgent", "RUNNING", "Orchestration online")
        _log(session, "RepoSense mission control activated")
        _log(session, f"Target repository: {url}")
        _log(session, f"Execution mode: {mode}")

        # DependencyAgent
        _set_agent(session, "DependencyAgent", "RUNNING", "Cloning repository")
        _log(session, "DependencyAgent activated")
        _log(session, "Cloning repository...")
        clone = clone_repo(url)
        if not clone["success"]:
            _set_agent(session, "DependencyAgent", "FAILED", "Clone failed")
            _log(session, f"Clone error: {clone.get('error', 'unknown')}", "error")
            session["status"] = "failed"
            return

        session["repo_path"] = clone["path"]
        session["repo_name"] = clone["slug"]
        _log(session, "Repository cloned" + (" (cached)" if clone.get("cached") else ""))

        _set_agent(session, "DependencyAgent", "THINKING", "Parsing Python files")
        _log(session, "Parsing Python files...")
        files = scan_repo(clone["path"])
        session["files"] = files
        _log(session, f"Discovered {len(files)} Python modules")

        _set_agent(session, "DependencyAgent", "RUNNING", "Building dependency graph")
        _log(session, "Building dependency graph...")
        graph_data = build_dependency_graph(files, clone["path"])
        session["graph"] = {"nodes": graph_data["nodes"], "edges": graph_data["edges"]}
        session["_nx_graph"] = graph_data["graph"]
        _log(
            session,
            f"Graph: {graph_data['metrics']['node_count']} nodes, "
            f"{graph_data['metrics']['edge_count']} edges",
        )
        _set_agent(session, "DependencyAgent", "COMPLETED", "Dependency graph ready")

        # Build graph memory nodes (JSON representation)
        session["graph_memory"] = {
            "repo": {
                "repo_name": clone["slug"],
                "repo_url": url,
                "status": "analyzing",
            },
            "files": [
                {
                    "path": f["path"],
                    "imports": f.get("imports", []),
                    "risk_score": 0,
                }
                for f in files[:100]
            ],
        }

        # SecurityAgent
        _set_agent(session, "SecurityAgent", "RUNNING", "Heuristic vulnerability scan")
        _log(session, "SecurityAgent activated")
        findings = scan_repository(clone["path"])
        session["findings"] = findings
        for f in findings[:5]:
            _log(
                session,
                f"Vulnerability detected: {f['title']} in {f['file']}:{f['line']}",
                "warn",
            )
        _set_agent(session, "SecurityAgent", "COMPLETED", f"{len(findings)} findings")

        # ImpactAgent
        _set_agent(session, "ImpactAgent", "RUNNING", "Blast radius analysis")
        _log(session, "ImpactAgent analyzing dependency chains...")
        target = "auth"
        for f in files:
            if "auth" in f["path"].lower():
                target = f["path"].replace(".py", "").replace("/", ".")
                break
        impact = impact_analysis(graph_data["graph"], target)
        session["impact"] = impact
        if impact.get("human_readable"):
            _log(session, f"Changing {target} affects: {', '.join(impact['human_readable'][:5])}")
        _set_agent(session, "ImpactAgent", "COMPLETED", "Impact map ready")

        # ExplanationAgent
        _set_agent(session, "ExplanationAgent", "RUNNING", "Repository intelligence")
        _log(session, "ExplanationAgent generating summary...")
        summary = generate_summary(
            clone["slug"], clone["path"], files, findings, graph_data["metrics"]
        )
        session["summary"] = summary
        session["graph_memory"]["repo"]["risk_level"] = summary.get("risk_level", "unknown")
        session["graph_memory"]["repo"]["summary"] = summary.get("purpose", "")
        _log(session, f"Repo type: {summary.get('repo_type', 'Unknown')}")
        _set_agent(session, "ExplanationAgent", "COMPLETED", "Summary ready")

        # FixAgent
        fixes = []
        approvals = []
        top_findings = [f for f in findings if f["severity"] in ("high", "medium")][:3]

        if top_findings:
            _set_agent(session, "FixAgent", "RUNNING", "Generating secure patches")
            _log(session, "FixAgent generating secure patch recommendations...")
            for finding in top_findings:
                fix = generate_fix(finding)
                fixes.append(fix)
                approval = {
                    "id": str(uuid.uuid4())[:8],
                    "agent": "SecurityAgent",
                    "question": finding["title"],
                    "file": finding["file"],
                    "line": finding["line"],
                    "recommendation": finding["recommendation"],
                    "fix_preview": fix.get("diff", ""),
                    "approved": None,
                    "status": "pending",
                }
                approvals.append(approval)
                if mode == "approval":
                    _set_agent(session, "FixAgent", "REQUESTING_APPROVAL", finding["title"])
                    _log(session, f"Approval required: {finding['title']}", "approval")
                else:
                    approval["approved"] = True
                    approval["status"] = "auto_approved"
                    _log(session, f"Auto-approved fix for {finding['file']}")

            if mode != "approval":
                _set_agent(session, "FixAgent", "COMPLETED", f"{len(fixes)} patches generated")
            else:
                _set_agent(session, "FixAgent", "WAITING", "Awaiting supervisor approval")
        else:
            _set_agent(session, "FixAgent", "COMPLETED", "No fixes required")
            _log(session, "No high-priority vulnerabilities for patch generation")

        session["fixes"] = fixes
        session["approvals"] = approvals

        # Persist output
        out_path = OUTPUTS_DIR / f"{session_id}_report.json"
        export = {
            k: v
            for k, v in session.items()
            if not k.startswith("_") and k != "files"
        }
        out_path.write_text(json.dumps(export, indent=2), encoding="utf-8")

        _set_agent(session, "MonitorAgent", "COMPLETED", "Mission complete")
        _log(session, "Analysis pipeline complete — supervisor review ready")
        session["status"] = "completed"

    except Exception as exc:
        _log(session, f"Orchestration error: {exc}", "error")
        session["status"] = "failed"
        _set_agent(session, "MonitorAgent", "FAILED", str(exc))


def resolve_approval(session_id: str, approval_id: str, approved: bool, reason: str = "") -> dict:
    session = _sessions.get(session_id)
    if not session:
        return {"error": "session not found"}

    for a in session["approvals"]:
        if a["id"] == approval_id:
            a["approved"] = approved
            a["status"] = "approved" if approved else "rejected"
            a["supervisor_note"] = reason
            if approved:
                _log(session, f"Supervisor approved fix for {a['file']}")
                _set_agent(session, "FixAgent", "COMPLETED", "Patch approved")
            else:
                _log(session, f"Supervisor rejected fix for {a['file']}", "warn")
                _set_agent(session, "FixAgent", "COMPLETED", "Patch rejected")
            return {"success": True, "approval": a}

    return {"error": "approval not found"}


def answer_query(session_id: str, query: str) -> str:
    session = _sessions.get(session_id)
    if not session:
        return "No active analysis session."

    q = query.lower()
    if "vulnerable" in q or "vulnerability" in q:
        if not session["findings"]:
            return "No vulnerabilities detected by heuristic scan."
        top = session["findings"][0]
        return (
            f"{top['title']} in {top['file']} line {top['line']}: "
            f"{top['recommendation']}"
        )
    if "depend" in q and "auth" in q:
        impact = session.get("impact", {})
        affected = impact.get("human_readable", [])
        return (
            f"Modules depending on auth chain: {', '.join(affected) or 'none detected'}."
        )
    if "risk" in q:
        high = [f for f in session["findings"] if f["severity"] == "high"]
        return f"Highest risk: {high[0]['file']} — {high[0]['title']}" if high else "Risk level is low."
    if "architecture" in q or "what is" in q:
        s = session.get("summary", {})
        return s.get("purpose", "Run an analysis first.")
    return (
        "Try: 'Why is this vulnerable?', 'What depends on auth.py?', "
        "'Show highest risk modules'"
    )
