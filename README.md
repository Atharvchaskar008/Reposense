# RepoSense

Live AI-powered GitHub repository intelligence platform.

## Run locally (Windows)

### 1. Prerequisites

- **Python 3.10+** — [python.org](https://www.python.org/downloads/) (enable **Add Python to PATH**)
- **Git** — [git-scm.com](https://git-scm.com/download/win)

Verify in PowerShell:

```powershell
python --version
git --version
```

### 2. Go to the project folder

```powershell
cd "C:\Users\athar\OneDrive\Desktop\Jachacks hackathon"
```

### 3. Virtual environment (recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If activation fails:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

### 5. Create `.env`

Create **`.env`** in the project root (same folder as `server.py`). This file is **not** committed to Git.

```env
GITHUB_TOKEN=your_github_token
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key

PORT=8000
LOW_COST_MODE=false
```

### 6. Start the server

**Option A — script:**

```powershell
.\start.ps1
```

**Option B — manual:**

```powershell
python server.py
```

### 7. Open the app

Go to **http://localhost:8000** in your browser.

Paste a public repo URL (e.g. `https://github.com/pallets/flask`) and click **Start Analysis**.

> Use **http://localhost:8000**, not the HTML file directly. Live logs need the backend.

### Troubleshooting

| Problem | Fix |
|--------|-----|
| `python` not found | Use `py -3.11 server.py` or reinstall Python with PATH |
| `git` not found | Install Git, restart terminal |
| Port in use | Set `PORT=8001` in `.env` |
| Missing modules | `pip install -r requirements.txt` |
| No live updates | Must use `http://localhost:8000` |
| Clone fails | Repo must be public; test: `git clone https://github.com/pallets/flask` |

Health: **http://localhost:8000/health**

## JacCloud

Set `GITHUB_TOKEN`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `PORT` — start with `python server.py`.

## Docs

- [JAC_ARCHITECTURE.md](JAC_ARCHITECTURE.md)
- [AGENT_INTERACTION_FLOW.md](AGENT_INTERACTION_FLOW.md)

## API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/analyze` | Start analysis |
| GET | `/stream/:id` | SSE live stream |
| POST | `/chat` | AI Q&A |
| POST | `/approve_fix` | Approve patches |
