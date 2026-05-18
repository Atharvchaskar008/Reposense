# RepoSense — autonomous multi-agent orchestrator

import from nodes.repo_nodes { RepoNode, FileNode, AgentNode }
import from nodes.task_nodes { TaskNode, ApprovalNode }
import from agents.dependency_agent { DependencyAgent }
import from agents.security_agent { SecurityAgent }
import from agents.impact_agent { ImpactAgent }
import from agents.fix_agent { FixAgent }
import from agents.monitor_agent { MonitorAgent }
import from agents.explanation_agent { ExplanationAgent }

walker RepoAnalyzer {
    has repo_url: str = "",
        execution_mode: str = "autonomous",
        repo_path: str = "",
        graph_data: dict = {},
        findings: list = [],
        files: list = [];

    can orchestrate with entry {
        report "RepoSense mission control online";

        repo = RepoNode(
            repo_url=self.repo_url,
            repo_name=self.repo_url,
            status="analyzing"
        );
        root ++> repo;

        dep_agent = AgentNode(name="DependencyAgent", state="RUNNING");
        root ++> dep_agent;

        dep_result = root spawn DependencyAgent(repo_url=self.repo_url);
        if dep_result.reports {
            self.graph_data = dep_result.reports[0];
            self.repo_path = dep_result.reports[0].get("path", "") if hasattr(dep_result.reports[0], "get") else "";
        }

        dep_agent.state = "COMPLETED";
        dep_agent.last_action = "Dependency graph built";

        sec_agent = AgentNode(name="SecurityAgent", state="RUNNING");
        repo ++> sec_agent;
        sec_result = repo spawn SecurityAgent(repo_path=self.repo_path);
        if sec_result.reports {
            self.findings = sec_result.reports[0];

        sec_agent.state = "COMPLETED";

        explain_agent = AgentNode(name="ExplanationAgent", state="RUNNING");
        repo ++> explain_agent;
        explain_result = repo spawn ExplanationAgent(
            repo_name=self.repo_url,
            repo_path=self.repo_path,
            files=self.files,
            findings=self.findings,
            metrics=self.graph_data.get("metrics", {}) if self.graph_data else {}
        );
        if explain_result.reports:
            repo.summary = str(explain_result.reports[0]);
            repo.risk_level = explain_result.reports[0].get("risk_level", "unknown") if hasattr(explain_result.reports[0], "get") else "unknown";

        explain_agent.state = "COMPLETED";
        repo.status = "complete";

        report {
            "status": "complete",
            "graph": self.graph_data,
            "findings": self.findings,
            "summary": explain_result.reports[0] if explain_result.reports else {}
        };
    }
}

with entry:__main__ {
    print("RepoSense — run via: jac main.jac or API server");
}
