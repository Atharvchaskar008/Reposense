"""Build dependency graph from parsed files using NetworkX."""

from pathlib import Path

import networkx as nx


def _module_key(path: str) -> str:
    return path.replace("\\", "/").replace(".py", "").replace("/", ".")


def _risk_for_path(path: str, findings: list | None) -> float:
    if not findings:
        return 0.0
    path_norm = path.replace("\\", "/").lower()
    score = 0.0
    for f in findings:
        fpath = (f.get("file") or "").replace("\\", "/").lower()
        if not fpath:
            continue
        if fpath in path_norm or path_norm.endswith(fpath):
            sev = (f.get("severity") or "").lower()
            score = max(score, {"high": 1.0, "medium": 0.6, "low": 0.3}.get(sev, 0.4))
    return score


def build_dependency_graph(
    files: list, repo_path: str, findings: list | None = None
) -> dict:
    """Create nodes/edges for visualization and impact analysis."""
    G = nx.DiGraph()
    path_to_module = {}

    for f in files:
        mod = _module_key(f["path"])
        path_to_module[f["path"]] = mod
        risk = _risk_for_path(f["path"], findings)
        G.add_node(
            mod,
            path=f["path"],
            imports=f.get("imports", []),
            risk_score=risk,
            has_issue=risk > 0,
        )

    root = Path(repo_path)
    for f in files:
        src_mod = _module_key(f["path"])
        src_dir = Path(f["path"]).parent

        for imp in f.get("imports", []):
            imp_base = imp.split(".")[0]
            for other in files:
                other_mod = _module_key(other["path"])
                other_name = Path(other["path"]).stem
                other_pkg = str(Path(other["path"]).parent).replace("\\", "/")

                matched = False
                if imp == other_mod or imp.endswith("." + other_name):
                    matched = True
                elif imp_base == other_name:
                    if src_dir == Path(other["path"]).parent or imp.startswith(
                        str(src_dir).replace("\\", ".")
                    ):
                        matched = True
                elif other_name in imp and other_pkg in imp.replace(".", "/"):
                    matched = True

                if matched and src_mod != other_mod:
                    G.add_edge(src_mod, other_mod, edge_type="imports_edge")

    nodes = [
        {
            "id": n,
            "path": G.nodes[n].get("path", n),
            "imports": G.nodes[n].get("imports", []),
            "risk_score": G.nodes[n].get("risk_score", 0),
            "has_issue": G.nodes[n].get("has_issue", False),
        }
        for n in G.nodes
    ]
    edges = [
        {"source": u, "target": v, "type": d.get("edge_type", "imports_edge")}
        for u, v, d in G.edges(data=True)
    ]

    return {
        "graph": G,
        "nodes": nodes,
        "edges": edges,
        "metrics": {
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
        },
    }


def impact_analysis(graph: nx.DiGraph, target_module: str) -> dict:
    """Compute blast radius for a module change."""
    if target_module not in graph:
        for n in graph.nodes:
            if target_module in n or n.endswith(target_module):
                target_module = n
                break

    if target_module not in graph:
        return {"target": target_module, "affected": [], "depth": 0}

    affected = set()
    for node in graph.nodes:
        if node == target_module:
            continue
        try:
            if nx.has_path(graph, node, target_module):
                affected.add(node)
        except nx.NetworkXError:
            pass

    try:
        downstream = nx.descendants(graph, target_module)
        affected.update(downstream)
    except nx.NetworkXError:
        pass

    human = []
    for mod in sorted(affected)[:12]:
        label = mod.split(".")[-1].replace("_", " ").title()
        human.append(label)

    return {
        "target": target_module,
        "affected": sorted(affected),
        "human_readable": human,
        "blast_radius": len(affected),
    }
