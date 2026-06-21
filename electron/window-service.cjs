const { app, BrowserWindow, shell } = require('electron');
const {
  MANAGER_HTML,
  REACT_HTML,
  ICON_PATH,
  PRELOAD_PATH,
  SMOKE_TEST,
  isExternalUrl
} = require('./environment.cjs');

function createManagerWindow() {
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

  // Load React app as primary interface; falls back to MANAGER_HTML if React dist is unavailable
  win.loadFile(REACT_HTML);
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
