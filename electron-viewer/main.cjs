// BAGO Electron App
// En modo empaquetado (electron-builder): lee la ruta de instalacion desde
// el registro de Windows para localizar el payload instalado, arranca el
// backend al abrirse y lo para al cerrarse.
// En modo desarrollo: usa la raiz del repo relativa a __dirname.

const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const fs = require('fs');
const path = require('path');
const { spawnSync, execSync, spawn } = require('child_process');
const http = require('http');

// ── Robust console logging in the main process ───────────────────────────────
// Windows Electron can throw EPIPE when writing to a closed stdout/stderr
// pipe (e.g. launched from a terminal that exits). Swallow those errors so
// a stray diagnostic write never crashes the app.
const safeWrite = (target, args) => {
  try {
    target.apply(console, args);
  } catch (err) {
    if (err?.code !== 'EPIPE') {
      try {
        process.stdout.write(`[console-fallback] ${args.join(' ')}\n`);
      } catch {}
    }
  }
};
const originalLog = console.log;
const originalError = console.error;
console.log = (...args) => safeWrite(originalLog, args);
console.error = (...args) => safeWrite(originalError, args);

// ── Resolver raíz del repo ────────────────────────────────────────────────────
function hasDevScript(rootPath) {
  return !!rootPath && fs.existsSync(path.join(rootPath, 'scripts', 'dev.ps1'));
}

function describeRuntimeRoot(rootPath, source) {
  if (!rootPath) return null;
  const root = path.resolve(rootPath);
  const monorepoBackend = path.join(root, 'backend');
  const flatBackend = root;
  const backendRoot = fs.existsSync(path.join(monorepoBackend, 'bago_core', 'cli.py'))
    ? monorepoBackend
    : fs.existsSync(path.join(flatBackend, 'bago_core', 'cli.py'))
      ? flatBackend
      : '';
  if (!backendRoot) return null;

  const serviceCandidates = [
    path.join(root, 'scripts', 'runtime-service.ps1'),
    path.join(root, 'scripts', 'dev.ps1'),
  ];
  const servicePs1 = serviceCandidates.find((candidate) => fs.existsSync(candidate)) || '';
  if (!servicePs1) return null;

  return {
    repoRoot: root,
    backendRoot,
    uiDist: path.join(backendRoot, 'ui-react', 'dist'),
    servicePs1,
    runDir: path.join(root, '.run'),
    source,
  };
}

function findWorkspaceRoot(startPath) {
  if (!startPath) return '';
  let current = path.resolve(startPath);
  for (let i = 0; i < 6; i += 1) {
    if (describeRuntimeRoot(current, 'detected-source')) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return '';
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
    return describeRuntimeRoot(repoRoot, 'dev');
  }

  const sourceRoot = findWorkspaceRoot(process.cwd()) || findWorkspaceRoot(path.dirname(process.execPath));
  if (sourceRoot) {
    return describeRuntimeRoot(sourceRoot, 'detected-source');
  }

  const explicitInstallRoot = (process.env.BAGO_INSTALL_ROOT || '').trim();
  const explicitRuntime = describeRuntimeRoot(explicitInstallRoot, 'env');
  if (explicitRuntime) return explicitRuntime;

  const installRoot = readRegistryInstallPath();
  const registeredRuntime = describeRuntimeRoot(installRoot, 'registry');
  if (registeredRuntime) return registeredRuntime;

  const packagedRuntime = describeRuntimeRoot(process.resourcesPath, 'resources');
  if (packagedRuntime) {
    packagedRuntime.runDir = path.join(app.getPath('userData'), '.run');
    return packagedRuntime;
  }

  const fallbackDevRoot = path.resolve(__dirname, '..');
  const fallbackRuntime = describeRuntimeRoot(fallbackDevRoot, 'fallback-dev');
  if (fallbackRuntime) return fallbackRuntime;

  return null;
}

let RUNTIME_PATHS = null;
let BACKEND_HEALTHY = false;

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

function getServicePs1Path() {
  const runtime = getRuntimePaths();
  return runtime ? runtime.servicePs1 : '';
}

function getRunDir() {
  const runtime = getRuntimePaths();
  return runtime ? runtime.runDir : path.join(app.getPath('userData'), '.run');
}

function getRequestLogPath() {
  return path.join(getRunDir(), 'electron-requests.log');
}

function bootLog(message) {
  try {
    const logPath = path.join(app.getPath('userData'), 'boot.log');
    fs.appendFileSync(logPath, `${new Date().toISOString()} ${message}\n`);
  } catch {}
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

function runRuntimeService(cmd) {
  if (process.platform !== 'win32') return true;
  const servicePs1Path = getServicePs1Path();
  const repoRoot = getRepoRoot();
  if (!servicePs1Path || !repoRoot) return false;
  try {
    const timeout = (cmd === 'backend' || cmd === 'start') ? 120000 : 30000;
    const result = spawnSync('powershell.exe', [
      '-NoProfile', '-ExecutionPolicy', 'Bypass',
      '-File', servicePs1Path, cmd
    ], { cwd: repoRoot, stdio: 'ignore', timeout });
    bootLog(`runRuntimeService(${cmd}) path=${servicePs1Path} cwd=${repoRoot} status=${String(result.status)} error=${String(result.error?.message || '')}`);
    return result.status === 0;
  } catch {
    bootLog(`runRuntimeService(${cmd}) threw`);
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

// In development mode, start the local backend if it is not already running.
// Returns true immediately if healthy or if a launch was attempted.
let devBackendStarting = false;
async function ensureDevBackend() {
  if (app.isPackaged) return true;
  if (await probeHealthOnce(HEALTH_URL)) return true;
  const runtime = getRuntimePaths();
  if (!runtime || !runtime.servicePs1) return false;
  if (devBackendStarting) return true;
  devBackendStarting = true;
  bootLog('dev backend not healthy; starting via dev.ps1 backend');
  return new Promise((resolve) => {
    const child = spawn('powershell.exe', [
      '-NoProfile', '-ExecutionPolicy', 'Bypass',
      '-File', runtime.servicePs1, 'backend'
    ], { cwd: runtime.repoRoot, stdio: 'ignore' });
    child.on('error', (err) => {
      bootLog(`dev backend spawn error: ${err.message}`);
      devBackendStarting = false;
      resolve(false);
    });
    child.on('exit', (code) => {
      bootLog(`dev backend launcher exited with code ${code}`);
      devBackendStarting = false;
      resolve(true);
    });
    // Also resolve after a short grace period so we don't block window creation.
    setTimeout(() => {
      devBackendStarting = false;
      resolve(true);
    }, 3000);
  });
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
  const runtime = getRuntimePaths();
  const uiDist = runtime ? path.join(runtime.uiDist, 'index.html') : '';
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

  if (BACKEND_HEALTHY) {
    win.loadURL(UI_URL);
  } else if (uiDist && fs.existsSync(uiDist)) {
    win.loadFile(uiDist).catch(() => { win.loadURL(UI_URL); });
  } else {
    win.loadURL(UI_URL);
  }

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
  bootLog(`runtime source=${runtime ? runtime.source : 'none'} repoRoot=${runtime ? runtime.repoRoot : 'none'} servicePs1=${runtime ? runtime.servicePs1 : 'none'}`);
  const uiDist = runtime ? path.join(runtime.uiDist, 'index.html') : '';
  bootLog(`uiDist=${uiDist} exists=${uiDist ? fs.existsSync(uiDist) : false}`);
  bootLog(`runtime source=${runtime?.source || 'null'} repoRoot=${runtime?.repoRoot || ''} servicePs1=${runtime?.servicePs1 || ''} runDir=${runtime?.runDir || ''}`);
  if (!runtime) {
    dialog.showErrorBox(
      'BAGO: runtime no resuelto',
      'No se pudo resolver la raiz de ejecucion. Configure BAGO_INSTALL_ROOT o HKCU\\Software\\BAGO\\InstallPath.'
    );
    app.exit(1);
    return;
  }

  // En modo empaquetado arrancamos el backend local; en desarrollo lo
  // arrancamos también si no hay nada respondiendo en 127.0.0.1:8080.
  if (app.isPackaged) {
    try { fs.mkdirSync(runtime.runDir, { recursive: true }); } catch {}
    const started = runRuntimeService('backend');
    if (!started) {
      dialog.showErrorBox('BAGO: error de arranque', 'No se pudo iniciar el backend (dev.ps1 start).');
      app.exit(1);
      return;
    }
  } else {
    await ensureDevBackend();
  }
  const healthy = await waitForBackendHealth(HEALTH_URL, 30000);
  BACKEND_HEALTHY = healthy;
  if (app.isPackaged && !healthy) {
    dialog.showErrorBox('BAGO: backend no disponible', 'El backend no respondió en /health dentro del tiempo esperado.');
    runRuntimeService('stop');
    app.exit(1);
    return;
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

// Al cerrar, detiene el backend automáticamente solo en modo empaquetado.
// En desarrollo el backend es gestionado por scripts/dev.ps1; de lo contrario
// al cerrar la ventana se invocaría 'dev.ps1 stop' sobre sí mismo.
app.on('before-quit', () => {
  if (!app.isPackaged) return;
  if (!runRuntimeService('stop')) {
    appendRequestLog('[LIFECYCLE] backend stop command returned non-zero');
  }
});
