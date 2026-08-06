// BAGO Electron App
// En modo empaquetado (electron-builder): lee la ruta de instalacion desde
// el registro de Windows para localizar dev.ps1, arranca el backend al
// abrirse y lo para al cerrarse.
// En modo desarrollo: usa la raiz del repo relativa a __dirname.

const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const fs = require('fs');
const path = require('path');
const { spawnSync, execSync } = require('child_process');
const http = require('http');

// ── Resolver raíz del repo ────────────────────────────────────────────────────
function resolveRepoRoot() {
  if (!app.isPackaged) {
    // Modo dev: electron-viewer/../
    return path.resolve(__dirname, '..');
  }
  // Modo empaquetado: leer registro HKCU\Software\BAGO\InstallPath
  try {
    const out = execSync(
      'reg query HKCU\\Software\\BAGO /v InstallPath',
      { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }
    );
    const m = out.match(/InstallPath\s+REG_SZ\s+(.+)/);
    if (m) return m[1].trim();
  } catch { /* registry key not found */ }
  // Fallback: cuatro niveles arriba del .exe (win-unpacked/BAGO.exe)
  return path.resolve(path.dirname(process.execPath), '..', '..', '..', '..');
}

const REPO_ROOT = resolveRepoRoot();
const DEV_PS1   = path.join(REPO_ROOT, 'scripts', 'dev.ps1');
const RUN_DIR   = path.join(REPO_ROOT, '.run');
const REQUEST_LOG = path.join(RUN_DIR, 'electron-requests.log');

const UI_URL = 'http://127.0.0.1:8080/';
const HEALTH_URL = 'http://127.0.0.1:8080/health';

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function requestPath(rawUrl) {
  try { return new URL(rawUrl).pathname; } catch { return '<invalid-url>'; }
}

function appendRequestLog(line) {
  fs.appendFile(REQUEST_LOG, `${line}\n`, () => {});
}

function runDevPs1(cmd) {
  if (process.platform !== 'win32') return true;
  try {
    const result = spawnSync('powershell.exe', [
      '-NoProfile', '-ExecutionPolicy', 'Bypass',
      '-File', DEV_PS1, cmd
    ], { cwd: REPO_ROOT, stdio: 'ignore', timeout: 30000 });
    return result.status === 0;
  } catch {
    return false;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isAllowedExternalUrl(raw) {
  try {
    const u = new URL(raw);
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch {
    return false;
  }
}

function probeHealthOnce(url) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: 2000 }, (res) => {
      const ok = res.statusCode === 200;
      res.resume();
      resolve(ok);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function waitForBackendHealth(url, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await probeHealthOnce(url)) return true;
    await sleep(500);
  }
  return false;
}

function getAutoCloseSeconds() {
  const raw = process.env.BAGO_E2E_AUTOCLOSE_SECONDS;
  if (!raw) return 0;
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return Math.min(Math.floor(n), 600);
}

// ── Ventana principal ─────────────────────────────────────────────────────────
function createViewerWindow() {
  const iconPath = path.join(__dirname, 'bago.ico');
  const win = new BrowserWindow({
    width: 1600,
    height: 1000,
    minWidth: 1100,
    minHeight: 700,
    title: 'BAGO',
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
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
    if (isAllowedExternalUrl(url)) {
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

app.on('second-instance', () => {
  const windows = BrowserWindow.getAllWindows();
  if (windows.length > 0) {
    const win = windows[0];
    if (win.isMinimized()) win.restore();
    win.focus();
  }
});

app.whenReady().then(async () => {
  // Arrancar y validar backend antes de abrir la ventana empaquetada.
  if (app.isPackaged) {
    try { fs.mkdirSync(RUN_DIR, { recursive: true }); } catch {}
    const started = runDevPs1('start');
    if (!started) {
      dialog.showErrorBox('BAGO: error de arranque', 'No se pudo iniciar el backend (dev.ps1 start).');
      app.exit(1);
      return;
    }
    const healthy = await waitForBackendHealth(HEALTH_URL, 30000);
    if (!healthy) {
      dialog.showErrorBox('BAGO: backend no disponible', 'El backend no respondió en /health dentro del tiempo esperado.');
      runDevPs1('stop');
      app.exit(1);
      return;
    }
  }
  const mainWin = createViewerWindow();
  const autoCloseSeconds = getAutoCloseSeconds();
  if (autoCloseSeconds > 0) {
    setTimeout(() => {
      if (!mainWin.isDestroyed()) app.quit();
    }, autoCloseSeconds * 1000);
  }
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createViewerWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Al cerrar, detiene el backend automáticamente.
app.on('before-quit', () => {
  if (!runDevPs1('stop')) {
    appendRequestLog('[LIFECYCLE] backend stop command returned non-zero');
  }
});
