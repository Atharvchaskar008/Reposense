"""LLM-powered unified diff fixes for FixAgent."""

from __future__ import annotations

from config import LOW_COST_MODE
from utils.llm_client import complete


def _heuristic_fix(finding: dict) -> dict:
    hint = finding.get("patch_hint") or finding.get("recommendation", "")
    return {
        "file": finding.get("file"),
        "line": finding.get("line"),
        "title": finding.get("title"),
        "diff": hint or "Review and remediate manually.",
        "reasoning": finding.get("recommendation", "Heuristic security rule match."),
        "source": "heuristic",
    }


def generate_fix(finding: dict) -> dict:
    """Generate a unified diff patch for a security finding."""
    if LOW_COST_MODE:
        return _heuristic_fix(finding)

    snippet = (finding.get("snippet") or "")[:800]
    prompt = (
        f"Generate a minimal secure fix as a valid unified diff (---/+++/@@ format only).\n"
        f"Issue: {finding.get('title')}\n"
        f"File: {finding.get('file')}\n"
        f"Line: {finding.get('line')}\n"
        f"Recommendation: {finding.get('recommendation')}\n"
        f"Code snippet:\n{snippet}\n"
        "Output ONLY the diff block, no markdown fences."
    )

    result = complete(
        prompt,
        system=(
            "You are a security engineer. Output a concise unified diff that fixes the vulnerability. "
            "Do not include secrets or placeholder API keys."
        ),
        max_tokens=600,
        temperature=0.1,
        force_llm=True,
    )

    diff = result.get("text", "").strip()
    if diff.startswith("```"):
        diff = "\n".join(
            line for line in diff.splitlines() if not line.strip().startswith("```")
        ).strip()

    if diff and ("---" in diff or "+++" in diff):
        return {
            "file": finding.get("file"),
            "line": finding.get("line"),
            "title": finding.get("title"),
            "diff": diff,
            "reasoning": f"LLM-generated patch via {result.get('source', 'unknown')}.",
            "source": result.get("source", "llm"),
        }

    return _heuristic_fix(finding)
