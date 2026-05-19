"""Centralized configuration - loads .env via python-dotenv."""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - defensive fallback for startup reliability
    def load_dotenv(*args, **kwargs):
        return False


BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
DOTENV_LOADED = load_dotenv(ENV_FILE, override=False)


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes")


def _env_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


REPOS_DIR = BASE_DIR / "repos"
OUTPUTS_DIR = BASE_DIR / "outputs"
REPOS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

PORT = _env_int("PORT", "8000")
DEFAULT_EXECUTION_MODE = os.getenv("EXECUTION_MODE", "autonomous")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_API_KEY", "")

_has_llm = bool(GEMINI_API_KEY or OPENAI_API_KEY)
LOW_COST_MODE = _env_flag("LOW_COST_MODE", "false" if _has_llm else "true")

USE_LOCAL_MODELS = _env_flag("USE_LOCAL_MODELS", "false")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "deepseek-coder")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

MODEL_CONFIG = {
    "fix_agent": os.getenv("FIX_AGENT_MODEL", "gemini-flash"),
    "explanation_agent": os.getenv("EXPLANATION_AGENT_MODEL", "gemini-flash"),
    "security_agent": os.getenv("SECURITY_AGENT_MODEL", "gemini-flash"),
    "impact_agent": os.getenv("IMPACT_AGENT_MODEL", "gemini-flash"),
}

MAX_REPO_FILES = _env_int("MAX_REPO_FILES", "8000")
CLONE_TIMEOUT_SEC = _env_int("CLONE_TIMEOUT_SEC", "120")
OPENAI_TIMEOUT_SEC = _env_int("OPENAI_TIMEOUT_SEC", "30")
GEMINI_TIMEOUT_SEC = _env_int("GEMINI_TIMEOUT_SEC", "30")
GITHUB_TIMEOUT_SEC = _env_int("GITHUB_TIMEOUT_SEC", "25")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

AGENT_IDS = [
    "DependencyAgent",
    "SecurityAgent",
    "ImpactAgent",
    "FixAgent",
    "MonitorAgent",
    "ExplanationAgent",
]
