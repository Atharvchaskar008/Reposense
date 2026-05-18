"""AST-based Python file parsing for imports and structure."""

import ast
from pathlib import Path


def parse_python_file(file_path: Path) -> dict:
    """Extract imports and basic metrics from a Python file."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, OSError):
        return {"path": str(file_path), "imports": [], "lines": 0, "functions": []}

    imports = []
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node.name)

    rel = file_path.as_posix()
    return {
        "path": rel,
        "imports": sorted(set(imports)),
        "lines": len(source.splitlines()),
        "functions": functions,
    }


def scan_repo(repo_path: str) -> list:
    """Parse all Python files in a repository."""
    root = Path(repo_path)
    files = []
    skip = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}

    for path in root.rglob("*.py"):
        if any(part in skip for part in path.parts):
            continue
        data = parse_python_file(path)
        try:
            data["path"] = str(path.relative_to(root)).replace("\\", "/")
        except ValueError:
            pass
        files.append(data)

    return files
