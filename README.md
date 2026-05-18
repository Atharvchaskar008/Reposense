# RepoSense

**Graph-native multi-agent GitHub security mission control** — built with the [Jac ecosystem](https://jac-lang.org/) for JacHacks 2026.

RepoSense accepts **any public GitHub repository URL**, clones it dynamically, builds a dependency graph, runs security heuristics, generates LLM-powered fixes and Q&A, and streams live agent activity to a supervisor console.

## Features

| Capability | Description |
|------------|-------------|
| **Dynamic repos** | Paste any `https://github.com/owner/repo` — no hardcoded targets |
| **Primary LLM** | [Featherless AI](https://featherless.ai/) (OpenAI-compatible, DeepSeek-V3) |
| **Fallback chain** | Featherless → Gemini → OpenAI → heuristic |
| **Live SSE** | Real-time execution stream via Server-Sent Events |
| **Force graph** | Vanilla JS physics layout — **red nodes = security issues** |
| **Approval mode** | Supervisor approves/rejects FixAgent patches |
| **Smart Q&A** | Session-aware answers using scan context (not raw files) |
| **Jac CLI scanner** | Token-optimized `jac run main.jac <url>` (max 3 LLM calls) |

## Architecture

```
Supervisor (browser)
       │
       ▼
 Flask API (server.py) — SSE, rate limit, static UI
       │
       ├── orchestrator.py — agent pipeline
       ├── utils/llm_client.py — unified LLM
       └── Jac walkers (agents/*.jac) — graph-native scan
```

## Quick Start (Local)

### Prerequisites

- Python 3.10+
- Git on PATH
- [Jac](https://jac-lang.org/) (optional, for CLI scanner)

### 1. Install

```bash
git clone https://github.com/Atharvchaskar008/Reposense.git
cd Reposense
pip install -r requirements.txt
```

### 2. Configure Featherless API key

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
FEATHERLESS_API_KEY=your_featherless_key_here
LOW_COST_MODE=false
```

Get a key from [Featherless](https://featherless.ai/). The client uses:

- `FEATHERLESS_BASE_URL=https://api.featherless.ai/v1`
- `FEATHERLESS_MODEL=deepseek-ai/DeepSeek-V3-0324`

### 3. Run mission control

```bash
python server.py
```

Open **http://localhost:8000**

1. Paste a GitHub URL (e.g. `https://github.com/pallets/flask`)
2. Choose **Autonomous** or **Approval Required**
3. Watch agents, graph, patches, and ask questions in the Q&A bar

### 4. Run Jac CLI scanner (token-optimized)

```bash
jac run main.jac https://github.com/psf/requests
```

Report written to `outputs/report.json`.

## JacCloud Deployment

### Prepare

```bash
jac install
cp .env.example .env   # configure keys locally first
```

### Deploy with scale (Kubernetes)

```bash
jac start main.jac --scale
```

Production image build:

```bash
jac start main.jac --scale --build
```

### Environment variables on JacCloud dashboard

Set these in the JacCloud project settings (never commit real keys):

| Variable | Required | Description |
|----------|----------|-------------|
| `FEATHERLESS_API_KEY` | Yes (recommended) | Primary LLM |
| `FEATHERLESS_BASE_URL` | No | Default `https://api.featherless.ai/v1` |
| `FEATHERLESS_MODEL` | No | Default `deepseek-ai/DeepSeek-V3-0324` |
| `GEMINI_API_KEY` | No | Fallback LLM |
| `OPENAI_API_KEY` | No | Fallback LLM |
| `LOW_COST_MODE` | No | `false` for full LLM features |
| `GIT_CLONE_TIMEOUT` | No | Clone timeout seconds (default 180) |
| `RATE_LIMIT_MAX` | No | Max POST requests per IP per window (default 5) |

### Local Jac serve (API from walkers)

```bash
jac serve main.jac --host 0.0.0.0 --port 8000
```

Public walker `ScanRepo` is exposed for cloud HTTP triggers.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/analyze` | Start analysis `{ repo_url, execution_mode }` |
| `GET` | `/session/:id` | Full session state |
| `GET` | `/stream/:id` | SSE log + state stream |
| `POST` | `/approve` | Resolve approval |
| `POST` | `/query` | Smart Q&A with session context |
| `GET` | `/health` | Health check |

Rate limit: **5 POST requests per IP per 60 seconds** (configurable).

## Project Structure

```
├── main.jac              # CLI + JacCloud entry (ScanRepo walker)
├── jac.toml              # Project + serve + scale config
├── server.py             # Flask mission control API
├── orchestrator.py       # Multi-agent pipeline
├── config.py             # Environment configuration
├── agents/               # Jac walkers (graph_builder, security_scanner, …)
├── nodes/                # Graph memory nodes
├── utils/
│   ├── llm_client.py     # Featherless → Gemini → OpenAI → heuristic
│   ├── llm_fixer.py      # Unified diff patch generation
│   ├── github_tools.py   # GitHub API + OSV (Jac scanner)
│   ├── repo_cloner.py    # Dynamic git clone
│   └── rate_limiter.py   # IP rate limiting
├── frontend/             # Mission control UI
└── outputs/              # JSON reports
```

## Demo Flow (Judges)

1. Paste any public GitHub URL → agents activate with live SSE logs
2. Dependency graph animates — **red nodes** mark vulnerable modules
3. Security findings trigger FixAgent approval cards (approval mode)
4. Approve a patch → unified diff appears
5. Ask: *"Why is this vulnerable?"* → LLM answers from session context

## License

Hackathon prototype — MIT-friendly.
