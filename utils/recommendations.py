"""Generate improvement recommendations — combines heuristics + optional LLM."""

from config import LOW_COST_MODE
from utils.llm_client import generate as llm_generate


def build_recommendations(
    summary: dict,
    findings: list,
    code_quality: dict,
    readme: dict,
    github: dict,
) -> list:
    recs = []

    if findings:
        high = [f for f in findings if f.get("severity") == "high"]
        recs.append(
            f"Remediate {len(high)} high-severity security pattern(s) before next release."
            if high
            else f"Review {len(findings)} security pattern(s) flagged by static analysis."
        )

    if not readme.get("has_install_docs"):
        recs.append("Add clear installation steps to README for onboarding.")
    if not readme.get("has_usage_docs"):
        recs.append("Document usage examples in README to reduce contributor friction.")

    if code_quality.get("score", 100) < 70:
        recs.append("Refactor oversized modules to improve maintainability and testability.")

    if github.get("open_issues", 0) > 50:
        recs.append("Triage open issues and label critical security or reliability items.")

    if summary.get("complexity") == "High":
        recs.append("Introduce architecture decision records (ADRs) for cross-module changes.")

    if not recs:
        recs.append("Maintain current modular structure; schedule periodic dependency audits.")

    if not LOW_COST_MODE and len(recs) < 5:
        prompt = (
            f"List 3 actionable engineering recommendations for repo {github.get('full_name')}.\n"
            f"Type: {summary.get('repo_type')}\nFindings: {len(findings)}\n"
            f"Quality grade: {code_quality.get('grade')}"
        )
        llm, _ = llm_generate(prompt)
        if llm:
            for line in llm.strip().split("\n"):
                line = line.strip().lstrip("0123456789.-) ")
                if line and len(line) > 10:
                    recs.append(line)

    return recs[:8]
