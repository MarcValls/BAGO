const { app, BrowserWindow, shell } = require('electron');
const fs = require('fs');
const http = require('http');
const path = require('path');
const {
  MANAGER_HTML,
  REACT_HTML,
  ICON_PATH,
  PRELOAD_PATH,
  SMOKE_TEST,
  isExternalUrl
} = require('./environment.cjs');

let fallbackReactServer = null;
let fallbackReactServerUrl = '';

function getMimeType(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  switch (ext) {
    case '.html': return 'text/html; charset=utf-8';
    case '.js': return 'application/javascript; charset=utf-8';
    case '.css': return 'text/css; charset=utf-8';
    case '.json': return 'application/json; charset=utf-8';
    case '.svg': return 'image/svg+xml';
    case '.png': return 'image/png';
    case '.jpg':
    case '.jpeg': return 'image/jpeg';
    case '.gif': return 'image/gif';
    case '.ico': return 'image/x-icon';
    case '.woff': return 'font/woff';
    case '.woff2': return 'font/woff2';
    default: return 'application/octet-stream';
  }
}

function resolveFallbackFile(urlPath) {
  const distRoot = path.dirname(REACT_HTML);
  const cleanPath = String(urlPath || '/').split('?')[0].split('#')[0];
  const normalized = decodeURIComponent(cleanPath === '/' ? '/index.html' : cleanPath);
  const target = path.normalize(path.join(distRoot, normalized.replace(/^\/+/, '')));
  const relative = path.relative(distRoot, target);
  if (relative.startsWith('..') || path.isAbsolute(relative)) return null;
  return target;
}

function ensureFallbackReactServer() {
  if (fallbackReactServerUrl) {
    return Promise.resolve(fallbackReactServerUrl);
  }

  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const target = resolveFallbackFile(req.url || '/');
      if (!target) {
        res.writeHead(403, { 'content-type': 'text/plain; charset=utf-8' });
        res.end('Forbidden');
        return;
      }

      const exists = fs.existsSync(target);
      const filePath = exists ? target : path.join(path.dirname(REACT_HTML), 'index.html');
      try {
        const body = fs.readFileSync(filePath);
        res.writeHead(200, {
          'content-type': getMimeType(filePath),
          'cache-control': 'no-store'
        });
        res.end(body);
      } catch (error) {
        res.writeHead(500, { 'content-type': 'text/plain; charset=utf-8' });
        res.end(`Fallback UI failed: ${error && error.message ? error.message : error}`);
      }
    });

    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      if (!address || typeof address !== 'object') {
        reject(new Error('No se pudo arrancar el servidor local de fallback'));
        return;
      }
      fallbackReactServer = server;
      fallbackReactServerUrl = `http://127.0.0.1:${address.port}/`;
      resolve(fallbackReactServerUrl);
    });
  });
}

app.once('before-quit', () => {
  if (fallbackReactServer) {
    try { fallbackReactServer.close(); } catch {}
    fallbackReactServer = null;
    fallbackReactServerUrl = '';
  }
});

function createManagerWindow(options = {}) {
  const getRuntimeService = typeof options.getRuntimeService === 'function' ? options.getRuntimeService : null;
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 980,
    minHeight: 700,
    title: 'BAGO Installation Manager',
    icon: ICON_PATH,
    backgroundColor: '#020617',
    show: false,
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  win.removeMenu();
  win.once('ready-to-show', () => {
    if (!SMOKE_TEST) win.show();
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isExternalUrl(url)) shell.openExternal(url);
    return { action: 'deny' };
  });

  win.webContents.on('will-navigate', (event, url) => {
    if (url !== win.webContents.getURL() && isExternalUrl(url)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  // Load React through the BAGO web server so API calls are same-origin.
  // Fall back to a local static HTTP server so the renderer still mounts.
  (async () => {
    if (getRuntimeService) {
      try {
        const state = await getRuntimeService().ensureWebChatServer();
        await win.loadURL(state.url);
        return;
      } catch (error) {
        console.error(`BAGO React web server failed, falling back to local static UI: ${error && error.message ? error.message : error}`);
      }
    }
    const fallbackUrl = await ensureFallbackReactServer();
    await win.loadURL(fallbackUrl);
  })();
  if (SMOKE_TEST) {
    const timeout = setTimeout(() => {
      console.error(JSON.stringify({ manager_smoke: false, error: 'timeout' }));
      app.exit(1);
    }, 30000);
    win.webContents.once('did-finish-load', async () => {
      try {
        const result = await win.webContents.executeJavaScript(`
          new Promise(resolve => {
            const started = Date.now();
            const timer = setInterval(async () => {
              const status = typeof nodeCache !== 'undefined' && nodeCache.status;
              const health = typeof pmManagerHealth !== 'undefined' && pmManagerHealth;
              const releasesReady = typeof releaseItems !== 'undefined' && releaseItems.length > 0;
              if ((status && health && (releasesReady || Date.now() - started > 8000)) || Date.now() - started > 24000) {
                clearInterval(timer);
                const sample = status && Array.isArray(status.connectors_data)
                  ? status.connectors_data.find(item => item.mode === 'connected')
                  : null;
                const preview = sample && window.bagoElectron && window.bagoElectron.runNodePreview
                  ? await window.bagoElectron.runNodePreview(sample.installation_id, sample.piece_id, 'connected')
                  : null;
                const jobs = window.bagoElectron && window.bagoElectron.listReleaseJobs
                  ? await window.bagoElectron.listReleaseJobs()
                  : null;
                const sessions = window.bagoElectron && window.bagoElectron.runSessionCommand
                  ? await window.bagoElectron.runSessionCommand(['list'])
                  : null;
                const validRelease = typeof releaseItems !== 'undefined' && releaseItems.find(rel => {
                  const names = new Set((rel.assets || []).map(asset => String(asset.name || '').toLowerCase()));
                  return (rel.assets || []).some(asset => /\\.zip$/i.test(asset.name || '') && names.has(String(asset.name || '').toLowerCase() + '.sha256'));
                });
                const releasePreflight = validRelease && health && health.runtime_root && window.bagoElectron && window.bagoElectron.preflightRelease
                  ? await window.bagoElectron.preflightRelease({ release: validRelease, target: health.runtime_root, action: 'update' })
                  : null;
                const selectedSession = sessions && sessions.ok && Array.isArray(sessions.sessions) && sessions.sessions[0]
                  ? sessions.sessions[0]
                  : null;
                let sessionSync = null;
                if (selectedSession && window.bagoElectron && window.bagoElectron.getChatUrl) {
                  const chatUrl = await window.bagoElectron.getChatUrl({
                    sessionId: selectedSession.session_id || selectedSession.sid || '',
                    provider: selectedSession.provider || '',
                    model: selectedSession.model || '',
                    bridges: Array.isArray(selectedSession.active_bridges) ? selectedSession.active_bridges : [],
                    basePath: health && health.runtime_root ? health.runtime_root : ''
                  });
                  sessionSync = chatUrl
                    ? await fetch(String(chatUrl).replace(/\/?$/, '') + 'session').then(async response => response.ok ? response.json() : null).catch(() => null)
                    : null;
                }
                resolve({
                  title: document.title,
                  status_loaded: !!status,
                  installations: status && status.installations || 0,
                  pieces: status && status.pieces || 0,
                  connectors: status && status.connectors || 0,
                  evidence: !!(typeof nodeCache !== 'undefined' && nodeCache.evidence),
                  health_checks: health && Array.isArray(health.checks) ? health.checks.length : 0,
                  releases: typeof releaseItems !== 'undefined' && Array.isArray(releaseItems) ? releaseItems.length : 0,
                  preview_ok: !!(preview && preview.ok && preview.data && preview.data.ok),
                  jobs_bridge: Array.isArray(jobs),
                  sessions_bridge: !!(sessions && sessions.ok && Array.isArray(sessions.sessions)),
                  session_sync_ok: !!(sessionSync && selectedSession && sessionSync.provider === selectedSession.provider && sessionSync.model === selectedSession.model && String(sessionSync.session_id || '') === String(selectedSession.session_id || selectedSession.sid || '')),
                  chains_bridge: !!(window.bagoElectron && window.bagoElectron.readChainRegistry && window.bagoElectron.writeChainRegistry),
                  chain_editor: !!document.getElementById('pm-chain-track'),
                  patch_chain_surface: !!document.getElementById('pm-patch-surface'),
                  patch_chain_inspector: !!(document.getElementById('pm-detail-title') && document.getElementById('pm-patch-add-node') && typeof pmRenderChainDetail === 'function'),
                  release_preflight: !!(releasePreflight && releasePreflight.prepare_ready),
                  views: document.querySelectorAll('.pm-view').length,
                  duplicate_ids: (() => {
                    const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
                    return ids.filter((id, index) => ids.indexOf(id) !== index);
                  })()
                });
              }
            }, 250);
          })
        `);
        clearTimeout(timeout);
        const ok = !!(
          result.status_loaded
          && result.installations > 0
          && result.pieces > 0
          && result.connectors > 0
          && result.evidence
          && result.health_checks > 0
          && result.preview_ok
          && result.jobs_bridge
          && result.sessions_bridge
          && result.session_sync_ok
          && result.chains_bridge
          && result.chain_editor
          && result.patch_chain_surface
          && result.patch_chain_inspector
          && result.release_preflight
          && result.views >= 8
          && result.duplicate_ids.length === 0
        );
        console.log(JSON.stringify({ manager_smoke: ok, ...result }));
        app.exit(ok ? 0 : 1);
      } catch (error) {
        clearTimeout(timeout);
        console.error(JSON.stringify({ manager_smoke: false, error: error.message }));
        app.exit(1);
      }
    });
  }
}

module.exports = { createManagerWindow };
