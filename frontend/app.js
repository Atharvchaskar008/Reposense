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

const PHASE_LABELS = {
  queued: "Preparing analysis",
  cloning: "Cloning repository",
  analyzing: "Analyzing architecture",
  generating: "Running AI agents",
  completed: "Finalizing report",
  failed: "Execution interrupted",
};

const DEFAULT_SUMMARY = {
  repo_type: "General Software Project",
  architecture: "Architecture overview pending.",
  architecture_overview: "Architecture overview pending.",
  technologies: ["Unknown"],
  tech_stack: ["Unknown"],
  complexity: "Unknown",
  complexity_score: 0,
  risk_level: "Low",
  risk_summary: "No risk summary available yet.",
  purpose: "Repository analysis is being prepared.",
  repository_summary: "Repository analysis is being prepared.",
  security_insights: ["Security insights will appear during analysis."],
  maintainability_analysis: ["Maintainability analysis will appear during analysis."],
};

const DEFAULT_GITHUB = {
  full_name: "-",
  stars: 0,
  forks: 0,
  open_issues: 0,
  languages: ["Unknown"],
  description: "",
};

const DEFAULT_CODE_QUALITY = {
  score: 0,
  grade: "N/A",
  insights: [],
};

const DEFAULT_MAINTAINABILITY = {
  score: 0,
  grade: "N/A",
  insights: [],
};

let sessionId = null;
let eventSource = null;
let reconnectTimer = null;
let reconnectAttempts = 0;
let sessionFinished = false;
let logCursor = 0;
let latestState = null;
let activePollTimer = null;
let lastGithubName = "";
const seenLogs = new Set();

const $ = (id) => document.getElementById(id);

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function toArray(value, fallback = []) {
  return Array.isArray(value) ? value : fallback;
}

function asText(value, fallback = "-") {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

function asNumber(value, fallback = 0) {
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;");
}

function stateClass(state) {
  return asText(state, "IDLE").toLowerCase().replace(/\s+/g, "_");
}

function setSectionLoading(isLoading) {
  document.querySelectorAll(".panel").forEach((panel) => {
    panel.classList.toggle("is-loading", isLoading);
  });
}

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

function normalizeSummary(summary) {
  const safe = isPlainObject(summary) ? summary : {};
  const techStack = toArray(safe.tech_stack || safe.technologies, ["Unknown"])
    .map((item) => asText(item, "Unknown"))
    .filter(Boolean);
  const securityInsights = toArray(safe.security_insights, [])
    .map((item) => asText(item))
    .filter(Boolean);
  const maintainabilityInsights = toArray(safe.maintainability_analysis, [])
    .map((item) => asText(item))
    .filter(Boolean);

  return {
    ...DEFAULT_SUMMARY,
    ...safe,
    repo_type: asText(safe.repo_type, DEFAULT_SUMMARY.repo_type),
    architecture: asText(
      safe.architecture || safe.architecture_overview,
      DEFAULT_SUMMARY.architecture
    ),
    architecture_overview: asText(
      safe.architecture_overview || safe.architecture,
      DEFAULT_SUMMARY.architecture_overview
    ),
    technologies: techStack.length ? techStack : DEFAULT_SUMMARY.technologies,
    tech_stack: techStack.length ? techStack : DEFAULT_SUMMARY.tech_stack,
    complexity: asText(safe.complexity, DEFAULT_SUMMARY.complexity),
    complexity_score: asNumber(safe.complexity_score, 0),
    risk_level: asText(safe.risk_level, DEFAULT_SUMMARY.risk_level),
    risk_summary: asText(safe.risk_summary, DEFAULT_SUMMARY.risk_summary),
    purpose: asText(safe.purpose || safe.repository_summary, DEFAULT_SUMMARY.purpose),
    repository_summary: asText(
      safe.repository_summary || safe.purpose,
      DEFAULT_SUMMARY.repository_summary
    ),
    security_insights: securityInsights.length
      ? securityInsights
      : DEFAULT_SUMMARY.security_insights,
    maintainability_analysis: maintainabilityInsights.length
      ? maintainabilityInsights
      : DEFAULT_SUMMARY.maintainability_analysis,
  };
}

function normalizeGithub(github) {
  const safe = isPlainObject(github) ? github : {};
  const languages = toArray(safe.languages, [])
    .map((item) => asText(item, "Unknown"))
    .filter(Boolean);
  return {
    ...DEFAULT_GITHUB,
    ...safe,
    full_name: asText(safe.full_name, DEFAULT_GITHUB.full_name),
    stars: asNumber(safe.stars, DEFAULT_GITHUB.stars),
    forks: asNumber(safe.forks, DEFAULT_GITHUB.forks),
    open_issues: asNumber(safe.open_issues, DEFAULT_GITHUB.open_issues),
    languages: languages.length ? languages : DEFAULT_GITHUB.languages,
    description: asText(safe.description, DEFAULT_GITHUB.description),
  };
}

function normalizeMetric(metric, defaults) {
  const safe = isPlainObject(metric) ? metric : {};
  return {
    ...defaults,
    ...safe,
    score: asNumber(safe.score, defaults.score),
    grade: asText(safe.grade, defaults.grade),
    insights: toArray(safe.insights, defaults.insights)
      .map((item) => asText(item))
      .filter(Boolean),
  };
}

function normalizeRecommendations(recommendations, summary) {
  const direct = toArray(recommendations, [])
    .map((item) => asText(item))
    .filter(Boolean);
  if (direct.length) return direct;

  const fallback = [
    ...toArray(summary.security_insights, []),
    ...toArray(summary.maintainability_analysis, []),
  ]
    .map((item) => asText(item))
    .filter(Boolean);

  return fallback.length ? fallback.slice(0, 5) : ["Analysis completed with fallback data."];
}

function normalizeApprovals(approvals) {
  return toArray(approvals, [])
    .filter((approval) => isPlainObject(approval))
    .map((approval) => ({
      ...approval,
      id: asText(approval.id, ""),
      agent: asText(approval.agent, "Agent"),
      question: asText(approval.question, "Approval requested"),
      file: asText(approval.file, "unknown file"),
      line: asText(approval.line, "?"),
      recommendation: asText(approval.recommendation, "No recommendation provided."),
      fix_preview: asText(approval.fix_preview, "No patch preview available."),
      status: asText(approval.status, "pending"),
    }));
}

function normalizeFixes(fixes) {
  return toArray(fixes, [])
    .filter((fix) => isPlainObject(fix))
    .map((fix) => ({
      title: asText(fix.title, "Suggested patch"),
      file: asText(fix.file, "unknown file"),
      line: asText(fix.line, ""),
      diff: asText(fix.diff, "No patch preview available."),
      reasoning: asText(fix.reasoning, "Patch reasoning unavailable."),
    }));
}

function normalizeGraph(graph) {
  const safe = isPlainObject(graph) ? graph : {};
  const nodes = toArray(safe.nodes, [])
    .filter((node) => isPlainObject(node) && node.id)
    .map((node) => ({
      id: asText(node.id),
      path: asText(node.path, asText(node.id)),
      has_issue: !!node.has_issue,
      imports: asNumber(toArray(node.imports, []).length, 0),
    }));
  const validIds = new Set(nodes.map((node) => node.id));
  const edges = toArray(safe.edges, [])
    .filter((edge) => isPlainObject(edge) && validIds.has(edge.source) && validIds.has(edge.target))
    .map((edge) => ({
      source: asText(edge.source),
      target: asText(edge.target),
      type: asText(edge.type, "imports_edge"),
    }));
  return { nodes, edges };
}

function buildFallbackGraph(data = latestState) {
  const activeAgents = toArray(data?.active_agents, []).filter((agent) => isPlainObject(agent));
  if (activeAgents.length) {
    const nodes = activeAgents.map((agent, index) => ({
      id: `agent.${index}.${asText(agent.name, "agent").toLowerCase()}`,
      path: asText(agent.action || agent.state, "Working"),
      has_issue: false,
      active: true,
    }));
    const edges = nodes.slice(1).map((node, index) => ({
      source: nodes[index].id,
      target: node.id,
      type: "agent_flow",
    }));
    return { nodes, edges };
  }

  const summary = normalizeSummary(data?.summary);
  const stack = toArray(summary.tech_stack, ["Unknown"]).slice(0, 4);
  const nodes = [
    { id: "repo.core", path: summary.repo_type, has_issue: false, active: true },
    { id: "repo.arch", path: summary.architecture_overview, has_issue: false, active: false },
    ...stack.map((item, index) => ({
      id: `repo.tech.${index}`,
      path: item,
      has_issue: false,
      active: false,
    })),
  ];
  const edges = nodes.slice(1).map((node) => ({
    source: "repo.core",
    target: node.id,
    type: "fallback",
  }));
  return { nodes, edges };
}

function appendLog(entry) {
  const safeEntry = isPlainObject(entry) ? entry : { message: asText(entry, "Unknown log entry") };
  const key = `${safeEntry.ts || ""}|${safeEntry.agent || ""}|${safeEntry.message || safeEntry.display || ""}`;
  if (seenLogs.has(key)) return;
  seenLogs.add(key);
  if (seenLogs.size > 500) {
    const first = seenLogs.values().next().value;
    seenLogs.delete(first);
  }

  const stream = $("logStream");
  const line = document.createElement("div");
  const agent = safeEntry.agent ? `[${safeEntry.agent}] ` : "";
  line.className = `log-line ${asText(safeEntry.level, "info")}`;
  line.textContent = safeEntry.display
    ? `> ${safeEntry.display}`
    : `> ${agent}${asText(safeEntry.message, "Unknown log entry")}`;
  stream.appendChild(line);
  while (stream.children.length > 180) {
    stream.removeChild(stream.firstChild);
  }
  stream.scrollTop = stream.scrollHeight;
}

function updateAgents(agents) {
  const safeAgents = isPlainObject(agents) ? agents : {};
  AGENTS.forEach((name) => {
    const card = document.getElementById(`agent-${name}`);
    if (!card) return;
    const data = isPlainObject(safeAgents[name]) ? safeAgents[name] : {};
    const state = asText(data.state, "IDLE");
    card.className = `agent-card ${stateClass(state)}`;
    if (["RUNNING", "THINKING"].includes(state)) card.classList.add("running");
    card.querySelector("[data-state]").textContent = state;
    card.querySelector("[data-action]").textContent = asText(data.last_action, "Standing by");
    card.querySelector("[data-dot]").className = `status-dot ${stateClass(state)}`;
  });
}

function updateGithub(github) {
  const safeGithub = normalizeGithub(github);
  $("intelRepo").textContent = safeGithub.full_name;
  $("intelStars").textContent = `${safeGithub.stars} / ${safeGithub.forks} / ${safeGithub.open_issues}`;
  if (safeGithub.full_name !== "-" && safeGithub.full_name !== lastGithubName) {
    lastGithubName = safeGithub.full_name;
    if (safeGithub.description) {
      appendLog({ message: safeGithub.description, level: "info", agent: "DependencyAgent" });
    }
  }
}

function updateIntel(summary, github, codeQuality, recommendations, maintainability) {
  const safeSummary = normalizeSummary(summary);
  const safeGithub = normalizeGithub(github);
  const safeCodeQuality = normalizeMetric(codeQuality, DEFAULT_CODE_QUALITY);
  const safeMaintainability = normalizeMetric(maintainability, DEFAULT_MAINTAINABILITY);
  const safeRecommendations = normalizeRecommendations(recommendations, safeSummary);

  updateGithub(safeGithub);

  $("intelType").textContent = safeSummary.repo_type;
  $("intelArch").textContent = safeSummary.architecture_overview;
  $("intelTech").textContent = safeSummary.tech_stack.join(", ");
  $("intelComplexity").textContent = safeSummary.complexity_score
    ? `${safeSummary.complexity} (${safeSummary.complexity_score}/100)`
    : safeSummary.complexity;
  $("intelRisk").textContent = safeSummary.risk_level;
  $("intelRisk").className = `risk-badge ${safeSummary.risk_level.toLowerCase()}`;
  $("intelPurpose").textContent = safeSummary.repository_summary;

  const qualityBase =
    safeCodeQuality.grade !== "N/A"
      ? `${safeCodeQuality.grade} (${safeCodeQuality.score}/100)`
      : "Code quality pending";
  $("intelQuality").textContent =
    safeMaintainability.grade !== "N/A"
      ? `${qualityBase} | Maintainability ${safeMaintainability.grade} (${safeMaintainability.score}/100)`
      : qualityBase;

  $("intelRecs").innerHTML = safeRecommendations
    .map((recommendation) => `<li>${escapeHtml(recommendation)}</li>`)
    .join("");
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
  if (!isPlainObject(data)) return PHASE_LABELS.queued;
  if (data.phase) return asText(data.phase, PHASE_LABELS.queued);
  const lifecycle = asText(data.lifecycle || data.status, "queued");
  const progress = asNumber(data.progress, 0);
  if (lifecycle === "generating" && progress >= 88) return "Finalizing report";
  if (lifecycle === "generating") return "Generating recommendations";
  if (lifecycle === "analyzing" && progress >= 55) return "Running AI agents";
  return PHASE_LABELS[lifecycle] || "Preparing analysis";
}

function updatePhase(data) {
  $("missionPhase").textContent = derivePhase(data);
}

function updateAgentTicker(data) {
  const ticker = $("agentTicker");
  const activeAgents = toArray(data?.active_agents, []).filter((agent) => isPlainObject(agent));
  if (activeAgents.length) {
    ticker.textContent = activeAgents
      .map((agent) => `${asText(agent.name, "Agent")}: ${asText(agent.action || agent.state, "Working")}`)
      .join("  •  ");
    ticker.classList.add("is-live");
    return;
  }

  const status = asText(data?.status, "queued");
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
  const safeApprovals = normalizeApprovals(approvals);
  const box = $("approvalConsole");
  const pending = safeApprovals.filter((approval) => approval.status === "pending");
  if (!pending.length) {
    box.innerHTML = safeApprovals.length
      ? `<p class="muted">All supervisor approvals resolved.</p>`
      : `<p class="muted">Supervisor approvals appear when agents request critical actions.</p>`;
    return;
  }

  box.innerHTML = "";
  pending.forEach((approval) => {
    const card = document.createElement("div");
    card.className = "approval-card";
    card.innerHTML = `
      <h4>${escapeHtml(approval.agent)}: ${escapeHtml(approval.question)}</h4>
      <p class="muted">${escapeHtml(approval.file)}:${approval.line}</p>
      <p>${escapeHtml(approval.recommendation)}</p>
      <pre>${escapeHtml(approval.fix_preview)}</pre>
      <div class="approval-actions">
        <button class="approve" data-id="${approval.id}" data-act="approve">Approve</button>
        <button class="reject" data-id="${approval.id}" data-act="reject">Reject</button>
        <button data-id="${approval.id}" data-act="why">Ask Why</button>
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
  const safeFixes = normalizeFixes(fixes);
  const list = $("fixesList");
  if (!safeFixes.length) {
    list.innerHTML = `<p class="muted">Patches appear after security remediation tasks complete.</p>`;
    return;
  }

  list.innerHTML = safeFixes
    .map(
      (fix) => `
    <div class="fix-card">
      <strong>${escapeHtml(fix.title)}</strong>
      <p class="muted">${escapeHtml(fix.file)}:${fix.line}</p>
      <pre>${escapeHtml(fix.diff)}</pre>
      <p class="muted">${escapeHtml(fix.reasoning)}</p>
    </div>`
    )
    .join("");
}

function renderGraph(graph) {
  const svg = $("graphSvg");
  const safeGraph = normalizeGraph(graph);
  const graphPayload = safeGraph.nodes.length ? safeGraph : buildFallbackGraph();
  const nodes = toArray(graphPayload.nodes, []);
  const edges = toArray(graphPayload.edges, []);
  const activeAgentNames = new Set(
    toArray(latestState?.active_agents, [])
      .map((agent) => asText(agent.name, "").toLowerCase())
      .filter(Boolean)
  );

  if (!nodes.length) {
    svg.innerHTML = `
      <rect x="0" y="0" width="600" height="280" rx="18" class="graph-backdrop"/>
      <text x="24" y="40" class="graph-empty-title">AI orchestration canvas warming up</text>
      <text x="24" y="62" class="graph-empty-copy">Repository topology will appear as soon as dependency analysis starts.</text>
    `;
    return;
  }

  const width = 600;
  const height = 280;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) * 0.34;
  const positions = {};
  const visibleNodes = nodes.slice(0, 18);

  const defs = `
    <defs>
      <linearGradient id="graphEdgeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="rgba(38,38,38,0.45)"/>
        <stop offset="50%" stop-color="rgba(237,237,237,0.32)"/>
        <stop offset="100%" stop-color="rgba(38,38,38,0.45)"/>
      </linearGradient>
      <filter id="graphNodeGlow" x="-60%" y="-60%" width="220%" height="220%">
        <feDropShadow dx="0" dy="0" stdDeviation="6" flood-color="rgba(78,168,255,0.22)"/>
      </filter>
      <filter id="graphNodePurpleGlow" x="-60%" y="-60%" width="220%" height="220%">
        <feDropShadow dx="0" dy="0" stdDeviation="6" flood-color="rgba(164,123,255,0.2)"/>
      </filter>
    </defs>
  `;

  visibleNodes.forEach((node, index) => {
    const angleOffset = visibleNodes.length % 2 === 0 ? Math.PI / 18 : 0;
    const angle = (index / Math.max(visibleNodes.length, 1)) * Math.PI * 2 - Math.PI / 2 + angleOffset;
    const depth = 1 + ((index % 3) * 0.06);
    positions[node.id] = {
      x: centerX + radius * depth * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
      has_issue: !!node.has_issue,
      active:
        !!node.active ||
        activeAgentNames.has(idToAgentName(node.id)) ||
        activeAgentNames.has(asText(node.path, "").toLowerCase()),
      path: node.path,
    };
  });

  const edgeSvg = edges
    .slice(0, 30)
    .map((edge) => {
      const source = positions[edge.source];
      const target = positions[edge.target];
      if (!source || !target) return "";
      return `
        <line class="graph-edge" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}"/>
        <line class="graph-edge graph-edge-animated" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}"/>
      `;
    })
    .join("");

  const nodeSvg = Object.entries(positions)
    .map(([id, point]) => {
      const primary = id.split(".").pop().slice(0, 12);
      const secondary = asText(point.path, "").split("/").pop().split(".").slice(-1)[0].slice(0, 16);
      const nodeClass = [
        "graph-node-card",
        point.has_issue ? "issue" : "",
        point.active ? "active" : "",
      ]
        .filter(Boolean)
        .join(" ");
      return `
        <g class="graph-node-group ${point.active ? "active" : ""}" transform="translate(${point.x}, ${point.y})">
          <rect class="${nodeClass}" x="-56" y="-20" width="112" height="40" rx="12"/>
          <text class="graph-label" x="0" y="-2" text-anchor="middle">${escapeHtml(primary)}</text>
          <text class="graph-sub-label" x="0" y="12" text-anchor="middle">${escapeHtml(secondary || "module")}</text>
        </g>
      `;
    })
    .join("");

  svg.innerHTML = `
    ${defs}
    <rect x="0" y="0" width="600" height="280" rx="18" class="graph-backdrop"/>
    ${edgeSvg}
    ${nodeSvg}
  `;
}

function idToAgentName(id) {
  return asText(id, "")
    .split(".")
    .pop()
    .replace(/[_-]/g, " ")
    .toLowerCase();
}

function applyState(data) {
  try {
    const safeData = isPlainObject(data) ? data : {};
    latestState = safeData;
    if (typeof safeData.log_count === "number") {
      logCursor = Math.max(logCursor, safeData.log_count);
    }

    updateAgents(isPlainObject(safeData.agents) ? safeData.agents : {});
    updatePhase(safeData);
    updateAgentTicker(safeData);
    updateIntel(
      safeData.summary,
      safeData.github,
      safeData.code_quality,
      safeData.recommendations,
      safeData.maintainability
    );
    renderApprovals(safeData.approvals);
    renderFixes(safeData.fixes);
    renderGraph(safeData.graph);

    const progress = asNumber(safeData.progress, 0);
    if (progress && safeData.status !== "completed" && safeData.status !== "failed") {
      $("analyzeBtn").innerHTML =
        `<span class="btn-spinner" aria-hidden="true"></span><span>Executing ${progress}%</span>`;
    }

    if (safeData.status === "completed" || safeData.status === "failed") {
      sessionFinished = true;
      setAnalyzeLoading(false);
      setSectionLoading(false);
      setConnectionStatus(
        "connected",
        safeData.status === "completed" ? "Stream complete" : "Stream closed"
      );
      stopSessionPolling();
    }
  } catch (error) {
    appendLog({
      message: `UI recovered from malformed dashboard data: ${error.message}`,
      level: "warn",
      agent: "MonitorAgent",
    });
    setSectionLoading(false);
  }
}

async function pollSessionState() {
  if (!sessionId) return;
  try {
    const res = await fetch(`${API}/session/${sessionId}`);
    if (!res.ok) return;
    const data = await res.json();
    applyState(data);
  } catch (error) {
    appendLog({
      message: `Session refresh failed: ${error.message}`,
      level: "warn",
      agent: "MonitorAgent",
    });
  }
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

    if (msg.type === "log" && isPlainObject(msg.data)) {
      logCursor += 1;
      appendLog(msg.data);
    } else if (msg.type === "state") {
      applyState(msg.data);
    } else if (msg.type === "done") {
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
      setSectionLoading(false);
      setConnectionStatus("connected", "Stream complete");
      eventSource.close();
    } else if (msg.type === "error") {
      appendLog({ message: asText(msg.data?.message, "Stream error"), level: "error" });
      setConnectionStatus("error");
      eventSource.close();
      scheduleReconnect();
    }
  };

  eventSource.onerror = () => {
    if (sessionFinished) {
      setConnectionStatus("connected", "Stream complete");
      setSectionLoading(false);
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
  setSectionLoading(true);
  setConnectionStatus("connecting");
  $("logStream").innerHTML = "";
  lastGithubName = "";
  initAgents();
  updatePhase({ lifecycle: "queued" });
  updateAgentTicker({ status: "queued" });
  updateIntel({}, {}, {}, [], {});
  renderApprovals([]);
  renderFixes([]);
  renderGraph({});
  appendLog({ message: "Initializing graph-native mission control", agent: "MonitorAgent" });

  try {
    const res = await fetch(`${API}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_url: repoUrl, execution_mode: mode }),
    });
    const body = await res.json();
    if (!res.ok) throw new Error(body?.error || "Analysis failed to start");

    sessionId = body.session_id;
    appendLog({ message: `Session ${sessionId} - agents deploying`, agent: "MonitorAgent" });
    connectSSE();
  } catch (error) {
    appendLog({
      message: `Backend unavailable: ${error.message}. Run: python server.py`,
      level: "error",
    });
    setAnalyzeLoading(false);
    setSectionLoading(false);
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
  try {
    const res = await fetch(`${API}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, query: q, message: q }),
    });
    const data = await res.json();
    $("queryAnswer").textContent = asText(data?.answer, "No answer.");
  } catch (error) {
    $("queryAnswer").textContent = `Query unavailable: ${error.message}`;
  }
}

$("analyzeBtn").addEventListener("click", startAnalysis);
$("queryBtn").addEventListener("click", runQuery);
$("queryInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") runQuery();
});

initAgents();
setSectionLoading(false);
updateIntel({}, {}, {}, [], {});
renderApprovals([]);
renderFixes([]);
renderGraph({});
