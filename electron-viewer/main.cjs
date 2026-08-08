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
function hasDevScript(rootPath) {
  return !!rootPath && fs.existsSync(path.join(rootPath, 'scripts', 'dev.ps1'));
}

function readRegistryInstallPath() {
  try {
    return execSync(
      'powershell.exe -NoProfile -Command "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; (Get-ItemProperty -Path HKCU:\\Software\\BAGO -Name InstallPath -ErrorAction Stop).InstallPath"',
      { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }
    ).trim();
  } catch {
    try {
      const out = execSync(
        'reg query HKCU\\Software\\BAGO /v InstallPath',
        { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] }
      );
      const m = out.match(/InstallPath\s+REG_SZ\s+(.+)/);
      return m ? m[1].trim() : '';
    } catch {
      return '';
    }
  }
}

function resolveRuntimePaths() {
  if (!app.isPackaged) {
    const repoRoot = path.resolve(__dirname, '..');
    return {
      repoRoot,
      devPs1: path.join(repoRoot, 'scripts', 'dev.ps1'),
      runDir: path.join(repoRoot, '.run'),
      source: 'dev',
    };
  }

  const explicitInstallRoot = (process.env.BAGO_INSTALL_ROOT || '').trim();
  if (hasDevScript(explicitInstallRoot)) {
    return {
      repoRoot: explicitInstallRoot,
      devPs1: path.join(explicitInstallRoot, 'scripts', 'dev.ps1'),
      runDir: path.join(explicitInstallRoot, '.run'),
      source: 'env',
    };
  }

  const installRoot = readRegistryInstallPath();
  if (hasDevScript(installRoot)) {
    return {
      repoRoot: installRoot,
      devPs1: path.join(installRoot, 'scripts', 'dev.ps1'),
      runDir: path.join(installRoot, '.run'),
      source: 'registry',
    };
  }

  const packagedDevPs1 = path.join(process.resourcesPath, 'scripts', 'dev.ps1');
  if (fs.existsSync(packagedDevPs1)) {
    return {
      repoRoot: process.resourcesPath,
      devPs1: packagedDevPs1,
      runDir: path.join(app.getPath('userData'), '.run'),
      source: 'resources',
    };
  }

  const fallbackDevRoot = path.resolve(__dirname, '..');
  if (hasDevScript(fallbackDevRoot)) {
    return {
      repoRoot: fallbackDevRoot,
      devPs1: path.join(fallbackDevRoot, 'scripts', 'dev.ps1'),
      runDir: path.join(fallbackDevRoot, '.run'),
      source: 'fallback-dev',
    };
  }

  return null;
}

let RUNTIME_PATHS = null;

function getRuntimePaths() {
  if (!RUNTIME_PATHS) {
    RUNTIME_PATHS = resolveRuntimePaths();
  }
  return RUNTIME_PATHS;
}

function getRepoRoot() {
  const runtime = getRuntimePaths();
  return runtime ? runtime.repoRoot : '';
}

function getDevPs1Path() {
  const runtime = getRuntimePaths();
  return runtime ? runtime.devPs1 : '';
}

function getRunDir() {
  const runtime = getRuntimePaths();
  return runtime ? runtime.runDir : path.join(app.getPath('userData'), '.run');
}

function getRequestLogPath() {
  return path.join(getRunDir(), 'electron-requests.log');
}

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
  fs.appendFile(getRequestLogPath(), `${line}\n`, () => {});
}

function runDevPs1(cmd) {
  if (process.platform !== 'win32') return true;
  const devPs1Path = getDevPs1Path();
  const repoRoot = getRepoRoot();
  if (!devPs1Path || !repoRoot) return false;
  try {
    const result = spawnSync('powershell.exe', [
      '-NoProfile', '-ExecutionPolicy', 'Bypass',
      '-File', devPs1Path, cmd
    ], { cwd: repoRoot, stdio: 'ignore', timeout: 30000 });
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
  const runtime = getRuntimePaths();
  if (!runtime) {
    dialog.showErrorBox(
      'BAGO: runtime no resuelto',
      'No se pudo resolver la raiz de ejecucion. Configure BAGO_INSTALL_ROOT o HKCU\\Software\\BAGO\\InstallPath.'
    );
    app.exit(1);
    return;
  }

  // Arrancar y validar backend antes de abrir la ventana empaquetada.
  if (app.isPackaged) {
    try { fs.mkdirSync(runtime.runDir, { recursive: true }); } catch {}
    const started = runDevPs1('backend');
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
