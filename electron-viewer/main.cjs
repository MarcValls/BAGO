// BAGO Electron App
// En modo empaquetado (electron-builder): lee la ruta de instalacion desde
// el registro de Windows para localizar dev.ps1, arranca el backend al
// abrirse y lo para al cerrarse.
// En modo desarrollo: usa la raiz del repo relativa a __dirname.

const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const fs = require('fs');
const path = require('path');
const { spawnSync, execSync } = require('child_process');

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

// ── Helpers ───────────────────────────────────────────────────────────────────
function requestPath(rawUrl) {
  try { return new URL(rawUrl).pathname; } catch { return '<invalid-url>'; }
}

function appendRequestLog(line) {
  fs.appendFile(REQUEST_LOG, `${line}\n`, () => {});
}

function runDevPs1(cmd) {
  if (process.platform !== 'win32') return;
  try {
    spawnSync('powershell.exe', [
      '-NoProfile', '-ExecutionPolicy', 'Bypass',
      '-File', DEV_PS1, cmd
    ], { cwd: REPO_ROOT, stdio: 'ignore', timeout: 20000 });
  } catch { /* ignorar errores al arrancar/parar */ }
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
  // Arrancar el backend antes de abrir la ventana
  if (app.isPackaged) {
    try { fs.mkdirSync(RUN_DIR, { recursive: true }); } catch {}
    runDevPs1('start');
  }
  createViewerWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createViewerWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Al cerrar, detiene el backend automáticamente.
app.on('before-quit', () => {
  runDevPs1('stop');
});
