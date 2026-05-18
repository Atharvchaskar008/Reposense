"""Clone any public GitHub repository for analysis."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from config import GIT_CLONE_TIMEOUT, REPOS_DIR

_GITHUB_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$",
    re.IGNORECASE,
)


def validate_github_url(repo_url: str) -> tuple[bool, str]:
    """Validate user-supplied GitHub URL."""
    url = (repo_url or "").strip().rstrip("/")
    if not url:
        return False, "Repository URL is required"
    if "github.com" not in url.lower():
        return False, "Only github.com URLs are supported"
    if not _GITHUB_RE.match(url.replace(".git", "")):
        return False, "Invalid GitHub URL — use https://github.com/owner/repo"
    return True, url.replace(".git", "")


def _repo_slug(url: str) -> str:
    match = _GITHUB_RE.match(url.replace(".git", ""))
    if match:
        return f"{match.group(1)}_{match.group(2)}"
    return re.sub(r"[^\w\-]", "_", url)[-80:]


def clone_repo(repo_url: str, *, timeout: int | None = None) -> dict:
    """Clone repository into repos/ and return metadata."""
    ok, normalized = validate_github_url(repo_url)
    if not ok:
        return {"success": False, "error": normalized, "path": "", "slug": ""}

    timeout = timeout if timeout is not None else GIT_CLONE_TIMEOUT
    slug = _repo_slug(normalized)
    target = REPOS_DIR / slug

    if target.exists():
        try:
            if any(target.iterdir()):
                return {
                    "success": True,
                    "path": str(target),
                    "slug": slug,
                    "cached": True,
                    "url": normalized,
                }
        except OSError:
            pass

    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)

    cmd = ["git", "clone", "--depth", "1", "--single-branch", normalized, str(target)]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(target, ignore_errors=True)
        return {
            "success": False,
            "error": f"Git clone timed out after {timeout}s — try a smaller repository",
            "path": "",
            "slug": slug,
            "url": normalized,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Git is not installed or not on PATH",
            "path": "",
            "slug": slug,
            "url": normalized,
        }

    if result.returncode != 0:
        shutil.rmtree(target, ignore_errors=True)
        err = (result.stderr or result.stdout or "clone failed").strip()[:500]
        if "not found" in err.lower() or "404" in err:
            err = "Repository not found — check owner/name and that it is public"
        elif "timeout" in err.lower():
            err = f"Clone timed out after {timeout}s"
        return {
            "success": False,
            "error": err,
            "path": "",
            "slug": slug,
            "url": normalized,
        }

    return {
        "success": True,
        "path": str(target),
        "slug": slug,
        "cached": False,
        "url": normalized,
    }
