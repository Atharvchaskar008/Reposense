# 🧠 RepoSense

**Autonomous Graph-Native Engineering Mission Control**

Live, AI-powered GitHub repository intelligence platform that orchestrates multiple specialized AI agents to clone, analyze, and generate actionable insights for any public GitHub repository—providing a comprehensive security, architecture, and code quality overview in seconds.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-production-green.svg)](https://flask.palletsprojects.com/)
[![JacLang](https://img.shields.io/badge/jaclang-orchestration-blueviolet)](https://github.com/Jaseci-Labs/jaclang)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📖 Overview

RepoSense exists to bridge the gap between static code analysis and true engineering understanding. Traditional tools just report syntax errors. RepoSense deploys a **Graph-Native Autonomous Agent Swarm** that builds a deep, spatial memory map of your repository, understanding how files import each other, where security vulnerabilities lie, and what the true blast radius of a change would be.

## ✨ Key Features

- **📊 Graph-Native Reasoning:** Maps codebases into spatial memory (nodes and edges), allowing agents to traverse relationships instead of just reading flat files.
- **🤖 Jac Orchestration:** Agent lifecycles and workflows are managed by Jac (Jaseci), utilizing Object-Spatial Programming for complex multi-agent coordination.
- **🛡️ Autonomous Repository Intelligence:** Deploys a fleet of specialized agents (Dependency, Security, Impact, Fix, Explanation) to independently analyze aspects of the project.
- **🛠️ Multi-Agent Workflows:** Agents discover tasks dynamically through the graph rather than rigid, linear scripts.
- **📈 Engineering Insights:** Generates architecture summaries, code quality scores, and maintainability grades.
- **💬 Repository Understanding:** A conversational AI UI lets you ask questions directly to the agents about the analyzed codebase.
- **⚡ Real-Time Analysis Pipeline:** Watch the autonomous agents think, scan, and make decisions via a live Server-Sent Events (SSE) mission control dashboard.

## 🏗️ Architecture Overview

RepoSense separates tooling from reasoning:

- **Frontend:** A sleek, glassmorphic UI built with Vanilla JS/CSS communicating via Server-Sent Events (SSE) to display live graph rendering and agent state.
- **Backend:** A robust Python/Flask layer (`server.py`) that acts as the HTTP transport and UI server.
- **Jac Layer:** The brains of the operation (`mission.jac`). It owns orchestration, agent lifecycles, graph memory, and task propagation.
- **Orchestration Flow:** Agents are spawned into a spatial graph. The DependencyAgent builds the initial code graph, which the SecurityAgent traverses. Tasks are generated natively within the graph and picked up by subsequent agents.
- **Graph Reasoning:** Uses Jac's walker paradigm. Agents traverse `FileNode`s and `RepoNode`s, generating `VulnerabilityNode`s and `TaskNode`s based on findings.
- **Intelligence Pipeline:** Dependencies → Code Quality → Security Scanning → Blast Radius Impact → Fix Generation → Human Approval.

## 🗺️ Workflow Architecture

<img width="1561" height="686" alt="image" src="https://github.com/user-attachments/assets/47097a09-ded5-4bab-80cc-bdf78422e4c1" />


*The workflow begins with a GitHub URL input. The system clones the repository, parses the AST to build a dependency graph, and then deploys Jac agents. The agents traverse the spatial graph, running LLM heuristics and static scans, eventually proposing fixes back to the UI.*

## ⚙️ How It Works

1. **Initialization:** The user submits a public GitHub URL to the Mission Control dashboard.
2. **Cloning & Parsing (DependencyAgent):** The repo is cloned locally. Python utilities parse the AST to extract imports and build the structural Graph Memory.
3. **Security Scan (SecurityAgent):** The agent walks the graph, detecting high-risk patterns and attaching `VulnerabilityNode`s to the relevant `FileNode`s.
4. **Blast Radius (ImpactAgent):** Traverses the graph to determine the impact of a vulnerability, finding all dependent modules.
5. **AI Synthesis (ExplanationAgent):** Consolidates findings, generating a repository summary, tech stack breakdown, and plain-English insights.
6. **Patch Generation (FixAgent):** AI generates actionable fixes for detected vulnerabilities, issuing `ApprovalNode`s that pause the workflow to wait for Human-in-the-Loop supervisor approval.

## 💻 Tech Stack

- **Frontend:** HTML5, Vanilla JavaScript, CSS3 (Glassmorphism design system)
- **Backend Framework:** Python 3.10+, Flask (SSE/Async capabilities)
- **AI / Agent Orchestration:** JacLang (Jaseci), OpenAI, Google Gemini
- **Code Parsing:** `ast` (Python), GitPython
- **Graph Visualization:** D3-style custom SVG graph renderer

## 📁 Project Structure

```text
├── .env                  # Environment variables (Keys & Config)
├── server.py             # Flask HTTP & SSE Transport Layer
├── orchestrator.py       # Python pipeline wrapper
├── main.jac / mission.jac# Jac agent orchestration logic
├── config.py             # Project configuration
├── requirements.txt      # Python dependencies
├── frontend/             # Static UI assets
│   ├── index.html        # Mission Control Dashboard
│   ├── style.css         # Styling and animations
│   └── app.js            # Live SSE consumer and graph logic
└── utils/                # Stateless Python utilities
    ├── code_quality.py   # Complexity & quality metrics
    ├── graph_builder.py  # AST & dependency mapping
    ├── repo_cloner.py    # GitHub repository cloning
    └── security_scanner.py # Heuristic vulnerability scanning
```

## 🛠️ Installation Guide

Follow these steps to set up the project for development and contribution.

### Prerequisites

- **Python 3.10+** (Ensure Python is added to your system PATH)
- **Git**
- Valid API Keys (GitHub Personal Access Token, OpenAI, Gemini)

### 1. Cloning the Repository

```bash
git clone <your-repo-url>
cd reposense
```

### 2. Environment Setup

It is highly recommended to use a virtual environment.

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Dependency Installation

```bash
pip install -r requirements.txt
```

### 4. Environment Variables

Create a `.env` file in the root directory (same level as `server.py`).

```env
GITHUB_TOKEN=your_github_token
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key

PORT=8000
LOW_COST_MODE=false
```

### 5. Running the Backend & Frontend

The Flask server handles both the backend API and the static frontend UI.

```bash
python server.py
```

*Note: The frontend must be accessed via `http://localhost:8000` (not `file://`) to enable Server-Sent Events (SSE) for the live dashboard.*

### 6. Jac Setup (Optional Direct Usage)

While `server.py` wraps the Jac execution, you can run the mission directly using Jac for testing:

```bash
# Windows
set SESSION_ID=demo& set REPO_URL=https://github.com/pallets/flask& jac run mission.jac

# Mac/Linux
SESSION_ID=demo REPO_URL=https://github.com/pallets/flask jac run mission.jac
```

### Troubleshooting

- **`python` not found:** Ensure Python 3.10+ is in your PATH, or use `py -3.11 server.py`.
- **No live updates:** Ensure you are accessing the app via `localhost` and not opening the HTML file directly.
- **Cloning fails:** Ensure the target repository is public and accessible.

## 🚀 Quick Start

If your environment is ready, start the application in one command:

```powershell
.\start.ps1
```
Then navigate to `http://localhost:8000`.

## 🤝 Contributing

We welcome contributions! To get started:

1. Fork the repository.
2. Create a new feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes with descriptive messages (`git commit -m 'feat: added amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

Please ensure your code passes standard linting (`flake8` / `black`) and doesn't break existing agent workflows in `mission.jac`.

## 🔮 Future Improvements

- [ ] **Multi-Language AST Parsing:** Expand beyond Python (JavaScript/TypeScript, Go, Rust).
- [ ] **Custom Agent Modules:** Allow users to define their own Jac agents and plug them into the swarm.
- [ ] **CI/CD Integration:** Package RepoSense as a GitHub Action.
- [ ] **Vector Memory:** Integrate Pinecone or ChromaDB for long-term project memory across multiple analysis runs.
n*

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
