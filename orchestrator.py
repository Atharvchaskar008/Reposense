"""
RepoSense analysis orchestrator.

Coordinates real repository analysis, GitHub API, and LLM insights.
Delegates heavy lifting to stateless utils; persists state via snapshot.
"""

from __future__ import annotations

import json
import uuid

from config import AGENT_IDS, MAX_REPO_FILES
from utils import snapshot
from utils.code_quality import analyze_code_quality
from utils.github_api import fetch_full_github_intel
from utils.graph_builder import build_dependency_graph, impact_analysis
from utils.llm_client import chat as llm_chat
from utils.llm_client import generate as llm_generate
from utils.llm_fixer import generate_fix
from utils.maintainability import analyze_folder_structure, analyze_maintainability
from utils.parser import scan_repo
from utils.readme_analyzer import analyze_readme
from utils.repo_cloner import clone_repo
from utils.repo_validate import check_repo_size, validate_github_url
from utils.security_scanner import scan_repository
from utils.summarizer import _detect_stack, heuristic_summary


def _init_agents(session_id: str) -> None:
    for name in AGENT_IDS:
        snapshot.emit_agent(session_id, name, "IDLE", "Standing by")


def _log(session_id: str, msg: str, level: str = "info", agent: str = "") -> None:
    snapshot.emit_log(session_id, msg, level, agent)


def _agent(session_id: str, name: str, state: str, action: str = "") -> None:
    snapshot.emit_agent(session_id, name, state, action)


def run_analysis(session_id: str, repo_url: str, execution_mode: str = "autonomous") -> None:
    """Full analysis pipeline with lifecycle statuses."""
    try:
        ok, err, normalized = validate_github_url(repo_url)
        if not ok:
            _log(session_id, err, "error", "MonitorAgent")
            snapshot.finalize_session(session_id, "failed")
            return
        repo_url = normalized or repo_url

        _init_agents(session_id)
        _log(session_id, "Mission control online - analysis queued", agent="MonitorAgent")
        _agent(session_id, "MonitorAgent", "RUNNING", "Orchestrating pipeline")

        # --- GitHub metadata ---
        snapshot.set_lifecycle(session_id, "analyzing", 8)
        _agent(session_id, "DependencyAgent", "RUNNING", "Fetching GitHub metadata")
        _log(session_id, "Fetching repository metadata from GitHub API", agent="DependencyAgent")
        github = fetch_full_github_intel(repo_url)
        snapshot.merge_session(
            session_id,
            {
                "github": github,
                "contributors": github.get("contributors", []),
            },
        )
        if github.get("error"):
            _log(session_id, f"GitHub API warning: {github['error']}", "warn", "DependencyAgent")
        else:
            _log(
                session_id,
                f"Repository {github.get('full_name')} - {github.get('stars', 0)} stars, "
                f"{github.get('forks', 0)} forks",
                agent="DependencyAgent",
            )

        # --- Clone ---
        snapshot.set_lifecycle(session_id, "cloning", 18)
        _log(session_id, "Cloning repository...", agent="DependencyAgent")
        clone = clone_repo(repo_url)
        if not clone["success"]:
            _agent(session_id, "DependencyAgent", "FAILED", "Clone failed")
            _log(session_id, f"Clone failed: {clone.get('error', 'unknown')}", "error", "DependencyAgent")
            snapshot.finalize_session(session_id, "failed")
            return

        repo_path = clone["path"]
        _log(
            session_id,
            f"Repository cloned{' (cache hit)' if clone.get('cached') else ''}",
            agent="DependencyAgent",
        )

        size_ok, size_msg = check_repo_size(repo_path, MAX_REPO_FILES)
        if not size_ok:
            _log(session_id, size_msg, "error", "DependencyAgent")
            snapshot.finalize_session(session_id, "failed")
            return

        # --- Structure & parse ---
        snapshot.set_lifecycle(session_id, "analyzing", 30)
        structure = analyze_folder_structure(repo_path)
        snapshot.merge_session(session_id, {"structure": structure})
        _log(
            session_id,
            f"Layout: {structure.get('layout_pattern')} — {len(structure.get('top_level_directories', []))} top-level dirs",
            agent="DependencyAgent",
        )

        _agent(session_id, "DependencyAgent", "THINKING", "Parsing modules")
        files = scan_repo(repo_path)
        _log(session_id, f"Discovered {len(files)} Python modules", agent="DependencyAgent")

        graph_data = build_dependency_graph(files, repo_path)
        snapshot.merge_session(
            session_id,
            {
                "graph": {
                    "nodes": graph_data.get("nodes", []),
                    "edges": graph_data.get("edges", []),
                },
            },
        )
        _log(
            session_id,
            f"Dependency graph: {graph_data['metrics']['node_count']} nodes, "
            f"{graph_data['metrics']['edge_count']} edges",
            agent="DependencyAgent",
        )
        _agent(session_id, "DependencyAgent", "COMPLETED", "Dependency analysis complete")
        snapshot.emit_progress(session_id, 45)

        # --- Security ---
        _agent(session_id, "SecurityAgent", "RUNNING", "Security scan")
        _log(session_id, "Running security pattern analysis...", agent="SecurityAgent")
        findings = scan_repository(repo_path)
        snapshot.merge_session(session_id, {"findings": findings})
        for f in findings[:5]:
            _log(
                session_id,
                f"{f['title']} in {f['file']}:{f['line']}",
                "warn" if f.get("severity") in ("high", "medium") else "info",
                "SecurityAgent",
            )
        _agent(session_id, "SecurityAgent", "COMPLETED", f"{len(findings)} findings")
        snapshot.emit_progress(session_id, 55)

        # --- Impact ---
        _agent(session_id, "ImpactAgent", "RUNNING", "Impact analysis")
        target = "auth"
        for f in files:
            if "auth" in f["path"].lower():
                target = f["path"].replace(".py", "").replace("/", ".")
                break
        impact = impact_analysis(graph_data["graph"], target)
        snapshot.merge_session(session_id, {"impact": impact})
        if impact.get("human_readable"):
            _log(
                session_id,
                f"Blast radius for {target}: {', '.join(impact['human_readable'][:5])}",
                agent="ImpactAgent",
            )
        _agent(session_id, "ImpactAgent", "COMPLETED", "Impact map ready")
        snapshot.emit_progress(session_id, 62)

        # --- README & code quality ---
        readme = analyze_readme(repo_path)
        code_quality = analyze_code_quality(files, repo_path)
        maintainability = analyze_maintainability(github, files, findings)
        snapshot.merge_session(
            session_id,
            {"readme": readme, "code_quality": code_quality, "maintainability": maintainability},
        )
        for insight in (maintainability.get("insights") or [])[:3]:
            _log(session_id, insight, "info", "ExplanationAgent")

        # --- AI generation phase ---
        snapshot.set_lifecycle(session_id, "generating", 72)
        _agent(session_id, "ExplanationAgent", "RUNNING", "Generating AI insights")

        stack = _detect_stack(repo_path, files)
        summary = heuristic_summary(
            github.get("full_name", clone["slug"]),
            stack,
            findings,
            graph_data["metrics"],
        )

        ctx = _build_llm_context(github, files, findings, graph_data, readme, code_quality, maintainability)
        prompt_summary = (
            f"Write a 3-4 sentence repository intelligence summary for judges.\n"
            f"Repo: {github.get('full_name')}\nDescription: {github.get('description')}\n"
            f"Languages: {', '.join(github.get('languages', []))}\n"
            f"Type hint: {stack['repo_type']}\nSecurity findings: {len(findings)}\n"
            f"Modules: {len(files)}"
        )
        ai_summary, provider = llm_generate(prompt_summary)
        if ai_summary and provider != "heuristic":
            summary["purpose"] = ai_summary
            summary["source"] = provider
            _log(session_id, f"AI repository summary generated ({provider})", agent="ExplanationAgent")

        arch_prompt = (
            f"Explain the architecture of this repository in 2-3 sentences.\n"
            f"Layout: {structure.get('layout_pattern')}\n"
            f"Top dirs: {', '.join(structure.get('top_level_directories', [])[:8])}\n"
            f"Stack: {stack['repo_type']}"
        )
        arch_text, _ = llm_generate(arch_prompt)
        if arch_text:
            summary["architecture"] = arch_text.strip()[:500]

        rec_prompt = (
            f"List 5 actionable engineering recommendations as bullet points.\n{ctx[:6000]}"
        )
        rec_text, _ = llm_generate(rec_prompt)
        recommendations = []
        if rec_text:
            for line in rec_text.split("\n"):
                line = line.strip().lstrip("•-*0123456789. ")
                if len(line) > 12:
                    recommendations.append(line)
        if not recommendations:
            recommendations = _fallback_recommendations(findings, maintainability, readme)

        snapshot.merge_session(
            session_id,
            {
                "summary": summary,
                "recommendations": recommendations[:8],
            },
        )
        _log(session_id, f"Repo type: {summary.get('repo_type')}", agent="ExplanationAgent")
        _agent(session_id, "ExplanationAgent", "COMPLETED", "Intelligence report ready")
        snapshot.emit_progress(session_id, 88)

        # --- Fixes ---
        _agent(session_id, "FixAgent", "RUNNING", "Generating patches")
        fixes = []
        approvals = []
        for finding in [f for f in findings if f.get("severity") in ("high", "medium")][:3]:
            fix = generate_fix(finding)
            fixes.append({**fix, "title": finding.get("title", "Fix")})
            approval = {
                "id": uuid.uuid4().hex[:8],
                "agent": "SecurityAgent",
                "question": finding["title"],
                "file": finding["file"],
                "line": finding["line"],
                "recommendation": finding["recommendation"],
                "fix_preview": fix.get("diff", ""),
                "approved": None,
                "status": "pending",
            }
            if execution_mode == "approval":
                approvals.append(approval)
                _log(session_id, f"Approval required: {finding['title']}", "approval", "FixAgent")
            else:
                approval["approved"] = True
                approval["status"] = "auto_approved"
            _log(session_id, f"Patch generated for {finding['file']}", agent="FixAgent")

        snapshot.merge_session(session_id, {"fixes": fixes, "approvals": approvals})
        if execution_mode == "approval" and any(a["status"] == "pending" for a in approvals):
            _agent(session_id, "FixAgent", "WAITING", "Awaiting supervisor approval")
        else:
            _agent(session_id, "FixAgent", "COMPLETED", f"{len(fixes)} patches")

        _agent(session_id, "MonitorAgent", "COMPLETED", "Mission complete")
        _log(session_id, "Analysis complete — dashboard fully populated", agent="MonitorAgent")
        snapshot.finalize_session(session_id, "completed")

    except Exception as exc:
        _log(session_id, f"Orchestration error: {exc}", "error", "MonitorAgent")
        _agent(session_id, "MonitorAgent", "FAILED", str(exc))
        snapshot.finalize_session(session_id, "failed")


def _build_llm_context(github, files, findings, graph_data, readme, code_quality, maintainability) -> str:
    return json.dumps(
        {
            "github": {
                "full_name": github.get("full_name"),
                "stars": github.get("stars"),
                "description": github.get("description"),
            },
            "modules": len(files),
            "findings_count": len(findings),
            "graph_metrics": graph_data.get("metrics"),
            "readme_found": readme.get("found"),
            "code_quality_grade": code_quality.get("grade"),
            "maintainability_grade": maintainability.get("grade"),
        },
        indent=0,
    )[:8000]


def _fallback_recommendations(findings, maintainability, readme) -> list:
    recs = []
    if findings:
        recs.append("Address high-severity security patterns before next release.")
    recs.extend((maintainability.get("insights") or [])[:3])
    if not readme.get("has_install_docs"):
        recs.append("Add installation documentation to README.")
    if not recs:
        recs.append("Maintain modular architecture and schedule dependency audits.")
    return recs


def answer_query(session_id: str, query: str) -> str:
    session = snapshot.get_session(session_id)
    if not session:
        return "No active analysis session."
    ctx = json.dumps(
        {
            "repo": session.get("github", {}).get("full_name"),
            "summary": session.get("summary", {}),
            "findings": session.get("findings", [])[:5],
            "impact": session.get("impact", {}),
            "recommendations": session.get("recommendations", []),
        }
    )
    text, _ = llm_chat(ctx, query)
    return text


def resolve_approval(session_id: str, approval_id: str, approved: bool) -> dict:
    session = snapshot.get_session(session_id)
    if not session:
        return {"error": "session not found"}
    for a in session.get("approvals", []):
        if a.get("id") == approval_id:
            a["approved"] = approved
            a["status"] = "approved" if approved else "rejected"
            snapshot.merge_session(session_id, {"approvals": session["approvals"]})
            _log(
                session_id,
                f"Supervisor {'approved' if approved else 'rejected'} fix for {a.get('file')}",
                "approval" if approved else "warn",
                "FixAgent",
            )
            _agent(session_id, "FixAgent", "COMPLETED", "Patch approved" if approved else "Rejected")
            return {"success": True, "approval": a}
    return {"error": "approval not found"}
