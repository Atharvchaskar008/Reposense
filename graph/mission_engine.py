"""
Graph-native autonomous mission engine (Jac OSP runtime).

Executes event-driven agent coordination via graph traversal.
Python utils are stateless tools only — no workflow state here beyond the graph.
"""

import uuid
from typing import Any

from config import AGENT_IDS
from graph.memory import GraphMemory
from utils import snapshot
from utils.code_quality import analyze_code_quality
from utils.github_api import fetch_contributors_count, fetch_repo_metadata, parse_github_url
from utils.graph_builder import build_dependency_graph, impact_analysis
from utils.llm_fixer import generate_fix
from utils.parser import scan_repo
from utils.readme_analyzer import analyze_readme
from utils.recommendations import build_recommendations
from utils.repo_cloner import clone_repo
from utils.security_scanner import scan_repository
from utils.summarizer import generate_summary


class MissionEngine:
    """Jac MissionController — graph-native orchestration."""

    def __init__(self, session_id: str, repo_url: str, execution_mode: str = "autonomous") -> None:
        self.session_id = session_id
        self.repo_url = repo_url
        self.mode = execution_mode
        self.graph = GraphMemory()
        self.repo_path = ""
        self.files: list = []
        self.graph_data: dict = {}
        self.findings: list = []
        self._nx = None

    def _log(self, msg: str, level: str = "info", agent: str = "") -> None:
        snapshot.emit_log(self.session_id, msg, level, agent)

    def _agent(self, name: str, state: str, action: str = "") -> None:
        snapshot.emit_agent(self.session_id, name, state, action)
        for n in self.graph.find("AgentNode", name=name):
            n.props["state"] = state
            n.props["last_action"] = action

    def _push_state(self, extra: dict | None = None) -> None:
        agents = {
            n.props["name"]: {
                "name": n.props["name"],
                "state": n.props.get("state", "IDLE"),
                "last_action": n.props.get("last_action", ""),
            }
            for n in self.graph.find("AgentNode")
        }
        for aid in AGENT_IDS:
            agents.setdefault(aid, {"name": aid, "state": "IDLE", "last_action": ""})

        patch: dict[str, Any] = {
            "agents": agents,
            "graph_memory": self.graph.export_snapshot(),
        }
        if extra:
            patch.update(extra)
        snapshot.merge_session(self.session_id, patch)

    def run(self) -> None:
        snapshot.init_session(self.session_id, self.repo_url, self.mode)
        self._log("RepoSense graph-native mission control online", agent="MonitorAgent")
        self._agent("MonitorAgent", "RUNNING", "Orchestrating autonomous agents")

        repo_node = self.graph.add(
            "RepoNode",
            repo_url=self.repo_url,
            repo_name="",
            status="initializing",
        )
        for name in AGENT_IDS:
            an = self.graph.add("AgentNode", name=name, state="IDLE", last_action="")
            self.graph.link("assigned_to", repo_node.id, an.id)

        snapshot.emit_progress(self.session_id, 5)
        self._push_state()

        self._run_dependency_agent(repo_node)
        if repo_node.props.get("status") == "failed":
            snapshot.finalize_session(self.session_id, "failed")
            return

        self._run_security_agent(repo_node)
        self._run_impact_agent()
        self._run_explanation_agent(repo_node)
        self._run_fix_agent()
        self._finalize(repo_node)

    def _run_dependency_agent(self, repo_node) -> None:
        self._agent("DependencyAgent", "RUNNING", "Cloning repository")
        self._log("[DependencyAgent] activated — discovering repository structure", agent="DependencyAgent")
        snapshot.emit_progress(self.session_id, 10)
        self._push_state()

        gh = fetch_repo_metadata(self.repo_url)
        parsed = parse_github_url(self.repo_url)
        if parsed:
            gh["contributors_count"] = fetch_contributors_count(*parsed)
        snapshot.merge_session(self.session_id, {"github": gh})
        repo_node.props["repo_name"] = gh.get("full_name", self.repo_url)
        self._log(
            f"[DependencyAgent] GitHub metadata: {gh.get('stars', 0)} stars, "
            f"{gh.get('forks', 0)} forks",
            agent="DependencyAgent",
        )

        clone = clone_repo(self.repo_url)
        if not clone["success"]:
            self._agent("DependencyAgent", "FAILED", "Clone failed")
            self._log(f"[DependencyAgent] clone error: {clone.get('error')}", "error", "DependencyAgent")
            repo_node.props["status"] = "failed"
            return

        self.repo_path = clone["path"]
        repo_node.props["status"] = "cloned"
        self._log(
            f"[DependencyAgent] repository cloned{' (cache)' if clone.get('cached') else ''}",
            agent="DependencyAgent",
        )

        self._agent("DependencyAgent", "THINKING", "Parsing Python modules")
        self.files = scan_repo(self.repo_path)
        self._log(f"[DependencyAgent] discovered {len(self.files)} Python files", agent="DependencyAgent")

        for f in self.files[:80]:
            fn = self.graph.add(
                "FileNode",
                path=f["path"],
                imports=f.get("imports", []),
                risk_score=0.0,
            )
            self.graph.link("discovered_by", fn.id, repo_node.id, agent="DependencyAgent")

        scan_task = self.graph.add(
            "TaskNode",
            task_type="security_scan",
            status="pending",
            assigned_agent="",
            priority="high",
            details="Scan all FileNodes",
        )
        self.graph.link("generated_task", repo_node.id, scan_task.id, reason="files_discovered")

        self._agent("DependencyAgent", "RUNNING", "Building dependency graph")
        self.graph_data = build_dependency_graph(self.files, self.repo_path)
        self._nx = self.graph_data.get("graph")
        self._log(
            f"[DependencyAgent] dependency graph: "
            f"{self.graph_data['metrics']['node_count']} nodes, "
            f"{self.graph_data['metrics']['edge_count']} edges",
            agent="DependencyAgent",
        )

        dep_graph = {
            "nodes": self.graph_data.get("nodes", []),
            "edges": self.graph_data.get("edges", []),
        }
        snapshot.merge_session(self.session_id, {"graph": dep_graph})
        snapshot.emit_progress(self.session_id, 35)
        self._agent("DependencyAgent", "COMPLETED", "Dependency graph ready")
        self._push_state()

    def _run_security_agent(self, repo_node) -> None:
        tasks = self.graph.pending_tasks("security_scan")
        if not tasks:
            return

        self._agent("SecurityAgent", "RUNNING", "Traversing FileNodes")
        self._log("[SecurityAgent] claiming security_scan task via graph traversal", agent="SecurityAgent")

        task = tasks[0]
        task.props["status"] = "claimed"
        task.props["assigned_agent"] = "SecurityAgent"

        file_nodes = self.graph.find("FileNode")
        self._log(f"[SecurityAgent] traversing {len(file_nodes)} FileNodes", agent="SecurityAgent")

        self.findings = scan_repository(self.repo_path)
        for f in self.findings:
            vuln = self.graph.add(
                "VulnerabilityNode",
                rule=f.get("rule"),
                severity=f.get("severity"),
                file=f.get("file"),
                line=f.get("line"),
                title=f.get("title"),
            )
            self.graph.link("generated_task", vuln.id, task.id, reason="detected")
            fix_task = self.graph.add(
                "TaskNode",
                task_type="generate_fix",
                status="pending",
                assigned_agent="",
                priority=f.get("severity", "medium"),
                details=f.get("id", ""),
                finding=f,
            )
            self.graph.link("generated_task", vuln.id, fix_task.id, reason="remediation")

        task.props["status"] = "completed"
        self._log(
            f"[SecurityAgent] identified {len(self.findings)} security pattern(s)",
            "warn" if self.findings else "info",
            "SecurityAgent",
        )
        for f in self.findings[:5]:
            self._log(
                f"[SecurityAgent] {f['title']} in {f['file']}:{f['line']}",
                "warn",
                "SecurityAgent",
            )

        snapshot.merge_session(self.session_id, {"findings": self.findings})
        snapshot.emit_progress(self.session_id, 55)
        self._agent("SecurityAgent", "COMPLETED", f"{len(self.findings)} findings")
        self._push_state()

    def _run_impact_agent(self) -> None:
        impact_tasks = self.graph.pending_tasks("impact_analysis")
        if not impact_tasks and self._nx:
            impact_tasks = [
                self.graph.add(
                    "TaskNode",
                    task_type="impact_analysis",
                    status="pending",
                    assigned_agent="",
                    priority="medium",
                    details="blast_radius",
                )
            ]

        self._agent("ImpactAgent", "RUNNING", "Analyzing dependency chains")
        self._log("[ImpactAgent] analyzing downstream dependency impact", agent="ImpactAgent")

        target = "auth"
        for f in self.files:
            if "auth" in f["path"].lower():
                target = f["path"].replace(".py", "").replace("/", ".")
                break

        impact = impact_analysis(self._nx, target) if self._nx else {}
        if impact.get("human_readable"):
            self._log(
                f"[ImpactAgent] changing {target} affects: "
                f"{', '.join(impact['human_readable'][:6])}",
                agent="ImpactAgent",
            )

        for t in impact_tasks:
            t.props["status"] = "completed"
            t.props["assigned_agent"] = "ImpactAgent"

        snapshot.merge_session(self.session_id, {"impact": impact})
        snapshot.emit_progress(self.session_id, 68)
        self._agent("ImpactAgent", "COMPLETED", "Impact map ready")
        self._push_state()

    def _run_explanation_agent(self, repo_node) -> None:
        self._agent("ExplanationAgent", "RUNNING", "Synthesizing system intelligence")
        self._log("[ExplanationAgent] generating architecture intelligence", agent="ExplanationAgent")

        readme = analyze_readme(self.repo_path)
        code_quality = analyze_code_quality(self.files, self.repo_path)
        summary = generate_summary(
            repo_node.props.get("repo_name", "repo"),
            self.repo_path,
            self.files,
            self.findings,
            self.graph_data.get("metrics", {}),
        )

        session = snapshot.get_session(self.session_id) or {}
        github = session.get("github", {})
        recommendations = build_recommendations(
            summary, self.findings, code_quality, readme, github
        )

        repo_node.props["summary"] = summary.get("purpose", "")
        repo_node.props["risk_level"] = summary.get("risk_level", "unknown")
        repo_node.props["status"] = "analyzed"

        snapshot.merge_session(
            self.session_id,
            {
                "summary": summary,
                "readme": readme,
                "code_quality": code_quality,
                "recommendations": recommendations,
            },
        )
        self._log(f"[ExplanationAgent] repo type: {summary.get('repo_type')}", agent="ExplanationAgent")
        snapshot.emit_progress(self.session_id, 82)
        self._agent("ExplanationAgent", "COMPLETED", "Intelligence report ready")
        self._push_state()

    def _run_fix_agent(self) -> None:
        fix_tasks = self.graph.pending_tasks("generate_fix")
        if not fix_tasks:
            self._agent("FixAgent", "COMPLETED", "No fixes required")
            return

        self._agent("FixAgent", "RUNNING", "Claiming remediation tasks")
        self._log(f"[FixAgent] claiming {len(fix_tasks)} task(s) from graph", agent="FixAgent")

        fixes = []
        approvals = []

        for task in fix_tasks[:3]:
            finding = task.props.get("finding") or {}
            task.props["status"] = "claimed"
            task.props["assigned_agent"] = "FixAgent"

            fix = generate_fix(finding)
            fixes.append({**fix, "title": finding.get("title", "Fix")})

            approval = self.graph.add(
                "ApprovalNode",
                question=finding.get("title", "Apply fix?"),
                requested_by="SecurityAgent",
                risk_level=finding.get("severity", "medium"),
                action_type="apply_patch",
                status="pending",
                file=finding.get("file", ""),
                line=finding.get("line", 0),
                recommendation=finding.get("recommendation", ""),
                fix_preview=fix.get("diff", ""),
            )
            self.graph.link("approval_request", task.id, approval.id, severity=finding.get("severity"))

            approval_ui = {
                "id": approval.id,
                "agent": "SecurityAgent",
                "question": approval.props["question"],
                "file": approval.props["file"],
                "line": approval.props["line"],
                "recommendation": approval.props["recommendation"],
                "fix_preview": approval.props["fix_preview"],
                "approved": None,
                "status": "pending",
            }

            if self.mode == "approval":
                self._agent("FixAgent", "REQUESTING_APPROVAL", finding.get("title", ""))
                self._log(
                    f"[FixAgent] approval required: {finding.get('title')}",
                    "approval",
                    "FixAgent",
                )
            else:
                approval.props["status"] = "approved"
                approval_ui["approved"] = True
                approval_ui["status"] = "auto_approved"
                self._log(f"[FixAgent] auto-approved patch for {finding.get('file')}", agent="FixAgent")

            approvals.append(approval_ui)
            task.props["status"] = "completed"

            self._log(
                f"[FixAgent] generated secure replacement patch for {finding.get('file')}",
                agent="FixAgent",
            )

        snapshot.merge_session(self.session_id, {"fixes": fixes, "approvals": approvals})
        snapshot.emit_progress(self.session_id, 95)

        if self.mode == "approval" and any(a["status"] == "pending" for a in approvals):
            self._agent("FixAgent", "WAITING", "Awaiting supervisor approval")
        else:
            self._agent("FixAgent", "COMPLETED", f"{len(fixes)} patches generated")
        self._push_state()

    def _finalize(self, repo_node) -> None:
        repo_node.props["status"] = "complete"
        self._agent("MonitorAgent", "COMPLETED", "Mission complete")
        self._log("Autonomous execution complete — graph memory synchronized", agent="MonitorAgent")
        snapshot.finalize_session(self.session_id, "completed")
        self._push_state({"status": "completed"})


def run_mission(session_id: str, repo_url: str, execution_mode: str = "autonomous") -> None:
    """Entry point for graph-native mission (Jac brain)."""
    try:
        MissionEngine(session_id, repo_url, execution_mode).run()
    except Exception as exc:
        snapshot.emit_log(session_id, f"Mission error: {exc}", "error", "MonitorAgent")
        snapshot.emit_agent(session_id, "MonitorAgent", "FAILED", str(exc))
        snapshot.finalize_session(session_id, "failed")
