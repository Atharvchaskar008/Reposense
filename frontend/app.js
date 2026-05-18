const API = window.location.origin || "http://localhost:8000";

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
let graphSim = null;

const $ = (id) => document.getElementById(id);

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
      </div>
    `;
    grid.appendChild(card);
  });
}

function stateClass(state) {
  return (state || "IDLE").toLowerCase().replace(/\s+/g, "_");
}

function setLoading(loading) {
  const btn = $("analyzeBtn");
  btn.disabled = loading;
  btn.classList.toggle("is-loading", loading);
  btn.querySelector(".btn-spinner").hidden = !loading;
}

function updateAgents(agents) {
  if (!agents) return;
  Object.entries(agents).forEach(([name, data]) => {
    const card = document.getElementById(`agent-${name}`);
    if (!card) return;
    const st = data.state || "IDLE";
    card.className = `agent-card ${["RUNNING", "THINKING", "REQUESTING_APPROVAL"].includes(st) ? "running" : ""}`;
    card.querySelector("[data-state]").textContent = st;
    card.querySelector("[data-action]").textContent = data.last_action || "—";
    const dot = card.querySelector("[data-dot]");
    dot.className = `status-dot ${stateClass(st)}`;
  });
}

function appendLog(entry) {
  const stream = $("logStream");
  const line = document.createElement("div");
  line.className = `log-line ${entry.level || "info"}`;
  const ts = entry.ts ? new Date(entry.ts).toLocaleTimeString() : "";
  line.textContent = ts ? `> [${ts}] ${entry.message}` : `> ${entry.message}`;
  stream.appendChild(line);
  stream.scrollTop = stream.scrollHeight;
}

function updateIntel(summary) {
  if (!summary || !Object.keys(summary).length) return;
  $("intelType").textContent = summary.repo_type || "—";
  $("intelArch").textContent = summary.architecture || "—";
  $("intelTech").textContent = (summary.technologies || []).join(", ") || "—";
  $("intelComplexity").textContent = summary.complexity || "—";
  const risk = $("intelRisk");
  risk.textContent = summary.risk_level || "—";
  risk.className = `risk-badge ${(summary.risk_level || "").toLowerCase()}`;
  $("intelPurpose").textContent = summary.purpose || summary.risk_summary || "—";
}

function renderApprovals(approvals) {
  const box = $("approvalConsole");
  const pending = (approvals || []).filter((a) => a.status === "pending");
  if (!pending.length) {
    box.innerHTML = approvals?.length
      ? `<p class="muted">All approval requests resolved.</p>`
      : `<p class="muted">Approval mode lets you accept or reject FixAgent patches before they apply.</p>`;
    return;
  }
  box.innerHTML = "";
  pending.forEach((a) => {
    const card = document.createElement("div");
    card.className = "approval-card";
    card.innerHTML = `
      <h4>${a.agent}: ${a.question}</h4>
      <p class="muted">${a.file}:${a.line}</p>
      <p>${a.recommendation}</p>
      <pre>${escapeHtml(a.fix_preview || "")}</pre>
      <div class="approval-actions">
        <button class="approve" data-id="${a.id}" data-act="approve">Approve</button>
        <button class="reject" data-id="${a.id}" data-act="reject">Reject</button>
        <button data-id="${a.id}" data-act="why">Ask Why</button>
      </div>
    `;
    box.appendChild(card);
  });
  box.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => handleApproval(btn));
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;");
}

async function handleApproval(btn) {
  const id = btn.dataset.id;
  const act = btn.dataset.act;
  if (act === "why") {
    $("queryInput").value = "Why is this vulnerable?";
    await runQuery();
    return;
  }
  await fetch(`${API}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      approval_id: id,
      approved: act === "approve",
    }),
  });
}

function renderFixes(fixes) {
  const list = $("fixesList");
  if (!fixes?.length) {
    list.innerHTML = `<p class="muted">Patches appear after security analysis.</p>`;
    return;
  }
  list.innerHTML = fixes
    .map(
      (f) => `
    <div class="fix-card">
      <strong>${escapeHtml(f.title || "Suggested fix")}</strong>
      <p class="muted">${escapeHtml(f.file || "")}:${f.line || ""}</p>
      <pre>${escapeHtml(f.diff || "")}</pre>
      <p class="muted">${escapeHtml(f.reasoning || "")}</p>
    </div>`
    )
    .join("");
}

/** Vanilla force-directed layout */
function startForceGraph(graph) {
  const svg = $("graphSvg");
  const nodes = (graph?.nodes || []).slice(0, 32);
  const edges = (graph?.edges || []).slice(0, 60);

  if (!nodes.length) {
    svg.innerHTML = `<text x="24" y="48" fill="#64748b" font-size="13">Graph populates after dependency analysis</text>`;
    return;
  }

  const w = 640;
  const h = 360;
  const cx = w / 2;
  const cy = h / 2;

  const simNodes = nodes.map((n, i) => ({
    id: n.id,
    label: (n.id || "").split(".").pop().slice(0, 12),
    issue: n.has_issue || (n.risk_score || 0) > 0,
    x: cx + Math.cos((i / nodes.length) * Math.PI * 2) * 120,
    y: cy + Math.sin((i / nodes.length) * Math.PI * 2) * 120,
    vx: 0,
    vy: 0,
  }));

  const nodeIndex = Object.fromEntries(simNodes.map((n, i) => [n.id, i]));
  const simEdges = edges
    .filter((e) => nodeIndex[e.source] != null && nodeIndex[e.target] != null)
    .map((e) => ({ source: nodeIndex[e.source], target: nodeIndex[e.target] }));

  if (graphSim) cancelAnimationFrame(graphSim);

  const tick = () => {
    // repulsion
    for (let i = 0; i < simNodes.length; i++) {
      for (let j = i + 1; j < simNodes.length; j++) {
        const a = simNodes[i];
        const b = simNodes[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = 4200 / (dist * dist);
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        a.vx -= dx;
        a.vy -= dy;
        b.vx += dx;
        b.vy += dy;
      }
    }
    // springs
    simEdges.forEach((e) => {
      const a = simNodes[e.source];
      const b = simNodes[e.target];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      let dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - 70) * 0.04;
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      a.vx += dx;
      a.vy += dy;
      b.vx -= dx;
      b.vy -= dy;
    });
    // center gravity
    simNodes.forEach((n) => {
      n.vx += (cx - n.x) * 0.002;
      n.vy += (cy - n.y) * 0.002;
      n.vx *= 0.86;
      n.vy *= 0.86;
      n.x += n.vx;
      n.y += n.vy;
      n.x = Math.max(24, Math.min(w - 24, n.x));
      n.y = Math.max(24, Math.min(h - 24, n.y));
    });

    let edgeSvg = "";
    simEdges.forEach((e) => {
      const a = simNodes[e.source];
      const b = simNodes[e.target];
      edgeSvg += `<line class="graph-edge" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" />`;
    });

    let nodeSvg = "";
    simNodes.forEach((n) => {
      const cls = n.issue ? "graph-node issue" : "graph-node";
      nodeSvg += `
        <circle class="${cls}" cx="${n.x}" cy="${n.y}" r="16" />
        <text class="graph-label" x="${n.x}" y="${n.y + 28}" text-anchor="middle">${escapeHtml(n.label)}</text>
      `;
    });

    svg.innerHTML = edgeSvg + nodeSvg;
    graphSim = requestAnimationFrame(tick);
  };

  tick();
}

function applyState(data) {
  if (!data) return;
  updateAgents(data.agents);
  updateIntel(data.summary);
  renderApprovals(data.approvals);
  renderFixes(data.fixes);
  startForceGraph(data.graph);

  if (data.status === "completed" || data.status === "failed") {
    setLoading(false);
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    appendLog({
      message:
        data.status === "completed"
          ? "Mission complete — all agents standing down"
          : "Mission failed — check logs above",
      level: data.status === "completed" ? "info" : "error",
    });
  }
}

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource(`${API}/stream/${sessionId}`);

  eventSource.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "log") appendLog(msg.data);
      if (msg.type === "state") applyState(msg.data);
      if (msg.error) appendLog({ message: msg.error, level: "error" });
    } catch (e) {
      console.warn("SSE parse error", e);
    }
  };

  eventSource.onerror = () => {
    appendLog({ message: "SSE reconnecting…", level: "warn" });
    eventSource?.close();
    setTimeout(() => {
      if (sessionId) connectSSE();
    }, 1500);
  };
}

async function startAnalysis() {
  const repoUrl = $("repoInput").value.trim();
  const mode = $("executionMode").value;

  if (!repoUrl) {
    appendLog({ message: "Enter a GitHub repository URL.", level: "warn" });
    $("repoInput").focus();
    return;
  }

  if (!/^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+\/?$/i.test(repoUrl.replace(/\.git$/, ""))) {
    appendLog({ message: "Invalid URL — use https://github.com/owner/repo", level: "error" });
    return;
  }

  setLoading(true);
  $("logStream").innerHTML = "";
  initAgents();
  if (graphSim) cancelAnimationFrame(graphSim);

  appendLog({ message: "Initializing RepoSense mission control…", level: "info" });

  try {
    const res = await fetch(`${API}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, execution_mode: mode }),
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }

    sessionId = data.session_id;
    appendLog({ message: `Session ${sessionId} — agents deploying`, level: "info" });
    connectSSE();
  } catch (err) {
    appendLog({ message: err.message || "Cannot reach API — run: python server.py", level: "error" });
    setLoading(false);
  }
}

async function runQuery() {
  const q = $("queryInput").value.trim();
  if (!q) return;
  if (!sessionId) {
    $("queryAnswer").textContent = "Start an analysis first.";
    return;
  }
  $("queryAnswer").textContent = "Thinking…";
  $("queryAnswer").classList.add("loading");
  try {
    const res = await fetch(`${API}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, query: q }),
    });
    const data = await res.json();
    $("queryAnswer").textContent = data.answer || "No answer.";
  } catch {
    $("queryAnswer").textContent = "Query failed — check backend connection.";
  } finally {
    $("queryAnswer").classList.remove("loading");
  }
}

$("analyzeBtn").addEventListener("click", startAnalysis);
$("queryBtn").addEventListener("click", runQuery);
$("queryInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runQuery();
});

initAgents();
