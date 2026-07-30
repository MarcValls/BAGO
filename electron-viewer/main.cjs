// Visor minimo de la BAGO UI para desarrollo.
// Apunta al bridge local (127.0.0.1:8080) que sirve el dist/ compilado.
// Electron provee window.bagoElectron con APIs nativas:
// - chooseProjectRoot / chooseWorkspaceRoot: diálogo nativo de selección de carpeta
// - onInstanceActive: notificación de instancia única

const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const fs = require('fs');
const path = require('path');

const UI_URL = 'http://127.0.0.1:8080/';
const REQUEST_LOG = path.join(__dirname, '..', '.run', 'electron-requests.log');

function requestPath(rawUrl) {
  try {
    return new URL(rawUrl).pathname;
  } catch {
    return '<invalid-url>';
  }
}

function appendRequestLog(line) {
  fs.appendFile(REQUEST_LOG, `${line}\n`, () => {});
}

function createViewerWindow() {
  const win = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1100,
    minHeight: 700,
    title: 'BAGO UI (visor de desarrollo)',
    backgroundColor: '#07090d',
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  // Abrir links externos en el navegador del sistema, no en la app.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  // Permitir que la UI sepa que corre dentro de Electron.
  win.webContents.on('did-finish-load', () => {
    win.webContents.executeJavaScript(`
      window.bagoElectron = window.bagoElectron || {};
      window.bagoElectron.isViewer = true;
    `).catch(() => {});
    // DevTools solo se abren cuando se solicitan explícitamente para diagnóstico.
    if (process.env.BAGO_DEVTOOLS === '1') {
      win.webContents.openDevTools({ mode: 'detach' });
    }
  });

  win.loadURL(UI_URL);

  // Request diagnostics deliberately omit bodies and query strings.
  win.webContents.session.webRequest.onCompleted((details) => {
    const ts = new Date().toISOString();
    const line = `[${ts}] ${details.method} ${requestPath(details.url)} -> ${details.statusCode}`;
    console.log(line);
    appendRequestLog(line);
  });
  win.webContents.on('console-message', ({ level, message }) => {
    if (message && (message.includes('400') || message.includes('BagoHttp'))) {
      appendRequestLog(`[CONSOLE level=${level}] renderer request error`);
    }
  });
  win.webContents.session.webRequest.onErrorOccurred((details) => {
    const ts = new Date().toISOString();
    const line = `[${ts}] ERROR ${details.method} ${requestPath(details.url)} -> ${details.error}`;
    console.log(line);
    appendRequestLog(line);
  });

  return win;
}

// IPC: diálogo nativo para elegir raíz de proyecto.
ipcMain.handle('bago:choose-project-root', async (event, options = {}) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  const defaultPath = options.defaultPath || undefined;
  const result = await dialog.showOpenDialog(win, {
    title: 'Elegir raíz de proyecto',
    defaultPath,
    properties: ['openDirectory', 'createDirectory']
  });
  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true, path: '' };
  }
  return { canceled: false, path: result.filePaths[0] };
});

// IPC: diálogo nativo para elegir workspace.
ipcMain.handle('bago:choose-workspace-root', async (event, options = {}) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  const defaultPath = options.defaultPath || undefined;
  const result = await dialog.showOpenDialog(win, {
    title: 'Elegir workspace',
    defaultPath,
    properties: ['openDirectory', 'createDirectory']
  });
  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true, path: '' };
  }
  return { canceled: false, path: result.filePaths[0] };
});

app.whenReady().then(() => {
  createViewerWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createViewerWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
