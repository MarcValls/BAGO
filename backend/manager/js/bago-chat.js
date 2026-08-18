/* BAGO Chat tab — carga el chat web como iframe dentro del gestor.
 * También actúa como bridge postMessage: envía contexto operativo al chat
 * (vista activa, instalación seleccionada, resumen del node) para que BAGO
 * pueda actuar como copiloto contextual del gestor.
 */
(function () {
  'use strict';

  let chatUrl = null;
  let loading = false;

  function frame()  { return document.getElementById('pm-bago-frame');  }
  function status() { return document.getElementById('pm-bago-status'); }

  // ── postMessage bridge ────────────────────────────────────────────────────
  function broadcastToChat(type, data) {
    const f = frame();
    if (!f || !f.contentWindow || !chatUrl) return;
    try {
      f.contentWindow.postMessage({ source: 'bago-manager', type, data }, '*');
    } catch {}
  }

  // Interceptar pmSwitchView para notificar al chat de cambios de vista
  document.addEventListener('DOMContentLoaded', function () {
    const orig = window.pmSwitchView;
    if (typeof orig === 'function') {
      window.pmSwitchView = function (view) {
        orig.call(this, view);
        broadcastToChat('view-changed', { view });
      };
    }
  });

  // Enviar contexto completo cuando el chat se carga por primera vez
  function sendInitialContext() {
    // Vista activa
    const activeView = document.querySelector('.pm-view.active');
    const view = activeView ? activeView.id.replace('pm-view-', '') : 'patch';
    broadcastToChat('view-changed', { view });

    // Resumen de instalaciones si está disponible
    const installs = document.getElementById('pm-store-installs');
    const pieces = document.getElementById('pm-store-pieces');
    if (installs || pieces) {
      broadcastToChat('store-summary', {
        installations: installs ? installs.textContent : '?',
        pieces: pieces ? pieces.textContent : '?'
      });
    }
  }

  // ── Carga del iframe ──────────────────────────────────────────────────────
  function setStatus(html, isError) {
    const el = status();
    if (!el) return;
    el.innerHTML = html;
    el.style.display = '';
    el.style.color = isError ? '#f87171' : '';
  }

  function showFrame(url) {
    const f = frame();
    const s = status();
    if (!f) return;
    f.src = url;
    f.style.display = '';
    if (s) s.style.display = 'none';
    // Contexto inicial cuando el iframe termina de cargar
    f.addEventListener('load', sendInitialContext, { once: true });
  }

  async function loadChat() {
    if (chatUrl) { showFrame(chatUrl); return; }
    if (loading) return;
    loading = true;

    const api = window.bagoElectron;
    if (!api || typeof api.getChatUrl !== 'function') {
      setStatus(
        '<span class="pm-bago-icon">🖥️</span>' +
        '<strong>BAGO Chat</strong>' +
        '<p>Disponible solo desde la aplicación Electron.</p>',
        false
      );
      loading = false;
      return;
    }

    setStatus('<span class="pm-bago-icon">⏳</span><p>Iniciando BAGO chat…</p>', false);

    try {
      const session = typeof pmCurrentSession === 'function' ? pmCurrentSession() : null;
      chatUrl = await api.getChatUrl({
        sessionId: session && (session.session_id || session.sid) ? (session.session_id || session.sid) : '',
        provider: session && session.provider ? session.provider : '',
        model: session && session.model ? session.model : '',
        bridges: session && Array.isArray(session.active_bridges) ? session.active_bridges : [],
        basePath: session && session.base_path ? session.base_path : '',
      });
      showFrame(chatUrl);
    } catch (e) {
      setStatus(
        '<span class="pm-bago-icon">⚠️</span>' +
        '<strong>Error al iniciar el chat</strong>' +
        '<p>' + String(e && e.message || e) + '</p>' +
        '<button onclick="window.__bagoChatRetry&&window.__bagoChatRetry()" class="pm-btn" style="margin-top:8px">Reintentar</button>',
        true
      );
      chatUrl = null;
    } finally {
      loading = false;
    }
  }

  window.__bagoChatLoad = loadChat;
  window.__bagoChatRetry = function () { loading = false; chatUrl = null; loadChat(); };

  // Detecta clic en el botón de navegación BAGO y carga el chat
  document.addEventListener('click', function (e) {
    const btn = e.target && e.target.closest('[data-pm-view]');
    if (btn && btn.getAttribute('data-pm-view') === 'bago') {
      setTimeout(loadChat, 0);
    }
  });

  // ── Mostrar INSTALLS_ROOT en el sidebar ───────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    const api = window.bagoElectron;
    if (!api) return;

    // Versión dinámica desde release_version.txt (evita hardcode)
    if (typeof api.getVersion === 'function') {
      api.getVersion().then(function (v) {
        if (!v) return;
        const tag = 'v' + v.replace(/^v/, '');
        ['bago-version-meta', 'bago-version-footer'].forEach(function (id) {
          const el = document.getElementById(id);
          if (el) el.textContent = tag;
        });
      }).catch(function () {});
    }

    if (typeof api.getInstallsRoot !== 'function') return;
    api.getInstallsRoot().then(function (root) {
      if (!root) return;
      const store = document.querySelector('.pm-store');
      if (!store) return;
      const row = document.createElement('div');
      row.className = 'pm-store-row pm-installs-root-row';
      row.title = root;
      const parts = root.replace(/\\/g, '/').split('/').filter(Boolean);
      const label = parts.length > 2 ? '…/' + parts.slice(-2).join('/') : root;
      row.innerHTML = '<span>Installs root</span><strong style="font-size:9px;word-break:break-all">' +
        label.replace(/</g, '&lt;') + '</strong>';
      store.appendChild(row);
    }).catch(function () {});
  });
}());
