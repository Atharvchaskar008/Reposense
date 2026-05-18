"""Heuristic security scanning — no LLM required."""

import re
from pathlib import Path

PATTERNS = [
    (
        "hardcoded_secret",
        "high",
        re.compile(
            r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]"
        ),
        "Hardcoded secret or API key detected",
        "Move secrets to environment variables or a secrets manager.",
    ),
    (
        "eval_usage",
        "high",
        re.compile(r"\beval\s*\("),
        "Dangerous eval() usage",
        "Replace eval() with ast.literal_eval() or structured parsing.",
    ),
    (
        "exec_usage",
        "high",
        re.compile(r"\bexec\s*\("),
        "Dangerous exec() usage",
        "Avoid dynamic code execution; use safe alternatives.",
    ),
    (
        "subprocess_shell",
        "medium",
        re.compile(r"subprocess\.(call|run|Popen)\s*\([^)]*shell\s*=\s*True"),
        "Subprocess with shell=True",
        "Use shell=False and pass argument lists.",
    ),
    (
        "sql_injection",
        "high",
        re.compile(r"(?i)(execute|cursor\.execute)\s*\(\s*f?['\"].*%s"),
        "Potential SQL injection via string formatting",
        "Use parameterized queries with placeholders.",
    ),
    (
        "pickle_load",
        "medium",
        re.compile(r"pickle\.loads?\s*\("),
        "Unsafe pickle deserialization",
        "Avoid unpickling untrusted data.",
    ),
    (
        "dangerous_import",
        "low",
        re.compile(r"(?i)import\s+(pickle|marshal|xml\.etree)"),
        "Potentially dangerous import",
        "Review usage and restrict to trusted inputs.",
    ),
]

FIX_TEMPLATES = {
    "eval_usage": (
        "- eval(user_input)\n+ ast.literal_eval(user_input)  # only for literals"
    ),
    "hardcoded_secret": (
        "- API_KEY = \"sk-live-xxxxx\"\n+ API_KEY = os.environ.get(\"API_KEY\")"
    ),
    "subprocess_shell": (
        "- subprocess.run(cmd, shell=True)\n+ subprocess.run(cmd.split(), shell=False)"
    ),
    "sql_injection": (
        "- cursor.execute(f\"SELECT * FROM users WHERE id={uid}\")\n"
        "+ cursor.execute(\"SELECT * FROM users WHERE id=?\", (uid,))"
    ),
}


def scan_file(file_path: Path, rel_path: str) -> list:
    findings = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return findings

    lines = content.splitlines()
    for rule_id, severity, pattern, title, recommendation in PATTERNS:
        for i, line in enumerate(lines, 1):
            if pattern.search(line):
                findings.append(
                    {
                        "id": f"{rule_id}_{rel_path}_{i}",
                        "rule": rule_id,
                        "severity": severity,
                        "file": rel_path,
                        "line": i,
                        "title": title,
                        "snippet": line.strip()[:120],
                        "recommendation": recommendation,
                        "patch_hint": FIX_TEMPLATES.get(rule_id, ""),
                    }
                )
    return findings


def scan_repository(repo_path: str) -> list:
    root = Path(repo_path)
    all_findings = []
    skip = {".git", "__pycache__", "node_modules", ".venv", "venv"}

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".py", ".js", ".ts", ".env", ".yaml", ".yml", ".json"):
            continue
        if any(p in skip for p in path.parts):
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        all_findings.extend(scan_file(path, rel))

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    all_findings.sort(key=lambda x: severity_rank.get(x["severity"], 3))
    return all_findings
