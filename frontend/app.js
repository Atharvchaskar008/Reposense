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
    card.className = `agent-card ${["RUNNING", "THINKING"].includes(st) ? "running" : ""}`;
    card.querySelector("[data-state]").textContent = st;
    card.querySelector("[data-action]").textContent = data.last_action || "-";
    card.querySelector("[data-dot]").className = `status-dot ${stateClass(st)}`;
  });
}

function appendLog(entry) {
  const stream = $("logStream");
  const line = document.createElement("div");
  const agent = entry.agent ? `[${entry.agent}] ` : "";
  line.className = `log-line ${entry.level || "info"}`;
  line.textContent = entry.display ? `> ${entry.display}` : `> ${agent}${entry.message}`;
  stream.appendChild(line);
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
    $("intelType").textContent = summary.repo_type || "-";
    $("intelArch").textContent = summary.architecture || "-";
    const langs = summary.technologies || (github && github.languages) || [];
    $("intelTech").textContent = Array.isArray(langs) ? langs.join(", ") : langs;
    $("intelComplexity").textContent = summary.complexity || "-";
    const risk = $("intelRisk");
    risk.textContent = summary.risk_level || "-";
    risk.className = `risk-badge ${(summary.risk_level || "").toLowerCase()}`;
    $("intelPurpose").textContent =
      summary.purpose || summary.risk_summary || "Analysis complete.";
  }
  if (codeQuality && Object.keys(codeQuality).length && !maintainability?.grade) {
    $("intelQuality").textContent = `${codeQuality.grade} (${codeQuality.score}/100)`;
  }
  if (recommendations && recommendations.length) {
    $("intelRecs").innerHTML = recommendations
      .map((r) => `<li>${escapeHtml(r)}</li>`)
      .join("");
  }
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
  updateAgents(data.agents);
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
  const btn = $("analyzeBtn");
  if (data.progress) btn.textContent = `Executing ${data.progress}%`;
  if (data.status === "completed" || data.status === "failed") {
    btn.textContent = "Start Analysis";
    btn.disabled = false;
  }
}

function connectSSE() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource(`${API}/stream/${sessionId}`);

  eventSource.onmessage = (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    if (msg.type === "log" && msg.data) appendLog(msg.data);
    else if (msg.type === "state" && msg.data) applyState(msg.data);
    else if (msg.type === "done") {
      appendLog({
        message:
          msg.data?.status === "completed"
            ? "Autonomous execution complete"
            : "Execution failed",
        level: msg.data?.status === "completed" ? "info" : "error",
        agent: "MonitorAgent",
      });
      $("analyzeBtn").disabled = false;
      $("analyzeBtn").textContent = "Start Analysis";
      eventSource.close();
    } else if (msg.type === "error") {
      appendLog({ message: msg.data?.message || "Stream error", level: "error" });
      $("analyzeBtn").disabled = false;
      eventSource.close();
    }
  };

  eventSource.onerror = () => {
    appendLog({
      message: "SSE connection lost. Run: python server.py and open http://localhost:8000",
      level: "error",
    });
    $("analyzeBtn").disabled = false;
    eventSource.close();
  };
}

async function startAnalysis() {
  const repoUrl = $("repoInput").value.trim();
  const mode = $("executionMode").value;
  if (!repoUrl) {
    alert("Enter a public GitHub repository URL.");
    return;
  }

  $("analyzeBtn").disabled = true;
  $("analyzeBtn").textContent = "Executing...";
  $("logStream").innerHTML = "";
  lastGithubName = "";
  initAgents();
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
    $("analyzeBtn").disabled = false;
    $("analyzeBtn").textContent = "Start Analysis";
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
