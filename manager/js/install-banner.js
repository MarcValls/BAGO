// P0-05 fix: a small banner that listens to `bago:install-state` events
// from the main process. It is shown whenever the install is in a
// non-ready phase so the user always has a recovery action available,
// even if the install fails before the Manager window is interactive.
(function () {
  const api = (typeof window !== 'undefined' && window.bagoElectron) || null;
  if (!api) return;

  const PHASE_LABELS = {
    pending: 'Inicializando instalador…',
    detecting: 'Buscando una instalacion existente de BAGO…',
    installing: 'Instalando BAGO…',
    repairing: 'Reparando configuracion de BAGO…',
    reinstalling: 'Reinstalando BAGO…',
    ready: 'BAGO listo',
    failed: 'La instalacion fallo',
    cancelled: 'Instalacion cancelada por el usuario'
  };

  function ensureBanner() {
    let el = document.getElementById('bago-install-state-banner');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'bago-install-state-banner';
    el.setAttribute('role', 'status');
    el.style.cssText = [
      'position:fixed', 'left:16px', 'right:16px', 'bottom:16px',
      'z-index:2147483646', 'padding:14px 18px',
      'border-radius:10px', 'background:#0f172a', 'color:#e2e8f0',
      'box-shadow:0 8px 24px rgba(0,0,0,.35)', 'font:13px/1.4 system-ui,Segoe UI,Roboto,sans-serif',
      'display:flex', 'align-items:center', 'justify-content:space-between', 'gap:12px'
    ].join(';');
    el.innerHTML = '<span data-role="msg">Inicializando instalador…</span><button data-role="dismiss" style="background:transparent;color:#94a3b8;border:1px solid #334155;border-radius:6px;padding:4px 10px;cursor:pointer">Cerrar</button>';
    document.body.appendChild(el);
    el.querySelector('[data-role=dismiss]').addEventListener('click', () => el.remove());
    return el;
  }

  function render(state) {
    if (!state) return;
    if (state.phase === 'ready' || state.phase === 'cancelled') {
      // Recovery UI is no longer needed; remove any visible banner so the
      // Manager can claim the bottom of the screen.
      const existing = document.getElementById('bago-install-state-banner');
      if (existing) existing.remove();
      return;
    }
    const banner = ensureBanner();
    const label = PHASE_LABELS[state.phase] || state.phase;
    const dir = state.installDir ? ` (${state.installDir})` : '';
    const err = state.error ? ` — ${state.error}` : '';
    banner.querySelector('[data-role=msg]').textContent = `${label}${dir}${err}`;
    banner.style.background = state.phase === 'failed' ? '#7f1d1d' : '#0f172a';
  }

  api.onInstallState(render);
  api.getInstallState().then(render).catch(() => {});
})();
