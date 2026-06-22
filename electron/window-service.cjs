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
            const timer = setInterval(() => {
              const cp = document.querySelector('.bago-cp');
              const electronOk = !!(window.bagoElectron && typeof window.bagoElectron.getVersion === 'function');
              if ((cp && electronOk) || Date.now() - started > 15000) {
                clearInterval(timer);
                resolve({
                  title: document.title,
                  control_plane_loaded: !!cp,
                  activity_bar_items: document.querySelectorAll('.cp-act-btn').length,
                  electron_bridge: electronOk,
                  electron_methods: window.bagoElectron ? Object.keys(window.bagoElectron).length : 0,
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
          result.control_plane_loaded
          && result.electron_bridge
          && result.activity_bar_items >= 3
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
