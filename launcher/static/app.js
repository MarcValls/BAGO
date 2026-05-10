/* BAGO Command Center — app.js */

const API = 'http://localhost:7430';
let agentsData = [];
let launchHistory = JSON.parse(localStorage.getItem('bago_history') || '[]');
let pendingLaunch = null;          // { agent, models }
let lastRouteResult = null;        // Last routing decision
let currentMode = 'balanced';      // active routing mode
let sensitiveCallback = null;      // callback for confirmed sensitive action

// ─── Init ────────────────────────────────────────────────────────────────────

async function loadAll() {
  await Promise.all([
    loadAgents(),
    loadStatus(),
    loadRoutingHistory(),
    loadSessions(),
    loadIdeas(),
    loadLlmStatus(),
  ]);
  renderHistory();
  renderTimeline();
}

// ─── Tab navigation ──────────────────────────────────────────────────────────

function switchSidebar(tabId) {
  document.querySelectorAll('.stab').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
  document.querySelectorAll('.stab-panel').forEach(p => p.classList.toggle('active', p.id === tabId));
}

function switchMain(tabId) {
  document.querySelectorAll('.mtab').forEach(b => b.classList.toggle('active', b.dataset.tab === tabId));
  document.querySelectorAll('.mtab-panel').forEach(p => p.classList.toggle('active', p.id === tabId));
  if (tabId === 'm-cerebro') initCerebro();
}

// ─── Agents ──────────────────────────────────────────────────────────────────

async function loadAgents() {
  const grid = document.getElementById('agents-grid');
  try {
    const res  = await fetch(`${API}/api/agents`);
    agentsData = await res.json();
    grid.innerHTML = '';
    agentsData.forEach(a => grid.appendChild(buildCard(a)));
    renderSidebarAgents();
    updateHeaderAgentsBadge();
  } catch {
    grid.innerHTML = '<p style="color:var(--red);padding:20px">Error conectando con el servidor BAGO</p>';
  }
}

function updateHeaderAgentsBadge() {
  const available = agentsData.filter(a => a.available).length;
  const badge = document.getElementById('hdr-agents');
  badge.textContent = `${available}/${agentsData.length} agentes`;
  badge.className = `hdr-badge ${available > 0 ? 'badge-agents' : 'badge-err'}`;
}

function buildCard(agent) {
  const card = document.createElement('div');
  card.className = `agent-card ${agent.available ? 'available' : 'unavailable'}`;
  card.style.setProperty('--card-color', agent.color || 'var(--accent)');

  const models = agent.models.length
    ? agent.models.map(m => `<span class="model-tag">${m}</span>`).join('')
    : '';

  const reasonHtml = !agent.available
    ? `<div class="card-reason">⚠ ${agent.reason}</div>` : '';

  const installHtml = !agent.available
    ? `<div class="link-install"><a href="${agent.install_url}" target="_blank">Cómo instalar ↗</a></div>`
    : '';

  const strengthsMap = {
    ollama:  ['Privacidad total', 'Sin coste', 'Offline'],
    codex:   ['Edición multiarchivo', 'Ejecución comandos', 'Tests'],
    copilot: ['Revisión PR', 'Code review', 'Diff analysis'],
    claude:  ['Razonamiento largo', 'Documentación', 'Análisis'],
  };
  const strengths = (strengthsMap[agent.id] || []).map(s => `<span class="strength-tag">${s}</span>`).join('');

  card.innerHTML = `
    <div class="card-top">
      <span class="card-icon">${agent.icon}</span>
      <span class="dot ${agent.available ? 'dot-on' : 'dot-off'}"></span>
    </div>
    <div>
      <div class="card-name">${agent.name}</div>
      <div class="card-subtitle">${agent.subtitle}</div>
    </div>
    ${models ? `<div class="models-row">${models}</div>` : ''}
    ${strengths ? `<div class="strengths-row">${strengths}</div>` : ''}
    ${reasonHtml}
    <div class="card-footer">
      <button class="btn-launch"
        ${agent.available ? `onclick="openModal('${agent.id}')"` : 'disabled'}>
        ${agent.available ? '🚀 Iniciar' : 'No disponible'}
      </button>
      ${agent.available ? `<button class="btn-test" onclick="testAgent('${agent.id}')">🔍 Probar</button>` : ''}
      ${installHtml}
    </div>`;

  return card;
}

function renderSidebarAgents() {
  const list = document.getElementById('sidebar-agents');
  if (!agentsData.length) {
    list.innerHTML = '<span class="muted-text">Cargando…</span>';
    return;
  }
  list.innerHTML = agentsData.map(a => `
    <div class="sidebar-agent-card ${a.available ? 'sa-on' : 'sa-off'}">
      <span class="sa-icon">${a.icon}</span>
      <div class="sa-info">
        <div class="sa-name">${a.name}</div>
        <div class="sa-model">${a.active_model || (a.models[0] || '—')}</div>
      </div>
      <span class="dot ${a.available ? 'dot-on' : 'dot-off'}"></span>
    </div>`
  ).join('');
}

async function testAgent(agentId) {
  showToast(`🔍 Probando ${agentId}…`);
  // Route a simple test task to that agent
  try {
    const res  = await fetch(`${API}/api/route`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ task: `test ${agentId}` }),
    });
    const data = await res.json();
    showToast(`${agentId}: ${data.agent === agentId ? '✅ Seleccionado' : `→ ${data.agent}`}`);
  } catch {
    showToast('Error al probar agente', 'error');
  }
}

// ─── BAGO Status ─────────────────────────────────────────────────────────────

async function loadStatus() {
  try {
    const res  = await fetch(`${API}/api/status`);
    const data = await res.json();
    renderStatus(data);
  } catch {
    document.getElementById('status-panel').innerHTML =
      '<span class="muted-text">Error leyendo estado BAGO</span>';
  }
}

function renderStatus(s) {
  const panel = document.getElementById('status-panel');
  const badge = document.getElementById('hdr-health');

  if (s.error) {
    panel.innerHTML = `<span class="muted-text">${s.error}</span>`;
    badge.className = 'hdr-badge badge-err';
    badge.textContent = '⬡ error';
    return;
  }

  const score = parseInt(s.health);
  const badgeClass = score >= 80 ? 'badge-ok' : score >= 50 ? 'badge-warn' : 'badge-err';
  badge.className = `hdr-badge ${badgeClass}`;
  badge.textContent = `⬡ health ${score}/100`;

  // Mode badge
  const modeBadge = document.getElementById('hdr-mode');
  modeBadge.textContent = `⚙ ${s.mode || 'balanced'}`;

  const rows = [
    ['Versión',    s.version],
    ['Modo',       s.mode],
    ['Health',     `${s.health}/100`],
    ['Flujo',      s.active_flow || 'ninguno'],
    ['Ideas',      s.ideas_count ?? '?'],
    ['Proyecto',   s.project || '?'],
    ['Último W2',  s.last_w2 ? s.last_w2.slice(0, 28) + '…' : '?'],
    ['Actualizado', s.last_session ? s.last_session.slice(0, 10) : '?'],
  ];

  panel.innerHTML = `
    <h3 style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px">Estado BAGO</h3>
    ${rows.map(([k, v]) => `
      <div class="status-row">
        <span class="status-key">${k}</span>
        <span class="status-value">${v}</span>
      </div>`).join('')}`;
}

// ─── LLM Status ──────────────────────────────────────────────────────────────

async function loadLlmStatus() {
  try {
    const res  = await fetch(`${API}/api/llm/status`);
    const data = await res.json();
    renderLlmStatus(data);
  } catch {
    document.getElementById('llm-status-panel').innerHTML = '';
  }
}

function renderLlmStatus(s) {
  const panel = document.getElementById('llm-status-panel');
  const badge = document.getElementById('llm-model-badge');
  const statusColor = s.ollama_available ? 'var(--green)' : 'var(--red)';
  const statusText  = s.ollama_available ? '🟢 Ollama online' : '🔴 Ollama offline';

  if (badge) {
    badge.textContent = s.active_model || 'sin modelo';
    badge.className   = `hdr-badge ${s.ollama_available ? 'badge-ok' : 'badge-err'}`;
  }

  panel.innerHTML = `
    <div class="llm-panel-inner">
      <h3>LLM Local</h3>
      <div class="status-row"><span class="status-key">Estado</span><span class="status-value" style="color:${statusColor}">${statusText}</span></div>
      <div class="status-row"><span class="status-key">Modelo</span><span class="status-value">${s.active_model || '—'}</span></div>
      <div class="status-row"><span class="status-key">Servidor</span><span class="status-value" style="font-size:10px">${s.server_url}</span></div>
      ${s.ollama_models.length ? `<div class="models-row" style="margin-top:8px">${s.ollama_models.map(m => `<span class="model-tag">${m}</span>`).join('')}</div>` : ''}
    </div>`;
}

// ─── Pending task ─────────────────────────────────────────────────────────────

async function loadPendingTask() {
  try {
    const res  = await fetch(`${API}/api/task`);
    const data = await res.json();
    renderPendingTask(data);
  } catch {
    document.getElementById('pending-task-panel').innerHTML = '';
  }
}

function renderPendingTask(t) {
  const panel = document.getElementById('pending-task-panel');
  if (!t || t.status === 'none' || t.status === 'done' || t.error) {
    panel.innerHTML = '';
    return;
  }
  panel.innerHTML = `
    <div class="pending-task-inner">
      <h3>Tarea pendiente</h3>
      <div class="pending-task-title">${t.title || t.task || JSON.stringify(t)}</div>
      ${t.status ? `<div class="status-row"><span class="status-key">Estado</span><span class="status-value">${t.status}</span></div>` : ''}
    </div>`;
}

// ─── Routing History ─────────────────────────────────────────────────────────

async function loadRoutingHistory() {
  try {
    const res  = await fetch(`${API}/api/routing-history`);
    const data = await res.json();
    renderRoutingHistory(data);
  } catch {
    document.getElementById('routing-history-list').innerHTML =
      '<span class="muted-text">Error cargando historial</span>';
  }
}

function renderRoutingHistory(entries) {
  const list = document.getElementById('routing-history-list');
  if (!entries.length) {
    list.innerHTML = '<span class="muted-text">Sin historial de routing</span>';
    return;
  }
  list.innerHTML = `
    <h3 style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">Routing History</h3>
    ${entries.map(e => `
      <div class="rh-item">
        <div class="rh-task">${(e.task || e.input || '?').slice(0, 40)}…</div>
        <div class="rh-meta">
          <span class="rh-agent">${e.agent || e.recommended_agent || '?'}</span>
          <span class="rh-conf">${e.confidence || e.score || '?'}%</span>
          <span class="rh-time">${(e.timestamp || e.ts || '').slice(11, 16)}</span>
        </div>
      </div>`).join('')}`;
}

// ─── Sessions ────────────────────────────────────────────────────────────────

async function loadSessions() {
  try {
    const res  = await fetch(`${API}/api/sessions`);
    const data = await res.json();
    renderSessions(data);
  } catch {
    document.getElementById('sessions-list').innerHTML =
      '<span class="muted-text">Error cargando sesiones</span>';
  }
}

function renderSessions(sessions) {
  const list = document.getElementById('sessions-list');
  if (!sessions.length) {
    list.innerHTML = '<span class="muted-text">Sin sesiones registradas</span>';
    return;
  }
  list.innerHTML = sessions.map(s => {
    const title = s.title || s.workflow || s._file || 'Sesión';
    const date  = (s.started || s.timestamp || s.date || '').slice(0, 10);
    const status = s.status || s.state || '';
    return `
      <div class="session-item">
        <div class="session-title">${title}</div>
        <div class="session-meta">
          ${date ? `<span>${date}</span>` : ''}
          ${status ? `<span class="session-status">${status}</span>` : ''}
        </div>
      </div>`;
  }).join('');
}

// ─── Ideas ───────────────────────────────────────────────────────────────────

async function loadIdeas() {
  try {
    const res  = await fetch(`${API}/api/ideas`);
    const data = await res.json();
    renderIdeas(data);
  } catch {
    document.getElementById('ideas-list').innerHTML =
      '<span class="muted-text">Error cargando ideas</span>';
  }
}

function renderIdeas(ideas) {
  const list = document.getElementById('ideas-list');
  if (!ideas.length) {
    list.innerHTML = '<span class="muted-text">Sin ideas implementadas</span>';
    return;
  }
  list.innerHTML = ideas.map(i => {
    const title  = i.title || i.idea || JSON.stringify(i);
    const doneAt = (i.done_at || i.implemented_at || '').slice(0, 10);
    return `
      <div class="idea-item">
        <span class="idea-check">✓</span>
        <div class="idea-info">
          <div class="idea-title">${title}</div>
          ${doneAt ? `<div class="idea-date">${doneAt}</div>` : ''}
        </div>
      </div>`;
  }).join('');
}

// ─── Timeline ────────────────────────────────────────────────────────────────

async function renderTimeline() {
  const container = document.getElementById('timeline-events');
  try {
    const res     = await fetch(`${API}/api/routing-history`);
    const entries = await res.json();
    if (!entries.length) {
      container.innerHTML = '<span class="muted-text">Sin eventos recientes</span>';
      return;
    }
    container.innerHTML = entries.slice(0, 12).map(e => {
      const agentIcon = { ollama: '🦙', codex: '⚡', copilot: '🤖', claude: '🧠' }[e.agent] || '❓';
      const time = (e.timestamp || e.ts || '').slice(11, 16) || '—';
      const task = (e.task || e.input || '').slice(0, 30);
      const conf = e.confidence || e.score || '?';
      return `
        <div class="timeline-event">
          <span class="tl-icon">${agentIcon}</span>
          <span class="tl-task">${task}</span>
          <span class="tl-conf">${conf}%</span>
          <span class="tl-time">${time}</span>
        </div>`;
    }).join('');
  } catch {
    container.innerHTML = '<span class="muted-text">Sin eventos</span>';
  }
}

// ─── Dynamic routing ─────────────────────────────────────────────────────────

function selectMode(mode) {
  currentMode = mode;
  document.querySelectorAll('.mode-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.mode === mode);
  });
}

async function routeTask(forcedAgent = null) {
  const input  = document.getElementById('task-input');
  const task   = input.value.trim();
  const btn    = document.getElementById('btn-route');
  const result = document.getElementById('route-result');

  if (!task) { showToast('Escribe una tarea primero', 'error'); return; }

  btn.disabled   = true;
  btn.textContent = 'Analizando…';
  result.classList.add('hidden');
  document.getElementById('force-buttons').classList.add('hidden');

  try {
    const body = { task };
    if (forcedAgent) body.force_agent = forcedAgent;

    const res  = await fetch(`${API}/api/route`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(body),
    });
    const data = await res.json();
    lastRouteResult = data;
    renderRouteResult(data, task);
    updateRouterFlow(data);
    // Refresh timeline after routing
    renderTimeline();
  } catch {
    showToast('Error al analizar la tarea', 'error');
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Analizar →';
  }
}

async function forceAgent(agentId) {
  const task = document.getElementById('task-input').value.trim();
  if (!task) { showToast('Escribe una tarea primero', 'error'); return; }
  openModal(agentId, task);
}

function renderRouteResult(data, task) {
  const result = document.getElementById('route-result');
  result.classList.remove('hidden');

  if (!data.agent) {
    result.innerHTML = `<div class="route-card">
      <span style="color:var(--red)">⚠ ${data.reason || data.error || 'Sin agente disponible'}</span>
    </div>`;
    return;
  }

  const conf    = data.confidence || 50;
  const source  = data.decision_source || data.source || '—';
  const model   = data.model   || data.active_model || '—';
  const fallback = Array.isArray(data.fallback_chain)
    ? data.fallback_chain.join(' → ')
    : (data.fallback || '—');

  result.innerHTML = `
    <div class="route-card">
      <div class="route-left">
        <span class="route-emoji">${data.agent_icon || '🤖'}</span>
        <div>
          <div class="route-name">${data.agent_name || data.agent}</div>
          <div class="route-reason">${data.reason || '—'}</div>
          <div class="route-meta">
            <span class="route-badge">Modelo: ${model}</span>
            <span class="route-badge">Confianza: ${conf}%</span>
            <span class="route-badge">Fuente: ${source}</span>
          </div>
          ${fallback !== '—' ? `<div class="route-fallback">Fallback: ${fallback}</div>` : ''}
          <div class="confidence-bar">
            <div class="confidence-fill" style="width:${conf}%"></div>
          </div>
        </div>
      </div>
      <div class="route-actions">
        <button class="btn-primary" style="font-size:13px;padding:9px 16px"
          onclick="openModal('${data.agent}', '${(task || '').replace(/'/g, '')}', '${(data.model || '').replace(/'/g, '')}')">
          🚀 Iniciar ${data.agent_name || data.agent}
        </button>
        <button class="btn-secondary" style="font-size:12px;padding:8px 14px"
          onclick="showRouteJSON()">{ } JSON</button>
      </div>
    </div>`;

  // Show force buttons
  document.getElementById('force-buttons').classList.remove('hidden');
}

function showRouteJSON() {
  if (!lastRouteResult) return;
  const win = window.open('', '_blank', 'width=600,height=500');
  if (!win) return;
  const pre = win.document.createElement('pre');
  pre.style.cssText = 'background:#0d0f14;color:#e2e8f0;padding:20px;font-size:13px;margin:0;min-height:100vh';
  pre.textContent = JSON.stringify(lastRouteResult, null, 2);
  win.document.body.style.margin = '0';
  win.document.body.style.background = '#0d0f14';
  win.document.body.appendChild(pre);
}

// Update the router visual flow panel
function updateRouterFlow(data) {
  const guard   = document.getElementById('rf-guard-status');
  const cls     = document.getElementById('rf-classifier-status');
  const dec     = document.getElementById('rf-decision-status');

  guard.textContent = data.decision_source === 'hard_guardrail'
    ? '🔴 bloqueado' : '🟢 pasado';

  cls.textContent = data.decision_source === 'local_classifier'
    ? `✓ ${data.confidence || '?'}%` : '→ passthrough';

  dec.textContent = data.agent || '—';

  // Highlight selected agent node
  ['rf-ollama', 'rf-codex', 'rf-copilot'].forEach(id => {
    document.getElementById(id)?.classList.remove('rf-selected');
  });
  const targetId = 'rf-' + (data.agent || '');
  document.getElementById(targetId)?.classList.add('rf-selected');

  // Update details
  const details = document.getElementById('router-details');
  const content = document.getElementById('router-detail-content');
  details.classList.remove('hidden');
  const fields = [
    ['Agente',     data.agent_name || data.agent || '—'],
    ['Modelo',     data.model || data.active_model || '—'],
    ['Confianza',  `${data.confidence || '?'}%`],
    ['Fuente',     data.decision_source || data.source || '—'],
    ['Motivo',     data.reason || '—'],
    ['Fallback',   Array.isArray(data.fallback_chain) ? data.fallback_chain.join(' → ') : (data.fallback || '—')],
  ];
  content.innerHTML = fields.map(([k, v]) => `
    <div class="status-row">
      <span class="status-key">${k}</span>
      <span class="status-value">${v}</span>
    </div>`).join('');
}

// ─── BAGO Brain (Cerebro) ─────────────────────────────────────────────────────

let cerebroInitialized = false;

function initCerebro() {
  if (cerebroInitialized) return;
  cerebroInitialized = true;

  const canvas = document.getElementById('cerebro-canvas');
  const container = document.getElementById('cerebro-container');
  canvas.width  = container.clientWidth  || 700;
  canvas.height = container.clientHeight || 420;
  const ctx = canvas.getContext('2d');

  // Node definitions: { id, label, x, y, color, size }
  const W = canvas.width;
  const H = canvas.height;
  const nodes = [
    { id: 'bago',      label: 'BAGO',            x: W*0.5,  y: H*0.5,  color: '#4f8ef7', size: 30 },
    { id: 'estado',    label: 'Estado',           x: W*0.15, y: H*0.3,  color: '#b794f4', size: 18 },
    { id: 'ideas',     label: 'Ideas',            x: W*0.15, y: H*0.55, color: '#b794f4', size: 18 },
    { id: 'sesiones',  label: 'Sesiones',         x: W*0.15, y: H*0.75, color: '#b794f4', size: 18 },
    { id: 'llm',       label: 'LLM',              x: W*0.75, y: H*0.3,  color: '#3ecf8e', size: 22 },
    { id: 'ollama',    label: 'Ollama',           x: W*0.65, y: H*0.15, color: '#3ecf8e', size: 15 },
    { id: 'codex',     label: 'Codex',            x: W*0.82, y: H*0.12, color: '#3ecf8e', size: 15 },
    { id: 'copilot',   label: 'Copilot',          x: W*0.92, y: H*0.3,  color: '#3ecf8e', size: 15 },
    { id: 'workflows', label: 'Workflows',        x: W*0.75, y: H*0.7,  color: '#f6ad55', size: 18 },
    { id: 'tools',     label: 'Tools',            x: W*0.85, y: H*0.85, color: '#f6ad55', size: 18 },
    { id: 'proyecto',  label: 'Proyecto activo',  x: W*0.5,  y: H*0.18, color: '#4f8ef7', size: 18 },
    { id: 'router',    label: 'Router',           x: W*0.5,  y: H*0.78, color: '#f56565', size: 18 },
  ];

  const edges = [
    ['bago', 'estado'], ['bago', 'ideas'], ['bago', 'sesiones'],
    ['bago', 'llm'],    ['bago', 'workflows'], ['bago', 'proyecto'],
    ['bago', 'router'],
    ['llm',  'ollama'], ['llm', 'codex'], ['llm', 'copilot'],
    ['workflows', 'tools'],
    ['router', 'ollama'], ['router', 'codex'], ['router', 'copilot'],
  ];

  // Simple spring-layout animation
  let hoveredNode = null;
  let animFrame;

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'rgba(13,15,20,0)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw edges
    edges.forEach(([a, b]) => {
      const na = nodes.find(n => n.id === a);
      const nb = nodes.find(n => n.id === b);
      if (!na || !nb) return;
      ctx.beginPath();
      ctx.moveTo(na.x, na.y);
      ctx.lineTo(nb.x, nb.y);
      ctx.strokeStyle = 'rgba(42,48,69,0.8)';
      ctx.lineWidth   = 1.5;
      ctx.stroke();
    });

    // Draw nodes
    nodes.forEach(n => {
      const isHovered = hoveredNode === n;
      // Glow
      if (isHovered) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.size + 8, 0, Math.PI * 2);
        ctx.fillStyle = n.color + '33';
        ctx.fill();
      }
      // Circle
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.size, 0, Math.PI * 2);
      ctx.fillStyle   = n.color + (isHovered ? 'ff' : 'cc');
      ctx.fill();
      ctx.strokeStyle = n.color;
      ctx.lineWidth   = 2;
      ctx.stroke();
      // Label
      ctx.fillStyle  = '#e2e8f0';
      ctx.font       = `${isHovered ? 13 : 11}px -apple-system, sans-serif`;
      ctx.textAlign  = 'center';
      ctx.fillText(n.label, n.x, n.y + n.size + 14);
    });
    animFrame = requestAnimationFrame(draw);
  }

  draw();

  // Hover detection
  canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    hoveredNode = nodes.find(n => Math.hypot(n.x - mx, n.y - my) < n.size + 5) || null;
    canvas.style.cursor = hoveredNode ? 'pointer' : 'default';
  });
  canvas.addEventListener('mouseleave', () => { hoveredNode = null; });

  // Handle resize: update W/H to the current canvas size before repositioning
  new ResizeObserver(() => {
    cancelAnimationFrame(animFrame);
    const prevW = canvas.width;
    const prevH = canvas.height;
    canvas.width  = container.clientWidth  || prevW;
    canvas.height = container.clientHeight || prevH;
    if (prevW > 0 && prevH > 0) {
      nodes.forEach(n => {
        n.x = (n.x / prevW) * canvas.width;
        n.y = (n.y / prevH) * canvas.height;
      });
    }
    draw();
  }).observe(container);
}

// ─── LLM Chat ────────────────────────────────────────────────────────────────

async function sendLlmChat() {
  const input = document.getElementById('llm-chat-input');
  const msg   = input.value.trim();
  if (!msg) return;

  const messages = document.getElementById('llm-chat-messages');
  const btn      = document.getElementById('btn-llm-send');

  // Show user message using insertAdjacentHTML for better performance
  messages.insertAdjacentHTML('beforeend', `<div class="chat-bubble chat-user">${escHtml(msg)}</div>`);
  input.value = '';
  btn.disabled = true;
  btn.textContent = 'Enviando…';

  // Thinking indicator
  const thinkId = 'think-' + Date.now();
  messages.insertAdjacentHTML('beforeend', `<div class="chat-bubble chat-assistant thinking" id="${thinkId}">💭 Pensando…</div>`);
  messages.scrollTop = messages.scrollHeight;

  try {
    const res  = await fetch(`${API}/api/llm/chat`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ message: msg }),
    });
    const data = await res.json();
    document.getElementById(thinkId)?.remove();
    if (data.ok) {
      messages.insertAdjacentHTML('beforeend', `<div class="chat-bubble chat-assistant">${escHtml(data.response)}</div>`);
    } else {
      messages.insertAdjacentHTML('beforeend', `<div class="chat-bubble chat-error">❌ ${escHtml(data.error || 'Error al conectar')}</div>`);
    }
  } catch {
    document.getElementById(thinkId)?.remove();
    messages.insertAdjacentHTML('beforeend', `<div class="chat-bubble chat-error">❌ Error de conexión con Ollama</div>`);
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Enviar →';
    messages.scrollTop = messages.scrollHeight;
  }
}

function escHtml(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}

// ─── Modal (launch agent) ─────────────────────────────────────────────────────

function openModal(agentId, prefilledTask = '', prefilledModel = '') {
  const agent = agentsData.find(a => a.id === agentId);
  if (!agent || !agent.available) return;

  pendingLaunch = { agent };

  document.getElementById('modal-icon').textContent   = agent.icon;
  document.getElementById('modal-title').textContent  = agent.name;
  document.getElementById('modal-desc').textContent   =
    `Se abrirá una nueva Terminal con BAGO bootstrap para ${agent.subtitle}.`;

  const modelRow = document.getElementById('modal-model-row');
  const modelSel = document.getElementById('model-select');
  if (agent.models.length > 1) {
    modelSel.innerHTML = agent.models.map(m =>
      `<option value="${m}" ${m === prefilledModel ? 'selected' : ''}>${m}</option>`
    ).join('');
    modelRow.classList.remove('hidden');
  } else {
    modelRow.classList.add('hidden');
    modelSel.innerHTML = agent.models.map(m => `<option value="${m}">${m}</option>`).join('');
  }

  document.getElementById('modal-task-input').value = prefilledTask;
  document.getElementById('modal-overlay').classList.remove('hidden');
  document.getElementById('modal-task-input').focus();
  document.getElementById('btn-confirm').onclick = confirmLaunch;
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  pendingLaunch = null;
}

async function confirmLaunch() {
  if (!pendingLaunch) return;
  const { agent } = pendingLaunch;
  const model = document.getElementById('model-select').value;
  const task  = document.getElementById('modal-task-input').value.trim();

  const btn = document.getElementById('btn-confirm');
  btn.disabled    = true;
  btn.textContent = 'Abriendo terminal…';

  try {
    const res  = await fetch(`${API}/api/launch`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ agent: agent.id, model, task }),
    });
    const data = await res.json();
    if (data.ok) {
      closeModal();
      showToast(`✅ Terminal abierta con ${agent.name}`, 'success');
      addHistory(agent, model);
    } else {
      showToast(`Error: ${data.error}`, 'error');
    }
  } catch {
    showToast('Error de conexión con el servidor', 'error');
  } finally {
    btn.disabled    = false;
    btn.textContent = '🚀 Abrir Terminal';
  }
}

// ─── Sensitive action modal ───────────────────────────────────────────────────

function openSensitiveModal(warning, command, onConfirm) {
  document.getElementById('sensitive-warning').textContent = warning;
  document.getElementById('sensitive-cmd').textContent     = command;
  sensitiveCallback = onConfirm;
  document.getElementById('sensitive-modal').classList.remove('hidden');
  document.getElementById('btn-sensitive-confirm').onclick = () => {
    closeSensitiveModal();
    if (sensitiveCallback) sensitiveCallback();
  };
}

function closeSensitiveModal() {
  document.getElementById('sensitive-modal').classList.add('hidden');
  sensitiveCallback = null;
}

// ─── History ─────────────────────────────────────────────────────────────────

function addHistory(agent, model) {
  launchHistory.unshift({
    icon:  agent.icon,
    name:  agent.name,
    model: model || '',
    time:  new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
  });
  if (launchHistory.length > 8) launchHistory.pop();
  localStorage.setItem('bago_history', JSON.stringify(launchHistory));
  renderHistory();
}

function renderHistory() {
  const list = document.getElementById('history-list');
  if (!launchHistory.length) {
    list.innerHTML = '<span class="muted-text">Sin lanzamientos recientes</span>';
    return;
  }
  list.innerHTML = launchHistory.map(h => `
    <div class="history-item">
      <span class="h-icon">${h.icon}</span>
      <div style="flex:1;min-width:0">
        <div style="font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${h.name}</div>
        ${h.model ? `<div style="font-size:10px;color:var(--muted)">${h.model}</div>` : ''}
      </div>
      <span style="font-size:11px;color:var(--muted);flex-shrink:0">${h.time}</span>
    </div>`).join('');
}

// ─── Toast ───────────────────────────────────────────────────────────────────

function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className   = `show ${type}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = ''; }, 3200);
}

// ─── Event listeners ─────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Enter to route
  document.getElementById('task-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') routeTask();
  });
  // Enter to chat
  document.getElementById('llm-chat-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') sendLlmChat();
  });
  // Close modals on overlay click
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target.id === 'modal-overlay') closeModal();
  });
  document.getElementById('sensitive-modal').addEventListener('click', e => {
    if (e.target.id === 'sensitive-modal') closeSensitiveModal();
  });
});

// ─── Boot ────────────────────────────────────────────────────────────────────

loadAll();
