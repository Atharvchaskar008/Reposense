# LLM and API Setup — RepoSense

RepoSense is **agent-first, LLM-second**. Most intelligence comes from AST parsing, graph traversal, and heuristic security rules. LLMs enhance specific agents only where reasoning or summarization adds clear value.

## Agent LLM Requirements

| Agent | Requires LLM? | Primary Method | API Key |
|-------|---------------|----------------|---------|
| **DependencyAgent** | No | AST, NetworkX, git clone | None |
| **SecurityAgent** | No (optional explain) | Regex, heuristics | `GEMINI_API_KEY` optional |
| **ImpactAgent** | No (optional narrate) | Graph traversal | Optional |
| **FixAgent** | **Yes** (recommended) | Heuristic fallback + LLM patches | See below |
| **MonitorAgent** | No | State machine / logs | None |
| **ExplanationAgent** | Optional | Stack heuristics + summary LLM | `GEMINI_API_KEY` optional |

## Best Model Per Agent

### DependencyAgent — No LLM

- **Tools:** `ast`, `networkx`, `subprocess` (git)
- **Why:** Deterministic and fast; LLM adds no value for import graphs.

### SecurityAgent — Heuristics first

- **Default:** Regex + static rules in `utils/security_scanner.py`
- **Optional LLM:** Vulnerability explanation, severity reasoning
- **Recommended:** Gemini 2.5 Flash — cheap, fast, generous free tier
- **Alternatives:** Claude Sonnet, GPT-4.1-mini
- **Key:** `GEMINI_API_KEY` (optional)

### ImpactAgent — Graph-first

- **Default:** NetworkX path / descendant analysis
- **Optional LLM:** Human-readable blast-radius narrative
- **Recommended:** Claude Sonnet or Gemini Flash
- **Key:** Optional

### FixAgent — Primary LLM agent

- **Responsibilities:** Patch generation, secure replacements, diffs, reasoning
- **Best for code fixes:** **Claude Sonnet** — clean patches, strong code understanding
- **Best for structured edits:** **GPT-4.1** — reliable structured output
- **Best for long repos / cost:** **Gemini 2.5 Pro** — large context, affordable
- **Hackathon default:** Claude Sonnet **or** Gemini 2.5 Pro
- **Keys (one of):**
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`
  - `GEMINI_API_KEY`

Configure in `.env`:

```env
FIX_AGENT_MODEL=claude-sonnet
```

### ExplanationAgent — Lightweight LLM

- **Default fallback:** Heuristic summaries (Flask → backend API, etc.)
- **Recommended:** **Gemini Flash** — fast, low cost, strong summarization
- **Alternatives:** GPT-4.1-mini, Claude Haiku
- **Key:** `GEMINI_API_KEY` (optional)

### MonitorAgent — No LLM

- Pure orchestration; no API key.

## Centralized Config

`config.py`:

```python
MODEL_CONFIG = {
    "fix_agent": "claude-sonnet",
    "explanation_agent": "gemini-flash",
    "security_agent": "gemini-flash",
    "impact_agent": "gemini-flash",
}
```

Copy `.env.example` → `.env` and set keys.

## Free Alternatives

| Need | Free option |
|------|-------------|
| Summaries | Heuristic mode (`LOW_COST_MODE=true`) |
| Security | Built-in regex scanner |
| Fixes | Patch templates in `security_scanner.FIX_TEMPLATES` |
| LLM calls | Gemini free tier, OpenAI trial credits |

## Local Model Support

```env
USE_LOCAL_MODELS=true
LOCAL_MODEL=deepseek-coder
OLLAMA_BASE_URL=http://localhost:11434
```

FixAgent routes through Ollama when enabled (`utils/llm_fixer.py`).

**Suggested local models:** DeepSeek Coder, Qwen Coder, CodeLlama via Ollama.

## Cost Optimization

### LOW-COST MODE (default)

```env
LOW_COST_MODE=true
```

- Only FixAgent may use LLM (if keys present)
- ExplanationAgent uses heuristics only
- SecurityAgent / ImpactAgent fully deterministic
- **Zero API keys required** for a working demo

### What you can skip initially

1. All API keys — full pipeline works with heuristics
2. ImpactAgent LLM narration
3. SecurityAgent LLM explanations
4. Local Ollama setup

### What to add for best demo

1. `GEMINI_API_KEY` — ExplanationAgent + optional Security narrations
2. `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` — FixAgent richer patches

## APIs Can Be Skipped Initially

Run with **no keys**:

```bash
python server.py
```

You still get: clone, dependency graph, security findings, impact analysis, heuristic summary, template-based fixes, live agent UI.

## Hackathon Recommendation

**Best balance of cost, speed, reliability, and demo quality:**

| Component | Choice |
|-----------|--------|
| Scanning & graph | Deterministic (no LLM) |
| Summaries | Gemini Flash |
| Fixes | Claude Sonnet |
| Mode | `LOW_COST_MODE=false` only if keys available |

This yields impressive demos with minimal token usage and fast responses.

## Environment Template

```env
GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
LOW_COST_MODE=true
USE_LOCAL_MODELS=false
FIX_AGENT_MODEL=claude-sonnet
EXPLANATION_AGENT_MODEL=gemini-flash
```
