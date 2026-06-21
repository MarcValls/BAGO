// startup-deps.js — Banner de arranque para dependencias base del manager.
(function () {
  const api = (typeof window !== 'undefined' && window.bagoElectron) || null;
  if (!api) return;

  const BANNER_ID = 'bago-startup-deps-banner';

  function ensureBanner() {
    let el = document.getElementById(BANNER_ID);
    if (el) return el;
    el = document.createElement('section');
    el.id = BANNER_ID;
    el.setAttribute('role', 'status');
    el.style.cssText = [
      'position:sticky',
      'top:0',
      'z-index:80',
      'margin:0 0 12px',
      'padding:14px 16px',
      'border:1px solid #7c2d12',
      'border-radius:12px',
      'background:linear-gradient(180deg,#1f2937,#0f172a)',
      'color:#e2e8f0',
      'box-shadow:0 10px 30px rgba(15,23,42,.28)',
      'display:none'
    ].join(';');
    document.body.insertBefore(el, document.body.firstChild);
    return el;
  }

  function dependencyLabel(id) {
    const match = (pmDependencyCatalog && pmDependencyCatalog.core || []).find(item => item.id === id);
    return match ? match.label : id;
  }

  async function runInstall(targets) {
    const names = Array.isArray(targets) ? targets.filter(Boolean) : [];
    if (!names.length) return;
    if (!window.confirm('¿Instalar las dependencias faltantes ahora?')) return;
    try {
      const result = await api.dependencyAction({ action: names.length > 1 ? 'install-all' : 'install', targets: names, target: names[0] });
      if (result && result.command) {
        await copyText(result.command);
        showToast('Comando copiado; ejecútalo manualmente si procede', true);
        return result;
      }
      showToast('Instalador iniciado en segundo plano', true);
      return result;
    } catch (error) {
      showToast(error.message || 'No se pudo lanzar la instalación', false);
    }
  }

  function render(state) {
    const startup = state && state.startup ? state.startup : { ready: true, missing_core: [], required_missing: [], recommended_missing: [] };
    const missing = Array.isArray(startup.missing_core) ? startup.missing_core : [];
    const banner = ensureBanner();

    if (!missing.length) {
      banner.style.display = 'none';
      banner.innerHTML = '';
      return;
    }

    const requiredMissing = missing.filter(item => item.required);
    const severity = requiredMissing.length ? 'required' : 'recommended';
    const title = requiredMissing.length
      ? 'BAGO necesita dependencias obligatorias para arrancar bien'
      : 'BAGO recomienda completar dependencias para trabajar mejor';
    const subtitle = requiredMissing.length
      ? 'Instálalas ahora para evitar fallos al iniciar o al cambiar de provider.'
      : 'No bloquean el arranque, pero te van a ahorrar errores después.';
    const primaryTargets = (requiredMissing.length ? requiredMissing : missing).filter(item => item.install_command);
    const manualTargets = (requiredMissing.length ? requiredMissing : missing).filter(item => !item.install_command);

    banner.innerHTML = [
      '<div style="display:flex;gap:14px;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;">',
      '<div style="min-width:280px;max-width:780px;">',
      '<div style="font-size:13px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;color:#fbbf24;">Arranque BAGO</div>',
      '<div style="font-size:18px;font-weight:700;margin-top:4px;">' + escapeHtml(title) + '</div>',
      '<div style="font-size:13px;color:#cbd5e1;margin-top:6px;">' + escapeHtml(subtitle) + '</div>',
      (manualTargets.length
        ? '<div style="margin-top:10px;font-size:12px;color:#fecaca;">Revisión manual requerida: ' + manualTargets.map(item => escapeHtml(dependencyLabel(item.id))).join(', ') + '</div>'
        : '') +
      '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;">' + primaryTargets.map(item => {
        const label = dependencyLabel(item.id);
        const tone = item.required ? 'background:#f97316;color:#fff;border-color:#fb923c;' : 'background:#334155;color:#e2e8f0;border-color:#475569;';
        return '<button class="pm-btn" data-startup-install="' + escapeHtml(item.id) + '" style="' + tone + '">Instalar ' + escapeHtml(label) + '</button>';
      }).join('') + '</div>',
      '</div>',
      '<div style="display:flex;flex-direction:column;gap:8px;min-width:220px;align-items:flex-end;">',
      '<span class="pm-badge ' + (severity === 'required' ? 'bad' : 'warn') + '">' + escapeHtml(startup.prompt || 'Dependencias detectadas') + '</span>',
      (primaryTargets.length ? '<button class="pm-btn primary" data-startup-install-all>Instalar faltantes</button>' : ''),
      '<button class="pm-btn" data-startup-open-health>Ver salud</button>',
      '</div>',
      '</div>'
    ].join('');
    banner.style.display = 'block';

    banner.querySelectorAll('[data-startup-install]').forEach(btn => {
      btn.addEventListener('click', () => runInstall([btn.getAttribute('data-startup-install') || '']));
    });
    const installAll = banner.querySelector('[data-startup-install-all]');
    if (installAll) {
      installAll.addEventListener('click', () => runInstall(primaryTargets.map(item => item.id)));
    }
    const openHealth = banner.querySelector('[data-startup-open-health]');
    if (openHealth) {
      openHealth.addEventListener('click', () => {
        const target = document.querySelector('[data-pm-view="health"]');
        if (target) target.click();
      });
    }
  }

  async function refresh() {
    try {
      const health = await api.managerHealth();
      render(health || {});
    } catch (error) {
      const banner = ensureBanner();
      banner.style.display = 'block';
      banner.style.borderColor = '#b91c1c';
      banner.style.background = 'linear-gradient(180deg,#7f1d1d,#450a0a)';
      banner.innerHTML = '<div style="font-size:14px;font-weight:700;">No se pudo comprobar el arranque</div><div style="font-size:12px;margin-top:6px;color:#fecaca;">' + escapeHtml(error.message || 'error desconocido') + '</div>';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', refresh, { once: true });
  } else {
    refresh();
  }
})();
