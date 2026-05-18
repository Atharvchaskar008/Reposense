# RepoSense Development Roadmap

## Phase 1 — Foundation (Complete)

| Task | Complexity | Status |
|------|------------|--------|
| Project structure (`jac.toml`, folders) | Low | Done |
| Graph nodes (`RepoNode`, `FileNode`, `TaskNode`) | Medium | Done |
| Python utils (clone, parse, graph) | Medium | Done |
| Config + `.env.example` | Low | Done |

## Phase 2 — Agents (Complete)

| Task | Complexity | Status |
|------|------------|--------|
| DependencyAgent (Jac + Python) | Medium | Done |
| SecurityAgent heuristics | Medium | Done |
| ImpactAgent graph traversal | Medium | Done |
| FixAgent + LLM hook | Medium | Done |
| ExplanationAgent heuristics | Low | Done |
| MonitorAgent | Low | Done |
| RepoAnalyzer orchestrator | Medium | Done |

## Phase 3 — API & Orchestration (Complete)

| Task | Complexity | Status |
|------|------------|--------|
| `orchestrator.py` pipeline | Medium | Done |
| `server.py` REST + CORS | Medium | Done |
| Approval workflow | Medium | Done |
| Session state + JSON export | Low | Done |

## Phase 4 — Mission Control UI (Complete)

| Task | Complexity | Status |
|------|------------|--------|
| Agent status panel (glow states) | High | Done |
| Live log stream | High | Done |
| Repository intelligence panel | Medium | Done |
| Approval console | Medium | Done |
| SVG dependency graph | Low | Done |
| Secondary query bar | Low | Done |
| Demo fallback (offline) | Low | Done |

## MVP vs Optional

### MVP (required for hackathon)

- [x] GitHub URL → clone → analyze
- [x] Live agent states + logs
- [x] Dependency graph
- [x] Security findings
- [x] Repo summary (heuristics)
- [x] Fix suggestions
- [x] Approval mode

### Optional (post-MVP)

- [ ] Full Jac-only runtime (no Python orchestrator)
- [ ] SSE-only frontend (remove polling)
- [ ] Richer LLM integrations (Anthropic/OpenAI SDKs)
- [ ] Multi-language AST (JS/TS)
- [ ] Persistent graph DB
- [ ] Auth / multi-user

## Recommended Build Order

1. Python utils + config
2. Orchestrator pipeline
3. HTTP server
4. Frontend agent panel + logs
5. Jac walkers (parallel)
6. Intelligence + approval UI
7. Graph viz + query bar
8. Docs + LLM guide

## Demo Priorities

1. **Agent panel animation** — judges see autonomy immediately
2. **Live log stream** — terminal aesthetic
3. **One real public repo** — Flask or FastAPI sample
4. **Approval moment** — supervisor approves a fix
5. **Intelligence summary** — non-technical clarity

## Final Submission Checklist

- [ ] `python server.py` runs without errors
- [ ] Frontend loads at http://localhost:8000
- [ ] Public GitHub repo analyzes end-to-end
- [ ] At least one security finding or clear "clean" message
- [ ] README setup steps verified on fresh machine
- [ ] `.env.example` documents all keys
- [ ] `LLM_AND_API_SETUP.md` included
- [ ] Git history shows incremental commits
- [ ] No secrets committed in `.env`

## Estimated Complexity

| Area | Effort |
|------|--------|
| Full MVP | 1–2 days |
| LLM polish | 4–8 hours |
| UI polish | 4–6 hours |
| Jac-only deployment | 8+ hours (optional) |

## Token / Cursor Optimization

- Build utils before agents
- Use heuristic mode first; add LLM last
- Keep Jac walkers thin; delegate to Python utils
- Commit per milestone (see git log)
