"""README analysis — stateless filesystem tool."""

from pathlib import Path


def analyze_readme(repo_path: str) -> dict:
    root = Path(repo_path)
    candidates = ["README.md", "README.MD", "readme.md", "README.rst", "README"]

    for name in candidates:
        path = root / name
        if path.exists():
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            lines = text.splitlines()
            headings = [l.strip() for l in lines if l.startswith("#")]
            has_install = any(
                kw in text.lower() for kw in ("pip install", "npm install", "docker", "setup")
            )
            has_usage = any(kw in text.lower() for kw in ("usage", "getting started", "quick start"))
            return {
                "found": True,
                "filename": name,
                "lines": len(lines),
                "headings": headings[:8],
                "excerpt": "\n".join(lines[:12]).strip()[:600],
                "has_install_docs": has_install,
                "has_usage_docs": has_usage,
                "word_count": len(text.split()),
            }

    return {
        "found": False,
        "filename": "",
        "excerpt": "",
        "headings": [],
        "has_install_docs": False,
        "has_usage_docs": False,
    }
