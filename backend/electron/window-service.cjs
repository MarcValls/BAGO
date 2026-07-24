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
            const timer = setInterval(() => {
              const root = document.querySelector('.app-root');
              const header = document.querySelector('.global-header');
              const sidebar = document.querySelector('.main-sidebar');
              const workspace = document.querySelector('.workspace-shell');
              const surface = document.querySelector('.surface-body');
              if ((root && header && sidebar && workspace && surface) || Date.now() - started > 24000) {
                clearInterval(timer);
                const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
                const scrollbar = surface ? getComputedStyle(surface, '::-webkit-scrollbar') : null;
                const bridge = window.bagoElectron;
                resolve({
                  title: document.title,
                  react_root: !!root,
                  header: !!header,
                  sidebar: !!sidebar,
                  workspace: !!workspace,
                  surface: !!surface,
                  destinations: document.querySelectorAll('.sidebar-item').length,
                  active_destination: document.querySelectorAll('.sidebar-item[aria-current="page"]').length,
                  bridge: !!bridge,
                  bridge_contract: !!(bridge
                    && typeof bridge.managerHealth === 'function'
                    && typeof bridge.getChatUrl === 'function'
                    && typeof bridge.readInstallSelection === 'function'),
                  scroll_overflow: surface ? getComputedStyle(surface).overflowY : '',
                  scrollbar_hidden: !!(scrollbar && (scrollbar.display === 'none' || scrollbar.width === '0px')),
                  duplicate_ids: ids.filter((id, index) => ids.indexOf(id) !== index)
                });
              }
            }, 250);
          })
        `);
        clearTimeout(timeout);
        const ok = !!(
          result.title === 'BAGO Control Plane'
          && result.react_root
          && result.header
          && result.sidebar
          && result.workspace
          && result.surface
          && result.destinations >= 8
          && result.active_destination === 1
          && result.bridge
          && result.bridge_contract
          && ['auto', 'scroll', 'hidden'].includes(result.scroll_overflow)
          && result.scrollbar_hidden
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
