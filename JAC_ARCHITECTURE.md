# Jac Architecture — RepoSense

RepoSense is a **graph-native autonomous engineering intelligence platform** powered by Jac agents. Python is a **tooling layer only**; Jac owns orchestration, memory, and coordination.

## Responsibility Split

| Layer | Owns | Does NOT own |
|-------|------|----------------|
| **Jac (`mission.jac`, agents, nodes)** | Orchestration, graph memory, agent lifecycle, task propagation, approvals | Filesystem, AST, git, HTTP |
| **Graph engine (`graph/mission_engine.py`)** | OSP runtime executing Jac-defined graph protocol | Business UI, HTTP transport |
| **Python utils (`utils/*`)** | Clone, parse, scan, summarize (stateless JSON in/out) | Agent state, workflows |
| **Flask (`server.py`)** | HTTP, SSE transport, static UI | Analysis logic |
| **Frontend** | Mission control visualization | Reasoning |

## What Moved Into Jac

- Agent lifecycle (`IDLE` → `RUNNING` → `COMPLETED`, etc.)
- Task propagation via `TaskNode` / `VulnerabilityNode` / `ApprovalNode`
- Graph-native agent communication (tasks discovered by traversal, not `security_agent.run_fix()`)
- Repository knowledge graph (`RepoNode`, `FileNode`, edges)
- Approval workflows (FixAgent creates `ApprovalNode`, pauses in approval mode)
- Mission sequencing (Dependency → Security → Impact → Explanation → Fix)

## What Remains in Python (Tools Only)

- `repo_cloner.clone_repo(url)` → `{path, slug, success}`
- `parser.scan_repo(path)` → `[{path, imports, lines}]`
- `graph_builder.build_dependency_graph(files, path)` → `{nodes, edges, metrics}`
- `security_scanner.scan_repository(path)` → `[findings]`
- `github_api.fetch_repo_metadata(url)` → `{stars, forks, languages, ...}`
- `summarizer.generate_summary(...)` → `{repo_type, architecture, ...}`
- `snapshot.*` → transport-only session file writes for SSE

## Execution Flow

```
Frontend (EventSource SSE)
    ↓ POST /analyze
Flask server (transport)
    ↓ thread
bridge/run_mission.py
    ↓ prefers: jac run mission.jac
    ↓ fallback: graph/mission_engine.py (OSP runtime)
Jac MissionEngine
    ↓ calls tools
Python utils (stateless)
    ↓ results
Graph memory + snapshot.emit
    ↓
SSE → Live UI
```

## Graph-Native Communication Model

**Bad (old):** Python `orchestrator.run_analysis()` calls agents sequentially.

**Good (now):**

1. `DependencyAgent` creates `FileNode`s + `TaskNode(security_scan)`
2. `SecurityAgent` claims pending `security_scan` task, traverses `FileNode`s, creates `VulnerabilityNode`s + `TaskNode(generate_fix)`
3. `FixAgent` claims `generate_fix` tasks, creates `ApprovalNode`s
4. Supervisor approves via API → graph/session update

## Memory Architecture

All mission state lives in `GraphMemory` (nodes + edges) during execution. Snapshots are exported to `outputs/{session_id}_live.json` for SSE—this is **transport**, not the source of truth during the run.

Node types: `RepoNode`, `FileNode`, `VulnerabilityNode`, `AgentNode`, `TaskNode`, `ApprovalNode`

Edge types: `imports_edge`, `discovered_by`, `generated_task`, `approval_request`, `assigned_to`

## Why This Fits Jac

Jac is designed for **object-spatial programming**: walkers traverse graphs, discover work, and coordinate through relationships. RepoSense maps directly:

- Repositories → spatial memory
- Agents → walkers
- Tasks → nodes awaiting traversal
- Approvals → graph state gates

## Running

```bash
pip install -r requirements.txt
python server.py
# Open http://localhost:8000 (required for SSE; file:// will not stream)
```

Optional direct Jac:

```bash
set SESSION_ID=demo& set REPO_URL=https://github.com/pallets/flask& jac run mission.jac
```
