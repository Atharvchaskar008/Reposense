# Graph-native repository memory nodes

node RepoNode {
    has repo_name: str = "",
        repo_url: str = "",
        status: str = "pending",
        risk_level: str = "unknown",
        summary: str = "";
}

node FileNode {
    has path: str = "",
        imports: list = [],
        vulnerabilities: list = [],
        risk_score: float = 0.0;
}

node AgentNode {
    has name: str = "",
        state: str = "IDLE",
        last_action: str = "";
}

edge imports_edge {
    has module_name: str = "";
}

edge depends_on {
    has strength: float = 1.0;
}

edge discovered_by {
    has timestamp: str = "";
}
