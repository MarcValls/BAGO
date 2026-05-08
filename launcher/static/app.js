/* BAGO Launcher — app.js */

const API = 'http://localhost:7430';
let agentsData = [];
let launchHistory = JSON.parse(localStorage.getItem('bago_history') || '[]');
let pendingLaunch = null;   // { agent, models }

// ─── Init ────────────────────────────────────────────────────────────────────

async function loadAll() {
  await Promise.all([loadAgents(), loadStatus()]);
  renderHistory();
}

// ─── Agents ──────────────────────────────────────────────────────────────────

async function loadAgents() {
  const grid = document.getElementById('agents-grid');
  try {
    const res  = await fetch(`${API}/api/agents`);
    agentsData = await res.json();
    grid.innerHTML = '';
    agentsData.forEach(a => grid.appendChild(buildCard(a)));
  } catch (e) {
    grid.innerHTML = '<p style="color:var(--red);padding:20px">Error conectando con el servidor BAGO</p>';
  }
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
    ${reasonHtml}
    <div class="card-footer">
      <button class="btn-launch"
        ${agent.available ? `onclick="openModal('${agent.id}')"` : 'disabled'}>
        ${agent.available ? '🚀 Iniciar' : 'No disponible'}
      </button>
      ${installHtml}
    </div>`;

  return card;
}

// ─── BAGO Status ─────────────────────────────────────────────────────────────

async function loadStatus() {
  try {
    const res  = await fetch(`${API}/api/status`);
    const data = await res.json();
    renderStatus(data);
  } catch (e) {
    document.getElementById('status-panel').innerHTML =
      '<span class="muted-text">Error leyendo estado BAGO</span>';
  }
}

function renderStatus(s) {
  const panel = document.getElementById('status-panel');
  const badge = document.getElementById('health-badge');

  if (s.error) {
    panel.innerHTML = `<span class="muted-text">${s.error}</span>`;
    badge.className = 'badge badge-err';
    badge.textContent = 'error';
    return;
  }

  const score = parseInt(s.health);
  const badgeClass = score >= 80 ? 'badge-ok' : score >= 50 ? 'badge-warn' : 'badge-err';
  badge.className = `badge ${badgeClass}`;
  badge.textContent = `⬡ health ${score}/100`;

  const rows = [
    ['Versión',    s.version],
    ['Modo',       s.mode],
    ['Health',     `${s.health}/100`],
    ['Flujo',      s.active_flow || 'ninguno'],
    ['Ideas',      s.ideas_count ?? '?'],
    ['Proyecto',   s.project || '?'],
    ['Último W2',  s.last_w2 ? s.last_w2.slice(0,28)+'…' : '?'],
    ['Actualizado',s.last_session ? s.last_session.slice(0,10) : '?'],
  ];

  panel.innerHTML = rows.map(([k, v]) =>
    `<div class="status-row">
      <span class="status-key">${k}</span>
      <span class="status-value">${v}</span>
    </div>`
  ).join('');
}

// ─── Dynamic routing ─────────────────────────────────────────────────────────

async function routeTask() {
  const input  = document.getElementById('task-input');
  const task   = input.value.trim();
  const btn    = document.getElementById('btn-route');
  const result = document.getElementById('route-result');

  if (!task) { showToast('Escribe una tarea primero', 'error'); return; }

  btn.disabled = true;
  btn.textContent = 'Analizando...';
  result.classList.add('hidden');

  try {
    const res  = await fetch(`${API}/api/route`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task }),
    });
    const data = await res.json();
    renderRouteResult(data, task);
  } catch (e) {
    showToast('Error al analizar la tarea', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<span>Analizar</span> →';
  }
}

function renderRouteResult(data, task) {
  const result = document.getElementById('route-result');
  result.classList.remove('hidden');

  if (!data.agent) {
    result.innerHTML = `<div class="route-card">
      <span style="color:var(--red)">⚠ ${data.reason}</span>
    </div>`;
    return;
  }

  const conf = data.confidence || 50;
  result.innerHTML = `
    <div class="route-card">
      <div class="route-left">
        <span class="route-emoji">${data.agent_icon}</span>
        <div>
          <div class="route-name">${data.agent_name}</div>
          <div class="route-reason">${data.reason}</div>
          <div class="confidence-bar">
            <div class="confidence-fill" style="width:${conf}%"></div>
          </div>
        </div>
      </div>
      <div class="route-actions">
        <button class="btn-primary" style="font-size:13px;padding:9px 16px"
          onclick="openModal('${data.agent}', '${(task||'').replace(/'/g,'')}', '${data.model||''}')">
          🚀 Iniciar ${data.agent_name}
        </button>
      </div>
    </div>`;
}

// Trigger on Enter
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('task-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') routeTask();
  });
});

// ─── Modal ───────────────────────────────────────────────────────────────────

function openModal(agentId, prefilledTask = '', prefilledModel = '') {
  const agent = agentsData.find(a => a.id === agentId);
  if (!agent || !agent.available) return;

  pendingLaunch = { agent };

  document.getElementById('modal-icon').textContent  = agent.icon;
  document.getElementById('modal-title').textContent = agent.name;
  document.getElementById('modal-desc').textContent  =
    `Se abrirá una nueva Terminal con BAGO bootstrap para ${agent.subtitle}.`;

  // Model select (only for ollama or multi-model)
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

  // Pre-fill task
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
  btn.disabled = true;
  btn.textContent = 'Abriendo terminal...';

  try {
    const res  = await fetch(`${API}/api/launch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agent: agent.id, model, task }),
    });
    const data = await res.json();
    if (data.ok) {
      closeModal();
      showToast(`✅ Terminal abierta con ${agent.name}`, 'success');
      addHistory(agent, model);
    } else {
      showToast(`Error: ${data.error}`, 'error');
    }
  } catch (e) {
    showToast('Error de conexión con el servidor', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 Abrir Terminal';
  }
}

// Close modal on overlay click
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target.id === 'modal-overlay') closeModal();
  });
});

// ─── History ─────────────────────────────────────────────────────────────────

function addHistory(agent, model) {
  launchHistory.unshift({
    icon: agent.icon,
    name: agent.name,
    model: model || '',
    time: new Date().toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' }),
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
  t.className = `show ${type}`;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.className = ''; }, 3200);
}

// ─── Boot ────────────────────────────────────────────────────────────────────

loadAll();
