const API =
  window.location.protocol === "file:"
    ? "http://localhost:8000"
    : window.location.origin;

const AGENTS = [
  "DependencyAgent",
  "SecurityAgent",
  "ImpactAgent",
  "FixAgent",
  "MonitorAgent",
  "ExplanationAgent",
];

let sessionId = null;
let eventSource = null;
let reconnectTimer = null;
let reconnectAttempts = 0;
let sessionFinished = false;
let logCursor = 0;
let latestState = null;
let activePollTimer = null;
const seenLogs = new Set();

const $ = (id) => document.getElementById(id);

const PHASE_LABELS = {
  queued: "Preparing analysis",
  cloning: "Cloning repository",
  analyzing: "Analyzing architecture",
  generating: "Running AI agents",
  completed: "Finalizing report",
  failed: "Execution interrupted",
};

function initAgents() {
  const grid = $("agentsGrid");
  grid.innerHTML = "";
  AGENTS.forEach((name) => {
    const card = document.createElement("div");
    card.className = "agent-card";
    card.id = `agent-${name}`;
    card.innerHTML = `
      <div>
        <div class="agent-name">${name}</div>
        <div class="agent-action" data-action>Standing by</div>
      </div>
      <div class="status-pill">
        <span class="status-dot idle" data-dot></span>
        <span data-state>IDLE</span>
      </div>`;
    grid.appendChild(card);
  });
}

function stateClass(state) {
  return (state || "IDLE").toLowerCase().replace(/\s+/g, "_");
}

function updateAgents(agents) {
  if (!agents) return;
  Object.entries(agents).forEach(([name, data]) => {
    const card = document.getElementById(`agent-${name}`);
    if (!card) return;
    const st = data.state || "IDLE";
    card.className = `agent-card ${stateClass(st)}`;
    if (["RUNNING", "THINKING"].includes(st)) card.classList.add("running");
    card.querySelector("[data-state]").textContent = st;
    card.querySelector("[data-action]").textContent = data.last_action || "-";
    card.querySelector("[data-dot]").className = `status-dot ${stateClass(st)}`;
  });
}

function appendLog(entry) {
  const key = `${entry.ts || ""}|${entry.agent || ""}|${entry.message || entry.display || ""}`;
  if (seenLogs.has(key)) return;
  seenLogs.add(key);
  if (seenLogs.size > 500) {
    const first = seenLogs.values().next().value;
    seenLogs.delete(first);
  }
  const stream = $("logStream");
  const line = document.createElement("div");
  const agent = entry.agent ? `[${entry.agent}] ` : "";
  line.className = `log-line ${entry.level || "info"}`;
  line.textContent = entry.display ? `> ${entry.display}` : `> ${agent}${entry.message}`;
  stream.appendChild(line);
  while (stream.children.length > 180) {
    stream.removeChild(stream.firstChild);
  }
  stream.scrollTop = stream.scrollHeight;
}

function escapeHtml(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;");
}

let lastGithubName = "";
function updateGithub(gh) {
  if (!gh || !Object.keys(gh).length) return;
  $("intelRepo").textContent = gh.full_name || "-";
  $("intelStars").textContent = `${gh.stars ?? 0} / ${gh.forks ?? 0} / ${gh.open_issues ?? 0}`;
  if (gh.full_name && gh.full_name !== lastGithubName) {
    lastGithubName = gh.full_name;
    if (gh.description) {
      appendLog({ message: gh.description, level: "info", agent: "DependencyAgent" });
    }
  }
}

function updateIntel(summary, github, codeQuality, recommendations, maintainability) {
  if (github) updateGithub(github);
  if (maintainability && maintainability.grade) {
    const q = $("intelQuality");
    const base = codeQuality?.grade
      ? `${codeQuality.grade} (${codeQuality.score}/100)`
      : "";
    q.textContent = base
      ? `${base} | Maintainability ${maintainability.grade}`
      : `Maintainability ${maintainability.grade} (${maintainability.score}/100)`;
  }
  if (summary && Object.keys(summary).length) {
    $("intelType").textContent = summary.repo_type || "General Software Project";
    $("intelArch").textContent = summary.architecture_overview || summary.architecture || "-";
    const langs = summary.tech_stack || summary.technologies || (github && github.languages) || [];
    $("intelTech").textContent = Array.isArray(langs) ? langs.join(", ") : langs;
    const complexityText = summary.complexity_score
      ? `${summary.complexity || "Unknown"} (${summary.complexity_score}/100)`
      : summary.complexity || "-";
    $("intelComplexity").textContent = complexityText;
    const risk = $("intelRisk");
    risk.textContent = summary.risk_level || "-";
    risk.className = `risk-badge ${(summary.risk_level || "").toLowerCase()}`;
    $("intelPurpose").textContent =
      summary.repository_summary || summary.purpose || summary.risk_summary || "Analysis complete.";
  }
  if (codeQuality && Object.keys(codeQuality).length && !maintainability?.grade) {
    $("intelQuality").textContent = `${codeQuality.grade} (${codeQuality.score}/100)`;
  }
  if (recommendations && recommendations.length) {
    $("intelRecs").innerHTML = recommendations
      .map((r) => `<li>${escapeHtml(r)}</li>`)
      .join("");
  } else if (summary?.security_insights?.length || summary?.maintainability_analysis?.length) {
    $("intelRecs").innerHTML = [
      ...(summary.security_insights || []),
      ...(summary.maintainability_analysis || []),
    ]
      .slice(0, 5)
      .map((r) => `<li>${escapeHtml(r)}</li>`)
      .join("");
  } else {
    $("intelRecs").innerHTML = `<li class="muted">Analysis completed with fallback data.</li>`;
  }
}

function setAnalyzeLoading(isLoading) {
  const btn = $("analyzeBtn");
  btn.disabled = isLoading;
  btn.classList.toggle("is-loading", isLoading);
  btn.innerHTML = isLoading
    ? `<span class="btn-spinner" aria-hidden="true"></span><span>Executing...</span>`
    : "Start Analysis";
  document.body.classList.toggle("is-analyzing", isLoading);
  document.querySelector(".stream-panel")?.classList.toggle("panel-live", isLoading);
  document.querySelector(".agents-panel")?.classList.toggle("panel-live", isLoading);
}

function setConnectionStatus(status, label = "") {
  const pill = $("streamConnection");
  pill.className = `connection-pill ${status}`;
  pill.textContent =
    label ||
    {
      connecting: "Connecting stream",
      connected: "Live stream active",
      reconnecting: "Reconnecting stream",
      error: "Stream interrupted",
    }[status] ||
      "Disconnected";
}

function derivePhase(data) {
  if (!data) return PHASE_LABELS.queued;
  if (data.phase) return data.phase;
  const lifecycle = data.lifecycle || data.status || "queued";
  if (lifecycle === "generating" && (data.progress || 0) >= 88) return "Finalizing report";
  if (lifecycle === "generating") return "Generating recommendations";
  if (lifecycle === "analyzing" && (data.progress || 0) >= 55) return "Running AI agents";
  return PHASE_LABELS[lifecycle] || "Preparing analysis";
}

function updatePhase(data) {
  $("missionPhase").textContent = derivePhase(data);
}

function updateAgentTicker(data) {
  const ticker = $("agentTicker");
  const activeAgents = data?.active_agents || [];
  if (activeAgents.length) {
    ticker.textContent = activeAgents
      .map((agent) => `${agent.name}: ${agent.action || agent.state}`)
      .join("  •  ");
    ticker.classList.add("is-live");
    return;
  }

  const status = data?.status || "queued";
  if (status === "completed") {
    ticker.textContent = "All agents finished. Report ready.";
  } else if (status === "failed") {
    ticker.textContent = "Agent execution interrupted. Showing latest available results.";
  } else {
    ticker.textContent = "Waiting for agents to start...";
  }
  ticker.classList.remove("is-live");
}

function renderApprovals(approvals) {
  const box = $("approvalConsole");
  const pending = (approvals || []).filter((a) => a.status === "pending");
  if (!pending.length) {
    box.innerHTML = approvals?.length
      ? `<p class="muted">All supervisor approvals resolved.</p>`
      : `<p class="muted">Supervisor approvals appear when agents request critical actions.</p>`;
    return;
  }
  box.innerHTML = "";
  pending.forEach((a) => {
    const card = document.createElement("div");
    card.className = "approval-card";
    card.innerHTML = `
      <h4>${escapeHtml(a.agent)}: ${escapeHtml(a.question)}</h4>
      <p class="muted">${escapeHtml(a.file)}:${a.line}</p>
      <p>${escapeHtml(a.recommendation)}</p>
      <pre>${escapeHtml(a.fix_preview || "")}</pre>
      <div class="approval-actions">
        <button class="approve" data-id="${a.id}" data-act="approve">Approve</button>
        <button class="reject" data-id="${a.id}" data-act="reject">Reject</button>
        <button data-id="${a.id}" data-act="why">Ask Why</button>
      </div>`;
    box.appendChild(card);
  });
  box.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => handleApproval(btn));
  });
}

async function handleApproval(btn) {
  const act = btn.dataset.act;
  if (act === "why") {
    $("queryInput").value = "Why is this vulnerable?";
    await runQuery();
    return;
  }
  await fetch(`${API}/approve_fix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      approval_id: btn.dataset.id,
      approved: act === "approve",
    }),
  });
}

function renderFixes(fixes) {
  const list = $("fixesList");
  if (!fixes?.length) {
    list.innerHTML = `<p class="muted">Patches appear after security remediation tasks complete.</p>`;
    return;
  }
  list.innerHTML = fixes
    .map(
      (f) => `
    <div class="fix-card">
      <strong>${escapeHtml(f.title || "Suggested patch")}</strong>
      <p class="muted">${escapeHtml(f.file)}:${f.line || ""}</p>
      <pre>${escapeHtml(f.diff || "")}</pre>
      <p class="muted">${escapeHtml(f.reasoning || "")}</p>
    </div>`
    )
    .join("");
}

function renderGraph(graph) {
  const svg = $("graphSvg");
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  if (!nodes.length) {
    svg.innerHTML = `<text x="20" y="40" fill="#64748b" font-size="12">Task graph populates after dependency analysis</text>`;
    return;
  }
  const w = 600,
    h = 320,
    cx = w / 2,
    cy = h / 2,
    r = Math.min(w, h) * 0.38;
  const positions = {};
  nodes.slice(0, 24).forEach((n, i) => {
    const angle = (i / Math.min(nodes.length, 24)) * Math.PI * 2;
    positions[n.id] = { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  });
  let edgeSvg = "";
  edges.slice(0, 40).forEach((e) => {
    const a = positions[e.source],
      b = positions[e.target];
    if (a && b) edgeSvg += `<line class="graph-edge" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}"/>`;
  });
  let nodeSvg = "";
  Object.entries(positions).forEach(([id, p]) => {
    const label = id.split(".").pop().slice(0, 10);
    nodeSvg += `<circle class="graph-node" cx="${p.x}" cy="${p.y}" r="14"/><text class="graph-label" x="${p.x}" y="${p.y + 24}" text-anchor="middle">${escapeHtml(label)}</text>`;
  });
  svg.innerHTML = edgeSvg + nodeSvg;
}

function applyState(data) {
  if (!data) return;
  latestState = data;
  if (typeof data.log_count === "number") {
    logCursor = Math.max(logCursor, data.log_count);
  }
  updateAgents(data.agents);
  updatePhase(data);
  updateAgentTicker(data);
  updateIntel(
    data.summary,
    data.github,
    data.code_quality,
    data.recommendations,
    data.maintainability
  );
  renderApprovals(data.approvals);
  renderFixes(data.fixes);
  renderGraph(data.graph);
  if (data.progress && data.status !== "completed" && data.status !== "failed") {
    $("analyzeBtn").innerHTML =
      `<span class="btn-spinner" aria-hidden="true"></span><span>Executing ${data.progress}%</span>`;
  }
  if (data.status === "completed" || data.status === "failed") {
    sessionFinished = true;
    setAnalyzeLoading(false);
    setConnectionStatus("connected", data.status === "completed" ? "Stream complete" : "Stream closed");
    stopSessionPolling();
  }
}

async function pollSessionState() {
  if (!sessionId) return;
  try {
    const res = await fetch(`${API}/session/${sessionId}`);
    if (!res.ok) return;
    const data = await res.json();
    applyState(data);
  } catch {}
}

function startSessionPolling() {
  if (activePollTimer) return;
  activePollTimer = setInterval(() => {
    if (!sessionFinished) pollSessionState();
  }, 2500);
}

function stopSessionPolling() {
  if (!activePollTimer) return;
  clearInterval(activePollTimer);
  activePollTimer = null;
}

function scheduleReconnect() {
  if (sessionFinished || reconnectTimer) return;
  reconnectAttempts += 1;
  const delay = Math.min(8000, 1200 * reconnectAttempts);
  setConnectionStatus("reconnecting", `Reconnecting stream (${reconnectAttempts})`);
  startSessionPolling();
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    pollSessionState();
    connectSSE({ reconnect: true });
  }, delay);
}

function connectSSE({ reconnect = false } = {}) {
  if (eventSource) eventSource.close();
  if (!sessionId) return;
  const url = `${API}/stream/${sessionId}?from_log=${logCursor}`;
  setConnectionStatus(reconnect ? "reconnecting" : "connecting");
  eventSource = new EventSource(url);

  eventSource.onopen = () => {
    reconnectAttempts = 0;
    stopSessionPolling();
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    setConnectionStatus("connected");
    if (reconnect) {
      appendLog({
        message: "Live stream resumed",
        level: "info",
        agent: "MonitorAgent",
      });
    }
  };

  eventSource.onmessage = (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    if (msg.type === "log" && msg.data) {
      logCursor += 1;
      appendLog(msg.data);
    }
    else if (msg.type === "state" && msg.data) applyState(msg.data);
    else if (msg.type === "done") {
      sessionFinished = true;
      appendLog({
        message:
          msg.data?.status === "completed"
            ? "Autonomous execution complete"
            : "Execution failed",
        level: msg.data?.status === "completed" ? "info" : "error",
        agent: "MonitorAgent",
      });
      setAnalyzeLoading(false);
      setConnectionStatus("connected", "Stream complete");
      eventSource.close();
    } else if (msg.type === "error") {
      appendLog({ message: msg.data?.message || "Stream error", level: "error" });
      setConnectionStatus("error");
      eventSource.close();
      scheduleReconnect();
    }
  };

  eventSource.onerror = () => {
    if (sessionFinished) {
      setConnectionStatus("connected", "Stream complete");
      return;
    }
    eventSource.close();
    appendLog({
      message: "Live stream connection interrupted. Reconnecting...",
      level: "warn",
      agent: "MonitorAgent",
    });
    scheduleReconnect();
  };
}

async function startAnalysis() {
  const repoUrl = $("repoInput").value.trim();
  const mode = $("executionMode").value;
  if (!repoUrl) {
    alert("Enter a public GitHub repository URL.");
    return;
  }

  sessionFinished = false;
  logCursor = 0;
  reconnectAttempts = 0;
  latestState = null;
  seenLogs.clear();
  stopSessionPolling();
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  setAnalyzeLoading(true);
  setConnectionStatus("connecting");
  $("logStream").innerHTML = "";
  lastGithubName = "";
  initAgents();
  updatePhase({ lifecycle: "queued" });
  updateAgentTicker({ status: "queued" });
  appendLog({ message: "Initializing graph-native mission control", agent: "MonitorAgent" });

  try {
    const res = await fetch(`${API}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, execution_mode: mode }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body.error || "Analysis failed to start");

    sessionId = body.session_id;
    appendLog({ message: `Session ${sessionId} - agents deploying`, agent: "MonitorAgent" });
    connectSSE();
  } catch (err) {
    appendLog({
      message: `Backend unavailable: ${err.message}. Run: python server.py`,
      level: "error",
    });
    setAnalyzeLoading(false);
    setConnectionStatus("error");
  }
}

async function runQuery() {
  const q = $("queryInput").value.trim();
  if (!q) return;
  if (!sessionId) {
    $("queryAnswer").textContent = "Start an analysis first.";
    return;
  }
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, query: q, message: q }),
  });
  const data = await res.json();
  $("queryAnswer").textContent = data.answer || "No answer.";
}

$("analyzeBtn").addEventListener("click", startAnalysis);
$("queryBtn").addEventListener("click", runQuery);
$("queryInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runQuery();
});

initAgents();
