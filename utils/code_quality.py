"""Code quality heuristics — stateless analysis tool."""

from pathlib import Path


def analyze_code_quality(files: list, repo_path: str) -> dict:
    if not files:
        return {
            "score": 0,
            "grade": "N/A",
            "insights": ["No Python files detected for quality analysis."],
            "metrics": {},
        }

    total_lines = sum(f.get("lines", 0) for f in files)
    large_files = [f for f in files if f.get("lines", 0) > 300]
    no_funcs = [f for f in files if not f.get("functions")]
    avg_lines = total_lines / max(len(files), 1)

    insights = []
    if large_files:
        insights.append(
            f"{len(large_files)} module(s) exceed 300 lines — consider splitting responsibilities."
        )
    if no_funcs and len(no_funcs) > len(files) * 0.3:
        insights.append("Several files lack function definitions — may be config/script heavy.")
    if avg_lines > 150:
        insights.append("High average file length — modularization could improve maintainability.")
    if not insights:
        insights.append("Module sizes and structure appear balanced for a project of this scale.")

    score = 85
    score -= min(30, len(large_files) * 5)
    score -= min(15, int(avg_lines / 50))
    score = max(35, min(98, score))

    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"

    return {
        "score": score,
        "grade": grade,
        "insights": insights,
        "metrics": {
            "total_files": len(files),
            "total_lines": total_lines,
            "avg_lines_per_file": round(avg_lines, 1),
            "large_file_count": len(large_files),
        },
    }
