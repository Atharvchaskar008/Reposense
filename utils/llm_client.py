"""Unified LLM client — Gemini primary, OpenAI fallback, heuristic last."""

from __future__ import annotations

from config import GEMINI_API_KEY, LOW_COST_MODE, OPENAI_API_KEY

GEMINI_MODEL = "gemini-2.0-flash"
OPENAI_MODEL = "gpt-4o-mini"


def _heuristic(prompt: str) -> str:
    return (
        "Analysis based on repository structure and static scans. "
        "Enable GEMINI_API_KEY or OPENAI_API_KEY for richer AI insights."
    )


def generate(prompt: str, system: str = "") -> tuple[str, str]:
    """
    Generate text from prompt.
    Returns (text, provider) where provider is gemini|openai|heuristic.
    """
    if LOW_COST_MODE and not GEMINI_API_KEY and not OPENAI_API_KEY:
        return _heuristic(prompt), "heuristic"

    full_prompt = f"{system}\n\n{prompt}".strip() if system else prompt

    if GEMINI_API_KEY:
        text = _gemini(full_prompt)
        if text:
            return text, "gemini"

    if OPENAI_API_KEY:
        text = _openai(full_prompt, system)
        if text:
            return text, "openai"

    return _heuristic(prompt), "heuristic"


def chat(session_context: str, question: str) -> tuple[str, str]:
    """Session-aware Q&A over analysis context."""
    prompt = (
        f"You are RepoSense, an expert repository intelligence assistant.\n"
        f"Use ONLY the analysis context below. Be concise and specific.\n\n"
        f"CONTEXT:\n{session_context[:12000]}\n\n"
        f"QUESTION: {question}"
    )
    return generate(prompt, system="Answer in 2-5 sentences.")


def _gemini(prompt: str) -> str | None:
    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text.strip()
    except Exception:
        pass

    try:
        import json
        import urllib.request

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        )
        body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:
        return None


def _openai(prompt: str, system: str) -> str | None:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=2048,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None
