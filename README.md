# RepoSense

**Autonomous graph-native AI mission control for software engineering** — built with the Jac ecosystem.

RepoSense is not a chatbot. It is a supervisor console where intelligent agents collaboratively analyze a live codebase: clone, map dependencies, scan security, compute impact, propose fixes, and explain architecture — with real-time orchestration streaming.

## Architecture

```
User (Supervisor)
       │
       ▼
 Mission Control UI (HTML/CSS/JS)
       │
       ▼
 Python API Server (orchestrator.py)
       │
       ├── Jac Walkers (agents/*.jac) — graph-native agents
       ├── Graph Memory (nodes/*.jac) — RepoNode, FileNode, TaskNode...
       └── Python Utils — clone, AST, NetworkX, heuristics
```

| Agent | Role | LLM |
|-------|------|-----|
| DependencyAgent | Clone, parse, dependency graph | No |
| SecurityAgent | Heuristic vulnerability scan | Optional |
| ImpactAgent | Blast-radius analysis | Optional |
| FixAgent | Patch recommendations | Yes (primary) |
| MonitorAgent | Orchestration visibility | No |
| ExplanationAgent | Plain-English repo summary | Optional |

## Quick Start

### Prerequisites

- Python 3.10+
- Git (for cloning repositories)
- [Jac](https://jac-lang.org/) (optional, for running `.jac` walkers directly)

### Install

```bash
cd "Jachacks hackathon"
pip install -r requirements.txt
cp .env.example .env   # optional API keys
```

### Run Mission Control

```bash
python server.py
```

Open **http://localhost:8000** in your browser.

1. Paste a public GitHub URL (e.g. `https://github.com/pallets/flask`)
2. Choose **Autonomous** or **Approval Required**
3. Click **Start Analysis**
4. Watch agents activate, logs stream, graph form, and approvals appear

### Run Jac Orchestrator (optional)

```bash
jac run main.jac
```

## Project Structure

```
├── jac.toml
├── main.jac                 # RepoAnalyzer orchestrator
├── agents/                  # Jac walker agents
├── nodes/                   # Graph memory nodes & edges
├── utils/                   # Python: clone, AST, graph, security
├── frontend/                # Mission control UI
├── orchestrator.py          # Live analysis pipeline
├── server.py                # HTTP API + static UI
├── config.py                # Model routing & API keys
├── repos/                   # Cloned repositories
└── outputs/                 # Analysis reports (JSON)
```

## Demo Flow (for judges)

1. Paste GitHub repo URL → agents activate immediately
2. Live terminal stream shows clone → parse → graph → security
3. Repository Intelligence panel explains architecture in plain English
4. Security finding triggers FixAgent approval card
5. Supervisor clicks **Approve** → patch appears
6. System graph visualizes module dependencies
7. Secondary query bar: *"Why is this vulnerable?"*

## Configuration

See [LLM_AND_API_SETUP.md](LLM_AND_API_SETUP.md) for API keys, model choices, and low-cost mode.

Default **low-cost mode** runs without any API keys using deterministic heuristics.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Start analysis `{ repo_url, execution_mode }` |
| GET | `/session/:id` | Full session state |
| GET | `/stream/:id` | SSE stream (logs + state) |
| POST | `/approve` | Resolve approval request |
| POST | `/query` | Secondary Q&A |
| GET | `/health` | Health check |

## Development

See [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) for build phases and checklist.

## License

Hackathon prototype — MIT-friendly, use and extend freely.
