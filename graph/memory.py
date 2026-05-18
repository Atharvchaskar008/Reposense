"""In-memory graph store — Jac graph memory mirror."""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class GraphNode:
    kind: str
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    props: dict = field(default_factory=dict)


@dataclass
class GraphEdge:
    kind: str
    source: str
    target: str
    props: dict = field(default_factory=dict)


class GraphMemory:
    """Living repository knowledge graph."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add(self, kind: str, **props: Any) -> GraphNode:
        node = GraphNode(kind=kind, props=dict(props))
        self.nodes[node.id] = node
        return node

    def link(self, kind: str, source: str, target: str, **props: Any) -> None:
        self.edges.append(GraphEdge(kind, source, target, dict(props)))

    def find(self, kind: str, **filters: Any) -> list[GraphNode]:
        out = []
        for n in self.nodes.values():
            if n.kind != kind:
                continue
            if all(n.props.get(k) == v for k, v in filters.items()):
                out.append(n)
        return out

    def pending_tasks(self, task_type: str | None = None) -> list[GraphNode]:
        tasks = self.find("TaskNode", status="pending")
        if task_type:
            tasks = [t for t in tasks if t.props.get("task_type") == task_type]
        return tasks

    def export_snapshot(self) -> dict:
        return {
            "nodes": [
                {"id": n.id, "kind": n.kind, **n.props} for n in self.nodes.values()
            ],
            "edges": [
                {"kind": e.kind, "source": e.source, "target": e.target, **e.props}
                for e in self.edges
            ],
        }
