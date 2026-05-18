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
let pollTimer = null;
let seenLogs = 0;

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

function updateAgents(agents) {
  if (!agents) return;
  Object.entries(agents).forEach(([name, data]) => {
    const card = document.getElementById(`agent-${name}`);
    if (!card) return;
    const st = data.state || "IDLE";
    card.className = `agent-card ${["RUNNING", "THINKING"].includes(st) ? "running" : ""}`;
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
  line.textContent = `> ${entry.message}`;
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
    if (!approvals?.length) {
      box.innerHTML = `<p class="muted">Agents will request supervisor approval when critical actions are detected.</p>`;
    } else {
      box.innerHTML = `<p class="muted">All approval requests resolved.</p>`;
    }
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
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
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
  pollSession();
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
      <strong>${f.title || "Suggested fix"}</strong>
      <p class="muted">${f.file}:${f.line}</p>
      <pre>${escapeHtml(f.diff || "")}</pre>
      <p class="muted">${f.reasoning || ""}</p>
    </div>`
    )
    .join("");
}

function renderGraph(graph) {
  const svg = $("graphSvg");
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  if (!nodes.length) {
    svg.innerHTML = `<text x="20" y="40" fill="#64748b" font-size="12">Graph populates after dependency analysis</text>`;
    return;
  }

  const w = 600;
  const h = 320;
  const cx = w / 2;
  const cy = h / 2;
  const r = Math.min(w, h) * 0.38;
  const positions = {};

  nodes.slice(0, 24).forEach((n, i) => {
    const angle = (i / Math.min(nodes.length, 24)) * Math.PI * 2;
    positions[n.id] = {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  });

  let edgeSvg = "";
  edges.slice(0, 40).forEach((e) => {
    const a = positions[e.source];
    const b = positions[e.target];
    if (a && b) {
      edgeSvg += `<line class="graph-edge" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" />`;
    }
  });

  let nodeSvg = "";
  Object.entries(positions).forEach(([id, p]) => {
    const label = id.split(".").pop().slice(0, 10);
    nodeSvg += `
      <circle class="graph-node" cx="${p.x}" cy="${p.y}" r="14" />
      <text class="graph-label" x="${p.x}" y="${p.y + 24}" text-anchor="middle">${label}</text>
    `;
  });

  svg.innerHTML = edgeSvg + nodeSvg;
}

async function pollSession() {
  if (!sessionId) return;
  try {
    const res = await fetch(`${API}/session/${sessionId}`);
    const data = await res.json();

    const logs = data.logs || [];
    while (seenLogs < logs.length) {
      appendLog(logs[seenLogs]);
      seenLogs++;
    }

    updateAgents(data.agents);
    updateIntel(data.summary);
    renderApprovals(data.approvals);
    renderFixes(data.fixes);
    renderGraph(data.graph);

    if (data.status === "completed" || data.status === "failed") {
      clearInterval(pollTimer);
      $("analyzeBtn").disabled = false;
      appendLog({
        message:
          data.status === "completed"
            ? "Mission complete — all agents standing down"
            : "Mission failed — check logs",
        level: data.status === "completed" ? "info" : "error",
      });
    }
  } catch (e) {
    console.error(e);
  }
}

async function startAnalysis() {
  const repoUrl = $("repoInput").value.trim();
  const mode = $("executionMode").value;

  if (!repoUrl) {
    alert("Paste a GitHub repository URL.");
    return;
  }

  $("analyzeBtn").disabled = true;
  $("logStream").innerHTML = "";
  seenLogs = 0;
  initAgents();

  appendLog({ message: "Initializing RepoSense mission control...", level: "info" });

  try {
    const res = await fetch(`${API}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, execution_mode: mode }),
    });

    if (!res.ok) throw new Error("Backend unavailable");

    const { session_id } = await res.json();
    sessionId = session_id;
    appendLog({ message: `Session ${sessionId} — agents deploying`, level: "info" });

    pollTimer = setInterval(pollSession, 600);
    pollSession();
  } catch (err) {
    appendLog({
      message: "Cannot reach API — run: python server.py",
      level: "error",
    });
    simulateDemo(repoUrl, mode);
    $("analyzeBtn").disabled = false;
  }
}

function simulateDemo(repoUrl, mode) {
  const steps = [
    { agent: "DependencyAgent", state: "RUNNING", msg: "Cloning repository..." },
    { agent: "DependencyAgent", state: "THINKING", msg: "Parsing Python files..." },
    { agent: "DependencyAgent", state: "COMPLETED", msg: "Dependency graph built" },
    { agent: "SecurityAgent", state: "RUNNING", msg: "Heuristic scan active" },
    { agent: "SecurityAgent", state: "COMPLETED", msg: "Vulnerability detected in config.py" },
    { agent: "ImpactAgent", state: "COMPLETED", msg: "Blast radius computed" },
    { agent: "ExplanationAgent", state: "COMPLETED", msg: "Repository summary ready" },
    {
      agent: "FixAgent",
      state: mode === "approval" ? "REQUESTING_APPROVAL" : "COMPLETED",
      msg: "Patch recommendation generated",
    },
    { agent: "MonitorAgent", state: "COMPLETED", msg: "Orchestration complete" },
  ];

  const agents = {};
  AGENTS.forEach((a) => {
    agents[a] = { name: a, state: "IDLE", last_action: "" };
  });

  let i = 0;
  const timer = setInterval(() => {
    if (i >= steps.length) {
      clearInterval(timer);
      updateIntel({
        repo_type: "Flask Backend API",
        architecture: "Modular service-oriented backend",
        technologies: ["Python", "Flask"],
        complexity: "Medium",
        risk_level: "Moderate",
        purpose: `Demo mode for ${repoUrl} — start python server.py for live analysis.`,
      });
      renderGraph({
        nodes: [
          { id: "app.main" },
          { id: "app.auth" },
          { id: "app.api" },
        ],
        edges: [
          { source: "app.main", target: "app.auth" },
          { source: "app.api", target: "app.auth" },
        ],
      });
      return;
    }
    const s = steps[i];
    agents[s.agent] = { name: s.agent, state: s.state, last_action: s.msg };
    appendLog({ message: s.msg, level: "info" });
    updateAgents(agents);
    i++;
  }, 700);
}

async function runQuery() {
  const q = $("queryInput").value.trim();
  if (!q) return;
  if (!sessionId) {
    $("queryAnswer").textContent = "Start an analysis first.";
    return;
  }
  try {
    const res = await fetch(`${API}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, query: q }),
    });
    const data = await res.json();
    $("queryAnswer").textContent = data.answer || "No answer.";
  } catch {
    $("queryAnswer").textContent = "Query requires active backend session.";
  }
}

$("analyzeBtn").addEventListener("click", startAnalysis);
$("queryBtn").addEventListener("click", runQuery);
$("queryInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runQuery();
});

initAgents();
