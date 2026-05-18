"""Centralized configuration — loads .env via python-dotenv."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

REPOS_DIR = BASE_DIR / "repos"
OUTPUTS_DIR = BASE_DIR / "outputs"
REPOS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

PORT = int(os.getenv("PORT", "8000"))
DEFAULT_EXECUTION_MODE = os.getenv("EXECUTION_MODE", "autonomous")

# Use LLMs when keys are present
_has_llm = bool(os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY"))
LOW_COST_MODE = os.getenv("LOW_COST_MODE", "false" if _has_llm else "true").lower() in (
    "1",
    "true",
    "yes",
)

USE_LOCAL_MODELS = os.getenv("USE_LOCAL_MODELS", "false").lower() in ("1", "true", "yes")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "deepseek-coder")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

MODEL_CONFIG = {
    "fix_agent": os.getenv("FIX_AGENT_MODEL", "gemini-flash"),
    "explanation_agent": os.getenv("EXPLANATION_AGENT_MODEL", "gemini-flash"),
    "security_agent": os.getenv("SECURITY_AGENT_MODEL", "gemini-flash"),
    "impact_agent": os.getenv("IMPACT_AGENT_MODEL", "gemini-flash"),
}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_KEY", "")

MAX_REPO_FILES = int(os.getenv("MAX_REPO_FILES", "8000"))
CLONE_TIMEOUT_SEC = int(os.getenv("CLONE_TIMEOUT_SEC", "120"))

AGENT_IDS = [
    "DependencyAgent",
    "SecurityAgent",
    "ImpactAgent",
    "FixAgent",
    "MonitorAgent",
    "ExplanationAgent",
]
