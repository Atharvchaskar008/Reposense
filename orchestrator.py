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
from utils.recommendations import build_recommendations
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


def _repo_name(repo_url: str, github: dict | None = None, slug: str = "") -> str:
    if github and github.get("full_name"):
        return github["full_name"]
    parts = [p for p in repo_url.rstrip("/").split("/") if p]
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1].replace('.git', '')}"
    return slug or repo_url


def _complexity_score(level: str, module_count: int) -> int:
    base = {"Low": 35, "Medium": 65, "High": 85}.get(level, 50)
    return min(100, max(10, base + min(module_count // 10, 10)))


def _security_insights(findings: list) -> list[str]:
    if not findings:
        return ["No critical patterns detected by heuristic scan."]
    insights = []
    for finding in findings[:3]:
        insights.append(
            f"{finding.get('severity', 'info').title()}: {finding.get('title', 'Issue found')} "
            f"at {finding.get('file', 'unknown file')}:{finding.get('line', '?')}"
        )
    return insights


def _ensure_summary_shape(
    summary: dict,
    recommendations: list,
    findings: list,
    maintainability: dict,
    code_quality: dict,
    metrics: dict,
) -> dict:
    safe = dict(summary or {})
    technologies = safe.get("technologies") or ["Unknown"]
    architecture = safe.get("architecture") or "Architecture overview unavailable."
    purpose = safe.get("purpose") or "Repository analysis completed with fallback data."
    complexity = safe.get("complexity") or "Unknown"

    safe.setdefault("repo_type", "General Software Project")
    safe["technologies"] = technologies
    safe["purpose"] = purpose
    safe["architecture"] = architecture
    safe["complexity"] = complexity
    safe["complexity_score"] = _complexity_score(complexity, metrics.get("node_count", 0))
    safe["repository_summary"] = purpose
    safe["tech_stack"] = technologies
    safe["architecture_overview"] = architecture
    safe["security_insights"] = _security_insights(findings)
    safe["maintainability_analysis"] = (maintainability.get("insights") or []) or [
        "Maintainability insights unavailable."
    ]
    safe["quality_score"] = code_quality.get("score", 0)
    safe["recommendations_preview"] = recommendations[:3]
    safe.setdefault("risk_level", "Low")
    safe.setdefault("risk_summary", "No critical patterns detected by heuristic scan.")
    safe.setdefault("source", "heuristic")
    return safe


def _fallback_dashboard(
    repo_url: str,
    github: dict | None = None,
    reason: str = "",
    findings: list | None = None,
) -> dict:
    github = dict(github or {})
    findings = findings or []
    repo_name = _repo_name(repo_url, github)
    github.setdefault("full_name", repo_name)
    github.setdefault("html_url", repo_url)
    github.setdefault("description", github.get("description") or "Repository metadata unavailable.")
    github.setdefault("languages", github.get("languages") or ["Unknown"])
    github.setdefault("stars", github.get("stars", 0))
    github.setdefault("forks", github.get("forks", 0))
    github.setdefault("open_issues", github.get("open_issues", 0))

    maintainability = {
        "score": 60,
        "grade": "C",
        "insights": [reason or "Analysis completed with limited upstream data."],
        "contributors_count": len(github.get("contributors", [])),
        "bus_factor_risk": len(github.get("contributors", [])) < 2,
    }
    code_quality = {
        "score": 50,
        "grade": "C",
        "insights": ["Code quality analysis unavailable; using fallback estimate."],
        "metrics": {
            "total_files": 0,
            "total_lines": 0,
            "avg_lines_per_file": 0,
            "large_file_count": 0,
        },
    }
    readme = {
        "found": False,
        "filename": "",
        "excerpt": "",
        "headings": [],
        "has_install_docs": False,
        "has_usage_docs": False,
    }
    structure = {
        "top_level_directories": [],
        "layout_pattern": "unknown",
        "top_level_files": 0,
    }
    summary = {
        "purpose": f"{repo_name} was analyzed with fallback heuristics because some live services were unavailable.",
        "repo_type": "General Software Project",
        "architecture": "Architecture overview unavailable without repository scan.",
        "technologies": github.get("languages") or ["Unknown"],
        "complexity": "Unknown",
        "risk_level": "Moderate" if findings else "Low",
        "risk_summary": reason or "Live analysis dependencies were unavailable.",
        "source": "fallback",
    }
    recommendations = build_recommendations(summary, findings, code_quality, readme, github)
    summary = _ensure_summary_shape(
        summary,
        recommendations,
        findings,
        maintainability,
        code_quality,
        {"node_count": 0, "edge_count": 0},
    )
    return {
        "github": github,
        "contributors": github.get("contributors", []),
        "summary": summary,
        "recommendations": recommendations[:8],
        "findings": findings,
        "fixes": [],
        "approvals": [],
        "impact": {"target": "", "affected": [], "human_readable": [], "blast_radius": 0},
        "code_quality": code_quality,
        "maintainability": maintainability,
        "structure": structure,
        "readme": readme,
        "graph": {"nodes": [], "edges": []},
    }


def _complete_with_fallback(
    session_id: str,
    repo_url: str,
    github: dict,
    reason: str,
    findings: list | None = None,
) -> None:
    snapshot.merge_session(session_id, _fallback_dashboard(repo_url, github, reason, findings))
    _log(session_id, reason, "warn", "MonitorAgent")
    _agent(session_id, "MonitorAgent", "COMPLETED", "Fallback dashboard ready")
    snapshot.finalize_session(session_id, "completed")


def run_analysis(session_id: str, repo_url: str, execution_mode: str = "autonomous") -> None:
    """Full analysis pipeline with lifecycle statuses."""
    github: dict = {}
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

        snapshot.set_lifecycle(session_id, "cloning", 18)
        _log(session_id, "Cloning repository...", agent="DependencyAgent")
        clone = clone_repo(repo_url)
        if not clone["success"]:
            _agent(session_id, "DependencyAgent", "FAILED", "Clone failed")
            _log(session_id, f"Clone failed: {clone.get('error', 'unknown')}", "error", "DependencyAgent")
            _complete_with_fallback(
                session_id,
                repo_url,
                github,
                "Repository clone failed; showing fallback dashboard data.",
            )
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
            _complete_with_fallback(
                session_id,
                repo_url,
                github,
                f"{size_msg}. Showing lightweight fallback dashboard instead.",
            )
            return

        snapshot.set_lifecycle(session_id, "analyzing", 30)
        structure = analyze_folder_structure(repo_path)
        snapshot.merge_session(session_id, {"structure": structure})
        _log(
            session_id,
            f"Layout: {structure.get('layout_pattern')} - {len(structure.get('top_level_directories', []))} top-level dirs",
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

        _agent(session_id, "SecurityAgent", "RUNNING", "Security scan")
        _log(session_id, "Running security pattern analysis...", agent="SecurityAgent")
        findings = scan_repository(repo_path)
        snapshot.merge_session(session_id, {"findings": findings})
        for finding in findings[:5]:
            _log(
                session_id,
                f"{finding['title']} in {finding['file']}:{finding['line']}",
                "warn" if finding.get("severity") in ("high", "medium") else "info",
                "SecurityAgent",
            )
        _agent(session_id, "SecurityAgent", "COMPLETED", f"{len(findings)} findings")
        snapshot.emit_progress(session_id, 55)

        _agent(session_id, "ImpactAgent", "RUNNING", "Impact analysis")
        target = "auth"
        for file_info in files:
            if "auth" in file_info["path"].lower():
                target = file_info["path"].replace(".py", "").replace("/", ".")
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

        readme = analyze_readme(repo_path)
        code_quality = analyze_code_quality(files, repo_path)
        maintainability = analyze_maintainability(github, files, findings)
        snapshot.merge_session(
            session_id,
            {"readme": readme, "code_quality": code_quality, "maintainability": maintainability},
        )
        for insight in (maintainability.get("insights") or [])[:3]:
            _log(session_id, insight, "info", "ExplanationAgent")

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
        if arch_text and _ != "heuristic":
            summary["architecture"] = arch_text.strip()[:500]

        rec_prompt = f"List 5 actionable engineering recommendations as bullet points.\n{ctx[:6000]}"
        rec_text, _ = llm_generate(rec_prompt)
        recommendations = []
        if rec_text and _ != "heuristic":
            for line in rec_text.split("\n"):
                line = line.strip().lstrip("â€¢-*0123456789. ")
                if len(line) > 12:
                    recommendations.append(line)
        if not recommendations:
            recommendations = _fallback_recommendations(findings, maintainability, readme)

        recommendations = build_recommendations(
            summary,
            findings,
            code_quality,
            readme,
            github,
        ) or recommendations
        summary = _ensure_summary_shape(
            summary,
            recommendations,
            findings,
            maintainability,
            code_quality,
            graph_data["metrics"],
        )

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
        _log(session_id, "Analysis complete - dashboard fully populated", agent="MonitorAgent")
        snapshot.finalize_session(session_id, "completed")

    except Exception as exc:
        _log(session_id, f"Orchestration error: {exc}", "error", "MonitorAgent")
        _complete_with_fallback(
            session_id,
            repo_url,
            github,
            f"Orchestration error: {exc}",
        )


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
    for approval in session.get("approvals", []):
        if approval.get("id") == approval_id:
            approval["approved"] = approved
            approval["status"] = "approved" if approved else "rejected"
            snapshot.merge_session(session_id, {"approvals": session["approvals"]})
            _log(
                session_id,
                f"Supervisor {'approved' if approved else 'rejected'} fix for {approval.get('file')}",
                "approval" if approved else "warn",
                "FixAgent",
            )
            _agent(session_id, "FixAgent", "COMPLETED", "Patch approved" if approved else "Rejected")
            return {"success": True, "approval": approval}
    return {"error": "approval not found"}
