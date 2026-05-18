"""LLM-powered fix suggestions for FixAgent."""

import json
import os
import urllib.request

from config import (
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    LOW_COST_MODE,
    MODEL_CONFIG,
    OLLAMA_BASE_URL,
    OPENAI_API_KEY,
    USE_LOCAL_MODELS,
    LOCAL_MODEL,
)


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


def _ollama_fix(finding: dict, snippet: str) -> dict | None:
    prompt = (
        f"Generate a minimal secure code fix as a unified diff.\n"
        f"Issue: {finding.get('title')}\nFile: {finding.get('file')}\n"
        f"Line: {finding.get('line')}\nCode: {snippet}\n"
        f"Recommendation: {finding.get('recommendation')}"
    )
    try:
        body = json.dumps(
            {
                "model": LOCAL_MODEL,
                "prompt": prompt,
                "stream": False,
            }
        ).encode()
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        text = data.get("response", "")
        if text:
            return {
                "file": finding.get("file"),
                "line": finding.get("line"),
                "title": finding.get("title"),
                "diff": text,
                "reasoning": "Generated via local Ollama model.",
                "source": f"ollama:{LOCAL_MODEL}",
            }
    except Exception:
        return None
    return None


def generate_fix(finding: dict) -> dict:
    if LOW_COST_MODE and not USE_LOCAL_MODELS:
        return _heuristic_fix(finding)

    if USE_LOCAL_MODELS:
        fix = _ollama_fix(finding, finding.get("snippet", ""))
        if fix:
            return fix
        return _heuristic_fix(finding)

    # API-based fix — use heuristics unless keys present
    model = MODEL_CONFIG.get("fix_agent", "claude-sonnet")
    if model.startswith("claude") and ANTHROPIC_API_KEY:
        pass  # placeholder for Anthropic integration
    elif "gpt" in model and OPENAI_API_KEY:
        pass
    elif GEMINI_API_KEY:
        pass

    return _heuristic_fix(finding)
