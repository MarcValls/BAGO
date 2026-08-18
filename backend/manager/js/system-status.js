// system-status.js — Pestaña Estado del Sistema del BAGO Manager v1

function pmSystemBadge(text, ok) {
  const cls = ok ? 'badge-on' : 'badge-off';
  return '<span class="pm-badge ' + cls + '">' + escapeHtml(text) + '</span>';
}

async function pmLoadSystemStatus() {
  const api = electronApi();
  const caption = document.getElementById('pm-system-caption');
  const statusBox = document.getElementById('pm-system-status');
  const healthBox = document.getElementById('pm-system-health');

  caption.textContent = 'Cargando estado…';
  statusBox.innerHTML = '<div style="padding:12px;color:#718198;font-size:12px;">Consultando supervisor…</div>';
  healthBox.innerHTML = '<div style="padding:12px;color:#718198;font-size:12px;">Consultando health checks…</div>';

  let supervisorData = null;
  let supervisorErr = '';
  let healthData = null;
  let healthErr = '';

  if (!api || (!api.runSupervisorCommand && !api.managerHealth)) {
    statusBox.innerHTML = '<div style="padding:12px;color:#fbbf24;font-size:12px;">Estado del sistema no disponible sin Electron/backend operativo.</div>';
    caption.textContent = 'Sistema no disponible';
    healthBox.innerHTML = '<div style="padding:12px;color:#fbbf24;font-size:12px;">Health checks no disponibles sin Electron/backend operativo.</div>';
    return;
  }

  // Supervisor status
  try {
    if (api && api.runSupervisorCommand) {
      const res = await api.runSupervisorCommand(['status', '--json']);
      if (res && res.ok && res.data) {
        supervisorData = res.data;
      } else if (res && res.ok && res.text) {
        supervisorData = { text: res.text };
      } else {
        supervisorErr = 'Respuesta inesperada del supervisor';
      }
    } else {
      supervisorErr = 'API no disponible (¿no estás en Electron?)';
    }
  } catch (e) {
    supervisorErr = e.message || 'Error desconocido';
  }

  // Manager health
  try {
    if (api && api.managerHealth) {
      healthData = await api.managerHealth();
    } else {
      healthErr = 'API no disponible';
    }
  } catch (e) {
    healthErr = e.message || 'Error desconocido';
  }

  // Render supervisor
  if (supervisorErr) {
    statusBox.innerHTML = '<div style="padding:12px;color:#fb7185;font-size:12px;">' + escapeHtml(supervisorErr) + '</div>';
    caption.textContent = 'Supervisor no disponible';
  } else if (supervisorData) {
    const alive = supervisorData.alive || supervisorData.running || false;
    const pid = supervisorData.pid || '—';
    const uptime = supervisorData.uptime || supervisorData.started || '—';
    const version = supervisorData.version || '—';
    const events = supervisorData.events || 0;
    const lastEvent = supervisorData.last_event || '—';

    const rows = [
      ['Estado', alive ? 'Activo · corriendo' : 'Detenido / no detectado', alive],
      ['PID', String(pid), !!pid],
      ['Uptime', String(uptime), !!alive],
      ['Versión', String(version), !!version],
      ['Eventos', String(events), true],
      ['Último evento', String(lastEvent), lastEvent !== '—'],
    ];

    statusBox.innerHTML = rows.map(r => {
      return '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:1px solid #1e293b;font-size:12px;">' +
        '<span style="color:#94a3b8;">' + escapeHtml(r[0]) + '</span>' +
        '<span style="color:#e2e8f0;font-family:JetBrains Mono,monospace;">' + pmSystemBadge(r[1], r[2]) + '</span>' +
        '</div>';
    }).join('');

    caption.textContent = alive
      ? 'Supervisor activo · PID ' + pid + ' · ' + uptime
      : 'Supervisor detenido. Usa Reiniciar para arrancarlo.';
  } else {
    statusBox.innerHTML = '<div style="padding:12px;color:#718198;font-size:12px;">Sin datos del supervisor</div>';
    caption.textContent = 'Sin datos';
  }

  // Render health
  if (healthErr) {
    healthBox.innerHTML = '<div style="padding:12px;color:#fb7185;font-size:12px;">' + escapeHtml(healthErr) + '</div>';
  } else if (healthData && Array.isArray(healthData.checks)) {
    const rows = healthData.checks.map(c => {
      const ok = !!c.ok;
      return '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;border-bottom:1px solid #1e293b;font-size:12px;">' +
        '<span style="color:#94a3b8;">' + escapeHtml(c.name) + '</span>' +
        '<span style="color:#e2e8f0;font-family:JetBrains Mono,monospace;max-width:60%;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="' + escapeHtml(c.detail || '') + '">' + pmSystemBadge(c.detail || (ok ? 'OK' : 'Falla'), ok) + '</span>' +
        '</div>';
    }).join('');
    const meta = '<div style="padding:8px 12px;color:#64748b;font-size:10px;border-bottom:1px solid #1e293b;">' +
      'Runtime: ' + escapeHtml(healthData.runtime_root || '—') + ' · Revisado: ' + new Date(healthData.checked_at).toLocaleTimeString('es-ES') +
      '</div>';
    healthBox.innerHTML = meta + rows;
  } else {
    healthBox.innerHTML = '<div style="padding:12px;color:#718198;font-size:12px;">Sin health checks</div>';
  }
}

async function pmRestartSupervisor() {
  const api = electronApi();
  if (!api || !api.runSupervisorCommand) {
    showToast('Reinicio no disponible sin Electron/backend operativo', false);
    return;
  }
  if (!confirm('¿Reiniciar el supervisor BAGO? Esto detendrá y volverá a arrancar el proceso de fondo.')) return;
  try {
    showToast('Deteniendo supervisor…', true);
    await api.runSupervisorCommand(['stop']);
    await new Promise(r => setTimeout(r, 1500));
    showToast('Arrancando supervisor…', true);
    await api.runSupervisorCommand(['start']);
    await new Promise(r => setTimeout(r, 1500));
    await pmLoadSystemStatus();
    showToast('Supervisor reiniciado', true);
  } catch (e) {
    showToast('Error al reiniciar: ' + (e.message || ''), false);
  }
}

async function pmCleanupZombies() {
  const api = electronApi();
  if (!api || !api.cleanupZombies) {
    showToast('Limpieza no disponible sin Electron/backend operativo', false);
    return;
  }
  if (!confirm('¿Limpiar conexiones zombie y procesos huérfanos? Esto cierra conexiones TIME_WAIT/CloseWait y python.exe sin padre.')) return;
  try {
    showToast('Limpiando zombies…', true);
    const res = await api.cleanupZombies();
    await pmLoadSystemStatus();
    const cleaned = res && typeof res.cleaned === 'number' ? res.cleaned : '?';
    showToast('Limpieza completada · ' + cleaned + ' proceso(s) cerrado(s)', true);
  } catch (e) {
    showToast('Error al limpiar: ' + (e.message || ''), false);
  }
}

function pmInitSystem() {
  const refreshBtn = document.getElementById('pm-system-refresh');
  const restartBtn = document.getElementById('pm-supervisor-restart');
  const cleanupBtn = document.getElementById('pm-zombie-cleanup');

  if (refreshBtn) refreshBtn.addEventListener('click', pmLoadSystemStatus);
  if (restartBtn) restartBtn.addEventListener('click', pmRestartSupervisor);
  if (cleanupBtn) cleanupBtn.addEventListener('click', pmCleanupZombies);

  // Auto-cargar cuando se muestra la pestaña
  const observer = new MutationObserver((mutations) => {
    mutations.forEach(m => {
      if (m.type === 'attributes' && m.attributeName === 'class') {
        const el = document.getElementById('pm-view-system');
        if (el && el.classList.contains('active')) {
          pmLoadSystemStatus();
        }
      }
    });
  });
  const sysView = document.getElementById('pm-view-system');
  if (sysView) observer.observe(sysView, { attributes: true });
}

pmInitSystem();
