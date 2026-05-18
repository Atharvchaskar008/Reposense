"""Clone GitHub repositories for analysis."""

import re
import subprocess
from pathlib import Path

from config import CLONE_TIMEOUT_SEC, REPOS_DIR


def _repo_slug(url: str) -> str:
    url = url.rstrip("/").replace(".git", "")
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+)", url)
    if match:
        return f"{match.group(1)}_{match.group(2)}"
    return re.sub(r"[^\w\-]", "_", url)[-80:]


def clone_repo(repo_url: str) -> dict:
    """Clone repository into repos/ and return metadata."""
    slug = _repo_slug(repo_url)
    target = REPOS_DIR / slug

    if target.exists() and any(target.iterdir()):
        return {
            "success": True,
            "path": str(target),
            "slug": slug,
            "cached": True,
        }

    target.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone", "--depth", "1", repo_url, str(target)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=CLONE_TIMEOUT_SEC)

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr or result.stdout,
            "path": "",
            "slug": slug,
        }

    return {
        "success": True,
        "path": str(target),
        "slug": slug,
        "cached": False,
    }
