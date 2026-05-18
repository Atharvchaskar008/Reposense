"""Build dependency graph from parsed files using NetworkX."""

from pathlib import Path

import networkx as nx


def _module_key(path: str) -> str:
    return path.replace("\\", "/").replace(".py", "").replace("/", ".")


def build_dependency_graph(files: list, repo_path: str) -> dict:
    """Create nodes/edges for visualization and impact analysis."""
    G = nx.DiGraph()
    path_to_module = {}

    for f in files:
        mod = _module_key(f["path"])
        path_to_module[f["path"]] = mod
        G.add_node(
            mod,
            path=f["path"],
            imports=f.get("imports", []),
            risk_score=0.0,
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
