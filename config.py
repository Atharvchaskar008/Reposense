"""Centralized model and runtime configuration for RepoSense."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPOS_DIR = BASE_DIR / "repos"
OUTPUTS_DIR = BASE_DIR / "outputs"

REPOS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

# Execution modes: "autonomous" | "approval"
DEFAULT_EXECUTION_MODE = os.getenv("EXECUTION_MODE", "autonomous")

# Low-cost mode: only FixAgent uses LLM; others use heuristics
LOW_COST_MODE = os.getenv("LOW_COST_MODE", "true").lower() in ("1", "true", "yes")

USE_LOCAL_MODELS = os.getenv("USE_LOCAL_MODELS", "false").lower() in ("1", "true", "yes")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "deepseek-coder")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

MODEL_CONFIG = {
    "fix_agent": os.getenv("FIX_AGENT_MODEL", "claude-sonnet"),
    "explanation_agent": os.getenv("EXPLANATION_AGENT_MODEL", "gemini-flash"),
    "security_agent": os.getenv("SECURITY_AGENT_MODEL", "gemini-flash"),
    "impact_agent": os.getenv("IMPACT_AGENT_MODEL", "gemini-flash"),
}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

AGENT_IDS = [
    "DependencyAgent",
    "SecurityAgent",
    "ImpactAgent",
    "FixAgent",
    "MonitorAgent",
    "ExplanationAgent",
]
