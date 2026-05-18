# RepoSense graph nodes — LLM only on llm_rating and summary

node RepoNode {
    has url: str = "",
        owner: str = "",
        repo_name: str = "",
        language: str = "",
        stars: int = 0;
}

node DependencyNode {
    has name: str = "",
        ecosystem: str = "",
        cve_ids: list = [],
        severity: str = "",
        llm_rating: str = "";
}

node SecretNode {
    has file_path: str = "",
        secret_type: str = "",
        risk_explanation: str = "";
}

node ReportNode {
    has risk_score: int = 0,
        summary: str = "",
        recommendations: list = [],
        total_issues: int = 0;
}
