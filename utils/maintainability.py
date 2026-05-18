"""Maintainability and contributor insights — stateless analysis."""

from datetime import datetime, timezone
from pathlib import Path


def analyze_maintainability(github: dict, files: list, findings: list) -> dict:
    score = 75
    insights = []

    stars = github.get("stars", 0)
    forks = github.get("forks", 0)
    issues = github.get("open_issues", 0)
    pushed = github.get("pushed_at", "")
    contributors = github.get("contributors_count", 0) or len(github.get("contributors", []))

    if contributors >= 5:
        score += 5
        insights.append(f"Healthy contributor base ({contributors} contributors).")
    elif contributors <= 1:
        score -= 10
        insights.append("Single-maintainer risk — consider expanding contributor pool.")

    if issues > 100:
        score -= 8
        insights.append(f"High open issue count ({issues}) — triage recommended.")
    elif issues == 0:
        insights.append("No open issues — active maintenance or low traffic.")

    if pushed:
        try:
            dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
            days = (datetime.now(timezone.utc) - dt).days
            if days > 365:
                score -= 15
                insights.append(f"Last push was {days} days ago — possible stale project.")
            elif days < 30:
                score += 5
                insights.append("Recently updated repository — active maintenance.")
        except ValueError:
            pass

    if len(findings) > 5:
        score -= 10
        insights.append("Multiple security patterns detected — prioritize remediation.")

    py_files = len(files)
    if py_files > 100:
        insights.append(f"Large codebase ({py_files} Python modules) — enforce modular boundaries.")

    score = max(20, min(98, score))
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"

    return {
        "score": score,
        "grade": grade,
        "insights": insights,
        "contributors_count": contributors,
        "bus_factor_risk": contributors < 2,
    }


def analyze_folder_structure(repo_path: str) -> dict:
    root = Path(repo_path)
    skip = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
    top_dirs = []
    file_count = 0

    for item in root.iterdir():
        if item.name in skip:
            continue
        if item.is_dir():
            top_dirs.append(item.name)
        elif item.is_file():
            file_count += 1

    layout = "flat"
    if "src" in top_dirs or "app" in top_dirs:
        layout = "src-layout"
    elif "packages" in top_dirs or "libs" in top_dirs:
        layout = "monorepo"
    elif len(top_dirs) > 6:
        layout = "multi-module"

    return {
        "top_level_directories": sorted(top_dirs)[:20],
        "layout_pattern": layout,
        "top_level_files": file_count,
    }
