"""GitHub REST API - stateless metadata fetch."""

from __future__ import annotations

import logging
import re
from typing import Any

import requests

from config import GITHUB_TIMEOUT_SEC, GITHUB_TOKEN

log = logging.getLogger("reposense.github")

_SESSION = requests.Session()
if GITHUB_TOKEN:
    _SESSION.headers.update(
        {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "RepoSense/1.0",
        }
    )
else:
    _SESSION.headers.update(
        {"Accept": "application/vnd.github+json", "User-Agent": "RepoSense/1.0"}
    )


def parse_github_url(url: str) -> tuple[str, str] | None:
    m = re.search(r"github\.com[/:]([^/]+)/([^/?#]+)", url)
    if m:
        return m.group(1), m.group(2).replace(".git", "")
    return None


def _get(url: str, timeout: int | None = None) -> Any:
    r = _SESSION.get(url, timeout=timeout or GITHUB_TIMEOUT_SEC)
    r.raise_for_status()
    return r.json()


def fetch_full_github_intel(repo_url: str) -> dict:
    """Fetch comprehensive repository metadata."""
    parsed = parse_github_url(repo_url)
    if not parsed:
        return {"error": "invalid GitHub URL", "full_name": repo_url}

    owner, repo = parsed
    base = f"https://api.github.com/repos/{owner}/{repo}"
    result: dict = {"full_name": f"{owner}/{repo}"}

    try:
        data = _get(base)
    except requests.HTTPError as exc:
        log.warning("GitHub API HTTP error for %s: %s", repo_url, exc)
        return {"error": f"GitHub API {exc.response.status_code}", "full_name": f"{owner}/{repo}"}
    except requests.RequestException as exc:
        log.warning("GitHub API request failed for %s: %s", repo_url, exc)
        return {"error": f"GitHub API unavailable: {exc}", "full_name": f"{owner}/{repo}"}
    except Exception as exc:
        log.exception("Unexpected GitHub API failure for %s", repo_url)
        return {"error": str(exc), "full_name": f"{owner}/{repo}"}

    result.update(
        {
            "name": data.get("name", repo),
            "description": data.get("description") or "",
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "watchers": data.get("subscribers_count", 0),
            "language": data.get("language") or "Unknown",
            "topics": data.get("topics", []),
            "default_branch": data.get("default_branch", "main"),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "pushed_at": data.get("pushed_at", ""),
            "license": (data.get("license") or {}).get("spdx_id", "None"),
            "size_kb": data.get("size", 0),
            "html_url": data.get("html_url", repo_url),
        }
    )

    try:
        langs = _get(f"{base}/languages")
        result["languages"] = sorted(langs.keys(), key=lambda k: langs[k], reverse=True)
        if not result.get("language") or result["language"] == "Unknown":
            result["language"] = result["languages"][0] if result["languages"] else "Unknown"
    except Exception as exc:
        log.info("GitHub languages fetch failed for %s: %s", repo_url, exc)
        result["languages"] = []

    try:
        contributors = _get(f"{base}/contributors?per_page=10")
        result["contributors"] = [
            {
                "login": c.get("login"),
                "contributions": c.get("contributions", 0),
                "avatar_url": c.get("avatar_url"),
            }
            for c in contributors[:10]
        ]
        result["contributors_count"] = len(contributors)
    except Exception as exc:
        log.info("GitHub contributors fetch failed for %s: %s", repo_url, exc)
        result["contributors"] = []
        result["contributors_count"] = 0

    try:
        commits = _get(f"{base}/commits?per_page=5")
        result["recent_commits"] = [
            {
                "sha": c.get("sha", "")[:7],
                "message": (c.get("commit", {}).get("message") or "")[:80],
                "author": (c.get("commit", {}).get("author", {}) or {}).get("name", ""),
                "date": (c.get("commit", {}).get("author", {}) or {}).get("date", ""),
            }
            for c in commits
        ]
    except Exception as exc:
        log.info("GitHub commits fetch failed for %s: %s", repo_url, exc)
        result["recent_commits"] = []

    try:
        prs = _get(f"{base}/pulls?state=open&per_page=5")
        result["open_pull_requests"] = len(prs)
        result["pull_requests_sample"] = [
            {"title": p.get("title"), "number": p.get("number")} for p in prs[:5]
        ]
    except Exception as exc:
        log.info("GitHub pull requests fetch failed for %s: %s", repo_url, exc)
        result["open_pull_requests"] = 0
        result["pull_requests_sample"] = []

    return result


def fetch_repo_metadata(repo_url: str) -> dict:
    return fetch_full_github_intel(repo_url)


def fetch_contributors_count(owner: str, repo: str) -> int:
    intel = fetch_full_github_intel(f"https://github.com/{owner}/{repo}")
    return intel.get("contributors_count", 0)
