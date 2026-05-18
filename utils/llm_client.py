"""Unified LLM client: Featherless → Gemini → OpenAI → heuristic fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from config import (
    FEATHERLESS_API_KEY,
    FEATHERLESS_BASE_URL,
    FEATHERLESS_MODEL,
    GEMINI_API_KEY,
    LOW_COST_MODE,
    OPENAI_API_KEY,
)


def _truncate(text: str, max_chars: int = 6000) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 20] + "\n...[truncated]"


def _featherless(prompt: str, system: str, max_tokens: int, temperature: float) -> str | None:
    if not FEATHERLESS_API_KEY:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=FEATHERLESS_API_KEY, base_url=FEATHERLESS_BASE_URL)
        resp = client.chat.completions.create(
            model=FEATHERLESS_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return None


def _gemini(prompt: str, system: str, max_tokens: int) -> str | None:
    if not GEMINI_API_KEY:
        return None
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    body = {
        "contents": [{"parts": [{"text": f"{system}\n\n{prompt}"}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2},
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode())
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = parts[0].get("text", "") if parts else ""
        return text.strip() or None
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, KeyError):
        return None


def _openai(prompt: str, system: str, max_tokens: int, temperature: float) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return None


def _heuristic(prompt: str, context: str = "") -> str:
    p = prompt.lower()
    if "unified diff" in p or "patch" in p or "fix" in p:
        return (
            "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,4 @@\n"
            "-SECRET = 'hardcoded'\n"
            "+import os\n"
            "+SECRET = os.environ.get('SECRET_KEY')\n"
        )
    if "risk" in p or "vulnerab" in p:
        return (
            "Based on the scan context: review high-severity findings first, "
            "rotate any exposed credentials, and pin dependency versions."
        )
    if context:
        return f"Analysis summary (offline mode): {context[:400]}"
    return "RepoSense is running in heuristic mode. Add FEATHERLESS_API_KEY for full LLM answers."


def complete(
    prompt: str,
    *,
    system: str = "You are RepoSense, a security-focused code analysis assistant. Be concise and actionable.",
    max_tokens: int = 800,
    temperature: float = 0.2,
    context: str = "",
    force_llm: bool = False,
) -> dict[str, Any]:
    """
    Return {"text": str, "source": str} using the first available provider.
    """
    prompt = _truncate(prompt)
    if context:
        prompt = f"Context:\n{_truncate(context, 3000)}\n\nQuestion/task:\n{prompt}"

    if not LOW_COST_MODE or force_llm:
        for name, fn in (
            ("featherless", lambda: _featherless(prompt, system, max_tokens, temperature)),
            ("gemini", lambda: _gemini(prompt, system, max_tokens)),
            ("openai", lambda: _openai(prompt, system, max_tokens, temperature)),
        ):
            text = fn()
            if text:
                return {"text": text, "source": name}

    return {"text": _heuristic(prompt, context), "source": "heuristic"}


def answer_with_session(query: str, session: dict) -> dict[str, Any]:
    """Smart Q&A using compact session context (no raw file dumps)."""
    findings = session.get("findings", [])[:8]
    summary = session.get("summary", {})
    impact = session.get("impact", {})
    graph = session.get("graph", {})

    finding_lines = [
        f"- {f.get('severity','?').upper()} {f.get('title')} ({f.get('file')}:{f.get('line')})"
        for f in findings
    ]
    ctx = (
        f"Repository: {session.get('repo_url', 'unknown')}\n"
        f"Status: {session.get('status', 'unknown')}\n"
        f"Purpose: {summary.get('purpose', summary.get('risk_summary', 'N/A'))}\n"
        f"Risk level: {summary.get('risk_level', 'unknown')}\n"
        f"Graph nodes: {len(graph.get('nodes', []))}, edges: {len(graph.get('edges', []))}\n"
        f"Impact target: {impact.get('target', 'N/A')}\n"
        f"Affected modules: {', '.join((impact.get('human_readable') or [])[:6])}\n"
        f"Findings ({len(findings)}):\n" + ("\n".join(finding_lines) or "  none")
    )

    result = complete(
        query,
        system=(
            "You are RepoSense mission control. Answer using ONLY the provided scan context. "
            "If data is missing, say so. Never invent CVE IDs or file paths."
        ),
        max_tokens=500,
        context=ctx,
        force_llm=bool(FEATHERLESS_API_KEY or GEMINI_API_KEY or OPENAI_API_KEY),
    )
    return result
