"""Launch analysis via orchestrator (production path)."""

from orchestrator import run_analysis


def run(session_id: str, repo_url: str, execution_mode: str) -> None:
    run_analysis(session_id, repo_url, execution_mode)
