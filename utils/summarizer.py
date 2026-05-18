"""Repository intelligence summaries — heuristics with optional LLM."""

import json
import os
import re
from pathlib import Path

from config import (
    ANTHROPIC_API_KEY,
    GEMINI_API_KEY,
    LOW_COST_MODE,
    MODEL_CONFIG,
    OPENAI_API_KEY,
)

STACK_SIGNALS = {
    "flask": ("Flask Backend API", "backend", ["Flask", "Python"]),
    "django": ("Django Monolithic Backend", "monolith", ["Django", "Python"]),
    "fastapi": ("FastAPI Backend Service", "microservice", ["FastAPI", "Python"]),
    "react": ("React Frontend Application", "spa", ["React", "JavaScript"]),
    "next": ("Next.js Full-Stack App", "fullstack", ["Next.js", "React"]),
    "tensorflow": ("Machine Learning Project", "ml", ["TensorFlow", "Python"]),
    "torch": ("Deep Learning Project", "ml", ["PyTorch", "Python"]),
    "express": ("Node.js API Service", "backend", ["Express", "Node.js"]),
    "jac": ("Jac Agent System", "agentic", ["Jac", "Jaseci"]),
    "streamlit": ("Data App / Dashboard", "data-app", ["Streamlit", "Python"]),
}


def _detect_stack(repo_path: str, files: list) -> dict:
    text_blob = ""
    root = Path(repo_path)
    for name in ("requirements.txt", "package.json", "pyproject.toml", "jac.toml"):
        p = root / name
        if p.exists():
            text_blob += p.read_text(encoding="utf-8", errors="ignore").lower()

    for f in files[:50]:
        text_blob += " ".join(f.get("imports", [])).lower()

    detected = []
    repo_type = "General Software Project"
    architecture = "Modular codebase"
    technologies = set()

    for key, (rtype, arch, techs) in STACK_SIGNALS.items():
        if key in text_blob:
            detected.append(key)
            repo_type = rtype
            architecture = {
                "backend": "Service-oriented backend",
                "monolith": "Monolithic layered backend",
                "microservice": "API-first microservice",
                "spa": "Single-page frontend",
                "fullstack": "Full-stack web application",
                "ml": "ML pipeline / experimentation",
                "agentic": "Graph-native agent system",
                "data-app": "Interactive data application",
            }.get(arch, architecture)
            technologies.update(techs)

    if "python" not in technologies and any(f["path"].endswith(".py") for f in files):
        technologies.add("Python")

    py_count = sum(1 for f in files if f["path"].endswith(".py"))
    complexity = "Low"
    if py_count > 80:
        complexity = "High"
    elif py_count > 25:
        complexity = "Medium"

    return {
        "repo_type": repo_type,
        "architecture": architecture,
        "technologies": sorted(technologies) or ["Unknown"],
        "complexity": complexity,
        "signals": detected,
    }


def heuristic_summary(repo_name: str, stack: dict, findings: list, metrics: dict) -> dict:
    high = sum(1 for f in findings if f.get("severity") == "high")
    risk = "Low"
    if high >= 3:
        risk = "High"
    elif high >= 1:
        risk = "Moderate"

    purpose = (
        f"This repository ({repo_name}) appears to be a {stack['repo_type'].lower()} "
        f"with {metrics.get('node_count', 0)} analyzed modules and "
        f"{metrics.get('edge_count', 0)} dependency relationships."
    )

    return {
        "purpose": purpose,
        "repo_type": stack["repo_type"],
        "architecture": stack["architecture"],
        "technologies": stack["technologies"],
        "complexity": stack["complexity"],
        "risk_level": risk,
        "risk_summary": (
            f"{len(findings)} security findings ({high} high severity)."
            if findings
            else "No critical patterns detected by heuristic scan."
        ),
        "source": "heuristic",
    }


def _call_gemini(prompt: str) -> str | None:
    if not GEMINI_API_KEY:
        return None
    try:
        import urllib.request

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.0-flash:generateContent?key="
            + GEMINI_API_KEY
        )
        body = json.dumps(
            {"contents": [{"parts": [{"text": prompt}]}]}
        ).encode()
        req = urllib.request.Request(
            url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return None


def generate_summary(
    repo_name: str,
    repo_path: str,
    files: list,
    findings: list,
    metrics: dict,
) -> dict:
    stack = _detect_stack(repo_path, files)
    base = heuristic_summary(repo_name, stack, findings, metrics)

    if LOW_COST_MODE or not GEMINI_API_KEY:
        return base

    if MODEL_CONFIG.get("explanation_agent") != "gemini-flash":
        return base

    prompt = (
        f"Summarize this codebase in 3 sentences for a hackathon judge.\n"
        f"Name: {repo_name}\nType: {stack['repo_type']}\n"
        f"Files: {len(files)}\nFindings: {len(findings)}\n"
        f"Technologies: {', '.join(stack['technologies'])}"
    )
    llm_text = _call_gemini(prompt)
    if llm_text:
        base["purpose"] = llm_text.strip()
        base["source"] = "gemini-flash"
    return base
