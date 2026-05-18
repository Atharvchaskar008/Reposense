"""GitHub + OSV utilities — pure Python, no LLM calls."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

GITHUB_API = "https://api.github.com"
OSV_API = "https://api.osv.dev/v1/query"
MAX_FILE_CHARS = 2000
MAX_CVE_IDS = 3
MAX_ROOT_FILES = 30
MAX_DEPS = 20

DEP_FILES = {
    "requirements.txt",
    "package.json",
    "Gemfile",
    "go.mod",
    "pom.xml",
}

SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-]{16,}")),
    ("password", re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]{6,}")),
    ("token", re.compile(r"(?i)(access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-\.]{12,}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic_secret", re.compile(r"(?i)(secret|private[_-]?key)\s*[:=]\s*['\"]?[a-zA-Z0-9_\-/+=]{12,}")),
]


def _github_get(path: str) -> dict[str, Any]:
    req = urllib.request.Request(
        f"{GITHUB_API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "RepoSense-JacHacks",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _github_get_text(path: str) -> str:
    req = urllib.request.Request(
        f"{GITHUB_API}{path}",
        headers={
            "Accept": "application/vnd.github.raw",
            "User-Agent": "RepoSense-JacHacks",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode(errors="replace")[:MAX_FILE_CHARS]


def parse_repo_url(repo_url: str) -> tuple[str, str]:
    url = repo_url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.replace("https://github.com/", "").replace("http://github.com/", "")
    parts = parts.split("/")
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1]


def fetch_repo_metadata(owner: str, repo: str) -> dict[str, Any]:
    data = _github_get(f"/repos/{owner}/{repo}")
    return {
        "name": data.get("name", repo),
        "language": data.get("language") or "unknown",
        "stars": data.get("stargazers_count", 0),
        "description": (data.get("description") or "")[:200],
    }


def list_root_files(owner: str, repo: str) -> list[str]:
    contents = _github_get(f"/repos/{owner}/{repo}/contents/")
    names: list[str] = []
    for item in contents:
        if item.get("type") == "file":
            names.append(item.get("name", ""))
        if len(names) >= MAX_ROOT_FILES:
            break
    return names


def fetch_file_content(owner: str, repo: str, filepath: str) -> str:
    try:
        return _github_get_text(f"/repos/{owner}/{repo}/contents/{filepath}")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return ""


def parse_dependencies(content: str, filename: str) -> list[dict[str, str]]:
    if not content:
        return []

    deps: list[dict[str, str]] = []
    name = filename.lower()

    if name == "requirements.txt":
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            pkg = re.split(r"[<>=!~\[]", line)[0].strip()
            if pkg:
                deps.append({"name": pkg, "version": "", "ecosystem": "PyPI"})
    elif name == "package.json":
        try:
            data = json.loads(content)
            for section in ("dependencies", "devDependencies"):
                for pkg, ver in (data.get(section) or {}).items():
                    deps.append({"name": pkg, "version": str(ver), "ecosystem": "npm"})
        except json.JSONDecodeError:
            pass
    elif name == "gemfile":
        for line in content.splitlines():
            m = re.match(r'gem\s+["\']([^"\']+)["\']', line.strip())
            if m:
                deps.append({"name": m.group(1), "version": "", "ecosystem": "RubyGems"})
    elif name == "go.mod":
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("require ") and "(" not in line:
                parts = line.replace("require ", "").split()
                if parts:
                    deps.append(
                        {
                            "name": parts[0],
                            "version": parts[1] if len(parts) > 1 else "",
                            "ecosystem": "Go",
                        }
                    )
            elif line and not line.startswith(("module ", "go ", "require", "replace", "//")):
                parts = line.split()
                if len(parts) >= 2 and "." in parts[0]:
                    deps.append({"name": parts[0], "version": parts[1], "ecosystem": "Go"})
    elif name == "pom.xml":
        for m in re.finditer(
            r"<artifactId>([^<]+)</artifactId>\s*<version>([^<]+)</version>", content
        ):
            deps.append({"name": m.group(1), "version": m.group(2), "ecosystem": "Maven"})

    return deps[:MAX_DEPS]


def check_cve(package_name: str, ecosystem: str) -> dict[str, Any]:
    payload = json.dumps({"package": {"name": package_name, "ecosystem": ecosystem}}).encode()
    req = urllib.request.Request(
        OSV_API,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return {"vulnerable": False, "cve_ids": [], "count": 0}

    vulns = data.get("vulns") or []
    cve_ids: list[str] = []
    for v in vulns:
        for alias in v.get("aliases") or []:
            if alias.startswith("CVE-"):
                cve_ids.append(alias)
        if len(cve_ids) >= MAX_CVE_IDS:
            break
    cve_ids = list(dict.fromkeys(cve_ids))[:MAX_CVE_IDS]
    return {"vulnerable": bool(cve_ids), "cve_ids": cve_ids, "count": len(cve_ids)}


def scan_secrets_regex(content: str, filename: str) -> list[dict[str, Any]]:
    if not content:
        return []
    findings: list[dict[str, Any]] = []
    for secret_type, pattern in SECRET_PATTERNS:
        count = len(pattern.findall(content))
        if count:
            findings.append({"type": secret_type, "count": count, "file": filename})
    return findings


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def build_cve_llm_input(deps_with_cves: list[dict[str, Any]]) -> str:
    """Max ~200 tokens for LLM call 1."""
    parts: list[str] = []
    for d in deps_with_cves:
        cves = ",".join(d.get("cve_ids") or []) or "none"
        parts.append(f"{d.get('name', '?')}({d.get('ecosystem', '?')}):{cves}")
    text = "Rate HIGH/MEDIUM/LOW per package: " + "; ".join(parts) if parts else "No CVEs"
    return _truncate_to_tokens(text, 200)


def build_secret_llm_input(secret_types: list[str]) -> str:
    """Max ~100 tokens for LLM call 2."""
    text = "Secret types found: " + (", ".join(secret_types) if secret_types else "none")
    return _truncate_to_tokens(text, 100)


def get_risk_score_input(cve_findings: list[dict[str, Any]], secret_findings: list[dict[str, Any]]) -> str:
    """Structured summary under 300 tokens for LLM call 3."""
    high = sum(1 for f in cve_findings if str(f.get("llm_rating", "")).upper() == "HIGH")
    medium = sum(1 for f in cve_findings if str(f.get("llm_rating", "")).upper() == "MEDIUM")
    low = sum(1 for f in cve_findings if str(f.get("llm_rating", "")).upper() == "LOW")
    secret_count = len(secret_findings)
    pkg_count = len(cve_findings)
    text = (
        f"CVEs: {high} critical/high, {medium} medium, {low} low. "
        f"Secrets: {secret_count} types found. Packages: {pkg_count} scanned."
    )
    return _truncate_to_tokens(text, 300)


def apply_llm_cve_ratings(rating_text: str, deps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse LLM batch response into per-package llm_rating."""
    default = "MEDIUM" if any(d.get("cve_ids") for d in deps) else "LOW"
    ratings: dict[str, str] = {}
    for line in rating_text.replace("\n", ";").split(";"):
        line = line.strip()
        if not line:
            continue
        upper = line.upper()
        level = "LOW"
        if "HIGH" in upper:
            level = "HIGH"
        elif "MEDIUM" in upper:
            level = "MEDIUM"
        for d in deps:
            name = d.get("name", "")
            if name and name.lower() in line.lower():
                ratings[name] = level
    for d in deps:
        d["llm_rating"] = ratings.get(d.get("name", ""), default)
        d["severity"] = d["llm_rating"]
    return deps


def parse_report_llm_output(text: str) -> dict[str, Any]:
    """Extract risk_score and recommendations from LLM call 3 text."""
    risk_score = 50
    m = re.search(r"risk[_\s-]*score\s*[:=]?\s*(\d{1,3})", text, re.I)
    if m:
        risk_score = min(100, max(0, int(m.group(1))))
    else:
        m2 = re.search(r"\b(\d{1,3})\s*/\s*100\b", text)
        if m2:
            risk_score = min(100, max(0, int(m2.group(1))))

    recommendations: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^[\-\*\d]+[\.\)]\s+", line) or line.lower().startswith("recommend"):
            clean = re.sub(r"^[\-\*\d]+[\.\)]\s*", "", line)
            if len(clean) > 10:
                recommendations.append(clean[:200])
    if not recommendations:
        recommendations = [text[:200] if text else "Review dependencies and rotate exposed secrets."]

    return {
        "risk_score": risk_score,
        "summary": text[:500],
        "recommendations": recommendations[:5],
    }


def pick_secret_scan_files(root_files: list[str], owner: str, repo: str) -> list[str]:
    """Priority: main, auth, config — max 3 files."""
    candidates: list[str] = []
    patterns = [
        (r"^(main|app|index|server)\.(py|js|ts|go|rb)$", 0),
        (r"auth", 1),
        (r"(config|settings|\.env)", 2),
    ]
    scored: list[tuple[int, str]] = []
    for f in root_files:
        for pat, pri in patterns:
            if re.search(pat, f, re.I):
                scored.append((pri, f))
                break
    scored.sort(key=lambda x: x[0])
    for _, f in scored:
        if f not in candidates:
            candidates.append(f)
        if len(candidates) >= 3:
            break
    for f in root_files:
        if f.endswith((".py", ".js", ".ts", ".env", ".yaml", ".yml")) and f not in candidates:
            candidates.append(f)
        if len(candidates) >= 3:
            break
    return candidates[:3]


def save_report_json(path: str, report: dict[str, Any]) -> None:
    report["scanned_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)


def featherless_complete(prompt: str, max_tokens: int = 500) -> str:
    """LLM call for Jac scanner secret risk (delegates to unified client)."""
    try:
        from utils.llm_client import complete

        result = complete(
            prompt,
            system="You are a security analyst. Be concise. Never repeat secret values.",
            max_tokens=max_tokens,
            force_llm=True,
        )
        return result.get("text", "")
    except ImportError:
        return "Rotate any exposed credentials immediately."
