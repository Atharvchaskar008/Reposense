"""Centralized configuration for RepoSense."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
REPOS_DIR = BASE_DIR / "repos"
OUTPUTS_DIR = BASE_DIR / "outputs"
FRONTEND_DIR = BASE_DIR / "frontend"

REPOS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

DEFAULT_EXECUTION_MODE = os.getenv("EXECUTION_MODE", "autonomous")
LOW_COST_MODE = os.getenv("LOW_COST_MODE", "false").lower() in ("1", "true", "yes")
USE_LOCAL_MODELS = os.getenv("USE_LOCAL_MODELS", "false").lower() in ("1", "true", "yes")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "deepseek-coder")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

FEATHERLESS_API_KEY = os.getenv("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE_URL = os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1")
FEATHERLESS_MODEL = os.getenv("FEATHERLESS_MODEL", "deepseek-ai/DeepSeek-V3-0324")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
GIT_CLONE_TIMEOUT = int(os.getenv("GIT_CLONE_TIMEOUT", "180"))

MODEL_CONFIG = {
    "fix_agent": os.getenv("FIX_AGENT_MODEL", "featherless"),
    "explanation_agent": os.getenv("EXPLANATION_AGENT_MODEL", "featherless"),
    "security_agent": os.getenv("SECURITY_AGENT_MODEL", "featherless"),
    "impact_agent": os.getenv("IMPACT_AGENT_MODEL", "featherless"),
}

AGENT_IDS = [
    "DependencyAgent",
    "SecurityAgent",
    "ImpactAgent",
    "FixAgent",
    "MonitorAgent",
    "ExplanationAgent",
]
