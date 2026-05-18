"""GitHub URL validation and repository safety checks."""

import re
from pathlib import Path

GITHUB_RE = re.compile(
    r"^https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?$",
    re.IGNORECASE,
)


def validate_github_url(url: str) -> tuple[bool, str, str | None]:
    """Return (ok, message, normalized_url)."""
    url = (url or "").strip()
    if not url:
        return False, "Repository URL is required", None
    m = GITHUB_RE.match(url.rstrip("/").replace(".git", ""))
    if not m:
        return False, "Only public github.com URLs are supported", None
    owner, repo = m.group(1), m.group(2)
    if ".." in owner or ".." in repo:
        return False, "Invalid repository path", None
    normalized = f"https://github.com/{owner}/{repo}"
    return True, "", normalized


def check_repo_size(repo_path: str, max_files: int) -> tuple[bool, str]:
    """Prevent analyzing extremely large trees."""
    root = Path(repo_path).resolve()
    count = 0
    skip = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    for p in root.rglob("*"):
        if any(part in skip for part in p.parts):
            continue
        if p.is_file():
            count += 1
            if count > max_files:
                return False, f"Repository exceeds {max_files} files limit"
    return True, ""
