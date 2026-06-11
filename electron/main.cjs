const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const { spawn, execFile } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { ReleaseJobManager } = require('./release-job-manager.cjs');

const ROOT_DIR = path.join(__dirname, '..');
const PACKAGED_RUNTIME_ROOT = path.join(process.resourcesPath || ROOT_DIR, 'app.asar.unpacked');
const DEV_PACKAGED_RUNTIME_ROOT = path.join(ROOT_DIR, 'dist', 'win-unpacked', 'resources', 'app.asar.unpacked');
const MANAGER_HTML = path.join(ROOT_DIR, 'manager', 'index.html');
const ICON_PATH = path.join(ROOT_DIR, 'bago.ico');
const PRELOAD_PATH = path.join(__dirname, 'preload.cjs');

// Directorio raíz donde el Manager guarda todas las instalaciones de BAGO.
// En producción: junto al .exe del Manager (persiste entre actualizaciones del app).
// En desarrollo: dentro del árbol de fuentes para no ensuciar el sistema.
const INSTALLS_ROOT = app.isPackaged
  ? path.join(path.dirname(app.getPath('exe')), 'installations')
  : path.join(ROOT_DIR, 'installations');

const MUTATING_NODE_COMMANDS = new Set(['connect', 'disconnect', 'set-mode']);
const SMOKE_TEST = process.env.BAGO_MANAGER_SMOKE_TEST === '1';
const CHAT_HOST = '127.0.0.1';
const CHAT_START_PORT = Number(process.env.BAGO_MANAGER_CHAT_PORT || 8080);
let activeNodeMutation = null;
let releaseJobs = null;
let webChatProcess = null;
let webChatWindow = null;
let webChatState = null;
if (SMOKE_TEST) {
  app.disableHardwareAcceleration();
  app.setPath('userData', path.join(os.tmpdir(), 'bago-manager-smoke'));
}

function isExternalUrl(url) {
  return /^https?:\/\//i.test(url);
}

function runVisiblePowerShell(command) {
  if (!command || typeof command !== 'string') {
    throw new Error('Comando vacío');
  }
  if (command.length > 12000) {
    throw new Error('Comando demasiado largo');
  }
  const child = spawn(
    'powershell.exe',
    ['-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
    {
      cwd: app.getPath('home'),
      detached: true,
      stdio: 'ignore',
      windowsHide: false
    }
  );
  child.unref();
  return { pid: child.pid };
}

function psSingleArg(value) {
  return `'${String(value || '').replace(/'/g, "''")}'`;
}

function hasBagoRuntime(root) {
  return !!root
    && fs.existsSync(path.join(root, 'bago_core', 'launcher.py'))
    && fs.existsSync(path.join(root, 'bago_core', 'session_control.py'))
    && fs.existsSync(path.join(root, '.bago', 'core', 'version.py'))
    && fs.existsSync(path.join(root, '.bago', 'core', 'context_store.py'));
}

// P0-01 fix: an installation manifest (install_manifest.json) marks a directory
// as a real system install, not just a runtime copy. Without this marker,
// `app.asar.unpacked` (or a dev tree) must never be treated as a real install.
function hasInstallManifest(root) {
  return !!root && fs.existsSync(path.join(root, 'install_manifest.json'));
}

// P0-01 fix: the bundled/packaged runtime is the runtime shipped inside the
// installer (app.asar.unpacked) or the local dev tree. It is valid for
// copy/repair operations but MUST NOT be confused with a real install.
function resolveBundledRuntimeRoot() {
  const candidates = app.isPackaged
    ? [PACKAGED_RUNTIME_ROOT, DEV_PACKAGED_RUNTIME_ROOT]
    : [ROOT_DIR, DEV_PACKAGED_RUNTIME_ROOT];
  for (const root of candidates) {
    if (hasBagoRuntime(root)) return root;
  }
  return '';
}

// P0-01 fix: a real install is a directory that is NOT the packaged runtime
// and that either carries an install_manifest.json (preferred) or lives in a
// well-known system/user location AND is writable from the current process.
function resolveInstalledRuntimeRoot() {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
  const localAppData = process.env.LOCALAPPDATA || (home ? path.join(home, 'AppData', 'Local') : '');

  const envOverride = process.env.BAGO_ROOT || '';

  // Primero: escanear el directorio de instalaciones propio del Manager.
  // Los BAGOs gestionados aquí tienen prioridad sobre instalaciones del sistema.
  const managedInstalls = [];
  try {
    if (fs.existsSync(INSTALLS_ROOT)) {
      fs.readdirSync(INSTALLS_ROOT, { withFileTypes: true })
        .filter(d => d.isDirectory())
        .forEach(d => managedInstalls.push(path.join(INSTALLS_ROOT, d.name)));
    }
  } catch {}

  const candidates = [
    envOverride,
    ...managedInstalls,
    path.join(programFiles, 'BAGO'),
    localAppData ? path.join(localAppData, 'BAGO') : '',
    home ? path.join(home, '.bago', 'active') : '',
    home ? path.join(home, '.bago', 'launch') : ''
  ].filter(Boolean);

  // Drop any candidate that resolves to the bundled/packaged runtime. The
  // bundled runtime is a copy of the Manager itself, not an install.
  const bundled = resolveBundledRuntimeRoot();
  const real = candidates.filter(c => {
    if (!hasBagoRuntime(c)) return false;
    if (bundled && path.resolve(c) === path.resolve(bundled)) return false;
    if (c === envOverride) return true; // explicit override always wins
    return hasInstallManifest(c) || isUserOwnedLocation(c, home);
  });
  return real[0] || '';
}

function isUserOwnedLocation(candidate, home) {
  if (!candidate || !home) return false;
  const resolved = path.resolve(candidate).toLowerCase();
  const homeLc = path.resolve(home).toLowerCase();
  const localAppDataLc = (process.env.LOCALAPPDATA || path.join(home, 'AppData', 'Local')).toLowerCase();
  return resolved.startsWith(homeLc) || resolved.startsWith(localAppDataLc);
}

// P0-01 fix: kept for backwards compatibility. By default we resolve a REAL
// install; the bundled runtime is only used as a fallback when the Manager
// is running in source/dev mode (e.g. `node electron/main.cjs` for testing).
function resolveBagoRuntimeRoot() {
  const installed = resolveInstalledRuntimeRoot();
  if (installed) return installed;
  if (!app.isPackaged) {
    const dev = resolveBundledRuntimeRoot();
    if (dev) return dev;
  }
  throw new Error('No se encontro una instalacion real de BAGO');
}

function resolveUiDist(runtimeRoot) {
  const candidates = [
    path.join(runtimeRoot, 'ui-react', 'dist'),
    path.join(ROOT_DIR, 'ui-react', 'dist'),
    path.join(PACKAGED_RUNTIME_ROOT, 'ui-react', 'dist'),
    path.join(DEV_PACKAGED_RUNTIME_ROOT, 'ui-react', 'dist')
  ];
  return candidates.find(candidate => fs.existsSync(path.join(candidate, 'index.html'))) || '';
}

function findPackagedRuntimeRoot() {
  return resolveBundledRuntimeRoot();
}

// P0-02 fix: choose a sensible default install dir for the current user.
// On Windows, Program Files is only writable for admins, so a non-elevated
// session falls back to %LOCALAPPDATA%\BAGO. The Manager still allows the
// user to pick any other writable location via the "Nueva copia" dialog.
let _defaultInstallDirCache = '';
function defaultInstallDir() {
  if (_defaultInstallDirCache) return _defaultInstallDirCache;
  // Las instalaciones de BAGO viven dentro del Manager, en INSTALLS_ROOT/active.
  // El Manager es la fuente de verdad; no se dispersan por %LOCALAPPDATA% ni Program Files.
  _defaultInstallDirCache = path.join(INSTALLS_ROOT, 'active');
  return _defaultInstallDirCache;
}

const PREFS_PATH = path.join(app.getPath('userData'), 'bago-manager-prefs.json');

function loadPrefs() {
  try {
    return JSON.parse(fs.readFileSync(PREFS_PATH, 'utf8'));
  } catch {
    return {};
  }
}

function savePrefs(prefs) {
  try {
    fs.writeFileSync(PREFS_PATH, JSON.stringify(prefs, null, 2));
  } catch {}
}

function buildInstallCommand(packagedRoot, installDir, extraArgs = []) {
  const installScript = path.join(packagedRoot, 'install-v4.ps1');
  if (!fs.existsSync(installScript)) {
    throw new Error(`No se encontró install-v4.ps1 en el paquete. Buscado en: ${installScript}`);
  }
  return [
    'powershell.exe',
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', installScript,
    '-SourceRoot', packagedRoot,
    '-InstallDir', installDir,
    '-Profile', 'stable',
    '-Mode', 'Express',
    ...extraArgs
  ];
}

function buildSourceInstallCommand(sourceRoot, installDir, branch = 'main', extraArgs = []) {
  const installScript = path.join(sourceRoot, 'install-v4.ps1');
  if (!fs.existsSync(installScript)) {
    throw new Error(`No se encontró install-v4.ps1 en la fuente. Buscado en: ${installScript}`);
  }
  const gitArgs = ['-C', sourceRoot, 'pull', '--ff-only', 'origin', branch];
  return {
    gitArgs,
    installArgs: [
      'powershell.exe',
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-File', installScript,
      '-SourceRoot', sourceRoot,
      '-InstallDir', installDir,
      '-Profile', 'stable',
      '-Mode', 'Express',
      ...extraArgs
    ]
  };
}

function showProgressWindow(title) {
  const win = new BrowserWindow({
    width: 480,
    height: 220,
    title: title || 'Procesando…',
    icon: ICON_PATH,
    backgroundColor: '#020617',
    resizable: false,
    minimizable: false,
    maximizable: false,
    alwaysOnTop: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true }
  });
  win.removeMenu();
  win.loadURL('data:text/html;base64,' + Buffer.from(`
    <!DOCTYPE html>
    <html style="background:#020617;color:#e2e8f0;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;">
      <div>
        <div style="font-size:48px;margin-bottom:12px;">⏳</div>
        <h2 style="margin:0 0 8px;font-size:18px;">${escapeHtml(title || 'Procesando…')}</h2>
        <p style="margin:0;color:#94a3b8;font-size:14px;">Esto puede tardar unos minutos.<br>No cierres esta ventana.</p>
      </div>
    </html>
  `).toString('base64'));
  return win;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

async function runInstallScript(packagedRoot, installDir, extraArgs = [], progressTitle = 'Instalando BAGO…') {
  const command = buildInstallCommand(packagedRoot, installDir, extraArgs);
  const progressWin = showProgressWindow(progressTitle);

  return new Promise((resolve, reject) => {
    const child = spawn(command[0], command.slice(1), {
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';
    child.stdout.on('data', d => { stdout += d; });
    child.stderr.on('data', d => { stderr += d; });

    child.on('exit', async (code) => {
      progressWin.close();
      if (code === 0) {
        resolve({ stdout, stderr });
      } else {
        await dialog.showErrorBox(
          'Instalación fallida',
          `El instalador retornó código ${code}.\n\nStdout:\n${stdout}\n\nStderr:\n${stderr}`
        );
        reject(new Error(`install-v4.ps1 exited with ${code}`));
      }
    });

    child.on('error', async (err) => {
      progressWin.close();
      await dialog.showErrorBox('Error al lanzar instalador', err.message);
      reject(err);
    });
  });
}

async function runGitPull(sourceRoot, branch) {
  const branchName = String(branch || 'main').trim() || 'main';
  return new Promise((resolve, reject) => {
    const child = spawn('git', ['-C', sourceRoot, 'pull', '--ff-only', 'origin', branchName], {
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe']
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', d => { stdout += d; });
    child.stderr.on('data', d => { stderr += d; });
    child.on('exit', code => {
      if (code === 0) {
        resolve({ stdout, stderr, branch: branchName });
      } else {
        reject(new Error((stderr || stdout || `git pull terminó con código ${code}`).trim()));
      }
    });
    child.on('error', reject);
  });
}

async function ensureBagoInstalled() {
  // P0-05 fix: this function is now "best effort" and never kills the app.
  // It always reports the resulting state to the UI via `bago:install-state`
  // so the Manager window can offer a recovery panel when something fails.
  let runtimeRoot = '';
  emitInstallState({ phase: 'detecting' });
  try {
    runtimeRoot = resolveBagoRuntimeRoot();
  } catch {
    runtimeRoot = '';
  }

  const packagedRoot = findPackagedRuntimeRoot();

  if (!runtimeRoot) {
    if (!packagedRoot) {
      emitInstallState({ phase: 'failed', error: 'runtime-empaketado-ausente', installDir: '' });
      await dialog.showErrorBox('BAGO Installation Manager', 'No se encontró el runtime de BAGO empaquetado. El instalador puede estar corrupto.');
      return '';
    }

    const result = await dialog.showMessageBox({
      type: 'question',
      buttons: ['Instalar ahora', 'Cancelar'],
      defaultId: 0,
      cancelId: 1,
      title: 'BAGO no está instalado',
      message: 'No se detectó una instalación de BAGO en este equipo.',
      detail: 'El Installation Manager puede instalar BAGO automáticamente usando el paquete incluido.',
      icon: ICON_PATH
    });

    if (result.response !== 0) {
      emitInstallState({ phase: 'cancelled' });
      return '';
    }

    const installDir = defaultInstallDir();
    emitInstallState({ phase: 'installing', installDir });
    try {
      await runInstallScript(packagedRoot, installDir);
    } catch (err) {
      emitInstallState({ phase: 'failed', error: String(err && err.message || err), installDir });
      return '';
    }
    const verified = resolveBagoRuntimeRoot();
    emitInstallState({ phase: 'ready', runtime: verified, installDir });
    await dialog.showMessageBox({
      type: 'info', buttons: ['OK'], title: 'Instalación completada',
      message: 'BAGO se instaló correctamente.', detail: `Ubicación: ${verified}`
    });
    return verified;
  }

  // CASO 2: hay instalación existente
  const prefs = loadPrefs();
  if (prefs.skipInstallPrompt) {
    emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
    return runtimeRoot;
  }

  const result = await dialog.showMessageBox({
    type: 'info',
    buttons: ['Continuar', 'Reparar configuración', 'Reinstalar / Actualizar', 'Nueva copia…'],
    defaultId: 0,
    cancelId: 0,
    title: 'BAGO ya está instalado',
    message: `Se detectó BAGO en:\n${runtimeRoot}`,
    detail: 'Puedes continuar, reparar la configuración, reinstalar desde cero o crear otra copia en un directorio diferente.',
    checkboxLabel: 'No volver a preguntar al inicio',
    checkboxChecked: false,
    icon: ICON_PATH
  });

  if (result.checkboxChecked) {
    prefs.skipInstallPrompt = true;
    savePrefs(prefs);
  }

  try {
    switch (result.response) {
      case 0: {
        emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
        return runtimeRoot;
      }
      case 1: {
        emitInstallState({ phase: 'repairing', installDir: runtimeRoot });
        await runInstallScript(packagedRoot, runtimeRoot, ['-RepairOnly'], 'Reparando configuración…');
        emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
        await dialog.showMessageBox({
          type: 'info', buttons: ['OK'], title: 'Reparación completada',
          message: 'La configuración de BAGO se reparó correctamente.', detail: `Ubicación: ${runtimeRoot}`
        });
        return runtimeRoot;
      }
      case 2: {
        emitInstallState({ phase: 'reinstalling', installDir: runtimeRoot });
        await runInstallScript(packagedRoot, runtimeRoot, [], 'Reinstalando BAGO…');
        const verified = resolveBagoRuntimeRoot();
        emitInstallState({ phase: 'ready', runtime: verified, installDir: runtimeRoot });
        await dialog.showMessageBox({
          type: 'info', buttons: ['OK'], title: 'Reinstalación completada',
          message: 'BAGO se reinstaló correctamente.', detail: `Ubicación: ${verified}`
        });
        return verified;
      }
      case 3: {
        if (!packagedRoot) {
          emitInstallState({ phase: 'failed', error: 'runtime-empaketado-ausente' });
          await dialog.showErrorBox('Error', 'No se encontró el runtime empaquetado para crear una nueva copia.');
          return runtimeRoot;
        }
        const { filePaths } = await dialog.showOpenDialog({
          title: 'Seleccionar directorio para la nueva copia de BAGO',
          defaultPath: path.join(path.dirname(defaultInstallDir()), 'BAGO-dev'),
          properties: ['openDirectory', 'createDirectory', 'promptToCreate']
        });
        if (!filePaths || !filePaths[0]) {
          emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
          return runtimeRoot;
        }
        const newDir = filePaths[0];
        emitInstallState({ phase: 'installing', installDir: newDir });
        await runInstallScript(packagedRoot, newDir, [], 'Instalando nueva copia…');
        emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: newDir });
        await dialog.showMessageBox({
          type: 'info', buttons: ['OK'], title: 'Nueva copia completada',
          message: 'La nueva copia de BAGO se instaló correctamente.', detail: `Ubicación: ${newDir}`
        });
        return runtimeRoot;
      }
      default:
        emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
        return runtimeRoot;
    }
  } catch (err) {
    emitInstallState({ phase: 'failed', error: String(err && err.message || err) });
    await dialog.showErrorBox('BAGO Installation Manager', 'Fallo en la operacion de instalacion: ' + (err && err.message || err));
    return '';
  }
}

function webChatStatus() {
  const procAlive = !!(webChatProcess && webChatProcess.exitCode === null && !webChatProcess.killed);
  const windowAlive = !!(webChatWindow && !webChatWindow.isDestroyed());
  return {
    running: !!(webChatState && (procAlive || windowAlive)),
    process_alive: procAlive,
    window_alive: windowAlive,
    ...(webChatState || {})
  };
}

async function probeWebChat(port) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 1200);
  try {
    const response = await fetch(`http://${CHAT_HOST}:${port}/session`, { signal: controller.signal });
    if (!response.ok) return false;
    const data = await response.json();
    return !!(data && data.session_id && data.provider);
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function waitForWebChat(port, timeoutMs = 12000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await probeWebChat(port)) return true;
    await new Promise(resolve => setTimeout(resolve, 350));
  }
  return false;
}

async function ensureWebChatServer(options = {}) {
  const requestedBasePath = String(options.basePath || '').trim();
  const runtimeRoot = resolveBagoRuntimeRoot();
  const basePath = requestedBasePath || runtimeRoot;
  const uiDist = resolveUiDist(runtimeRoot);
  const mayReuseExternal = !requestedBasePath || requestedBasePath === runtimeRoot;
  if (!uiDist) {
    throw new Error(`ui-react/dist no encontrado para ${runtimeRoot}`);
  }

  if (webChatState && webChatState.base_path === basePath && await probeWebChat(webChatState.port)) {
    return webChatState;
  }

  for (let port = CHAT_START_PORT; port < CHAT_START_PORT + 12; port += 1) {
    if (await probeWebChat(port)) {
      if (!mayReuseExternal) continue;
      webChatState = {
        host: CHAT_HOST,
        port,
        url: `http://${CHAT_HOST}:${port}/`,
        runtime_root: runtimeRoot,
        base_path: basePath,
        ui_dist: uiDist,
        reused: true
      };
      return webChatState;
    }

    const child = spawn(
      'python',
      [
        '-m', 'bago_core.launcher',
        '--base-path', basePath,
        'serve',
        '--host', CHAT_HOST,
        '--port', String(port),
        '--ui-dist', uiDist
      ],
      {
        cwd: runtimeRoot,
        stdio: 'ignore',
        windowsHide: true
      }
    );
    webChatProcess = child;
    child.once('exit', () => {
      if (webChatProcess === child) webChatProcess = null;
    });
    child.unref();

    if (await waitForWebChat(port)) {
      webChatState = {
        host: CHAT_HOST,
        port,
        url: `http://${CHAT_HOST}:${port}/`,
        pid: child.pid,
        runtime_root: runtimeRoot,
        base_path: basePath,
        ui_dist: uiDist,
        reused: false
      };
      return webChatState;
    }

    try { child.kill(); } catch {}
  }

  throw new Error('No se pudo arrancar BAGO web chat en un puerto local libre');
}

async function openWebChat(options = {}) {
  const state = await ensureWebChatServer(options || {});
  if (webChatWindow && !webChatWindow.isDestroyed()) {
    webChatWindow.focus();
    return { ...state, focused: true };
  }

  webChatWindow = new BrowserWindow({
    width: 1320,
    height: 900,
    minWidth: 980,
    minHeight: 680,
    title: 'BAGO Web Chat',
    icon: ICON_PATH,
    backgroundColor: '#080b12',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  webChatWindow.removeMenu();
  webChatWindow.on('closed', () => {
    webChatWindow = null;
  });
  webChatWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isExternalUrl(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  await webChatWindow.loadURL(state.url);
  return { ...state, focused: false };
}

function openCliChat(options = {}) {
  const runtimeRoot = resolveBagoRuntimeRoot();
  const basePath = String(options.basePath || '').trim() || runtimeRoot;
  const command = [
    `Set-Location -LiteralPath ${psSingleArg(runtimeRoot)}`,
    `python -m bago_core.launcher --base-path ${psSingleArg(basePath)} chat`
  ].join('; ');
  return runVisiblePowerShell(command);
}

function nodeAction(args) {
  const safe = Array.isArray(args) ? args.map(value => String(value || '')) : [];
  const nodeIndex = safe.indexOf('node');
  return nodeIndex >= 0 ? safe[nodeIndex + 1] || '' : '';
}

function runBagoNode(args) {
  // args: list of strings, e.g. ['node','status','--json']
  return new Promise((resolve, reject) => {
    const safe = (Array.isArray(args) ? args : []).map(a => String(a || ''));
    let runtimeRoot;
    try {
      runtimeRoot = resolveBagoRuntimeRoot();
    } catch (error) {
      reject(error);
      return;
    }
    const action = nodeAction(safe);
    const mutating = MUTATING_NODE_COMMANDS.has(action);
    if (mutating && activeNodeMutation) {
      reject(new Error(`Mutacion bloqueada: ${activeNodeMutation.action} sigue activa`));
      return;
    }
    if (mutating) {
      activeNodeMutation = {
        action,
        started_at: new Date().toISOString(),
        args: safe.slice()
      };
    }
    const cmd = `python -m bago_core.launcher ${safe.map(a => /[\s'"&|<>^]/.test(a) ? `"${a.replace(/"/g, '\\"')}"` : a).join(' ')}`;
    execFile(
      'python',
      ['-m', 'bago_core.launcher', ...safe],
      { cwd: runtimeRoot, windowsHide: true, maxBuffer: 16 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (mutating) activeNodeMutation = null;
        if (error) {
          reject(new Error(`${error.message}${stderr ? ` · ${stderr.trim()}` : ''} · cwd=${runtimeRoot} · cmd=${cmd}`));
          return;
        }
        resolve({ stdout, stderr, cmd, cwd: runtimeRoot });
      }
    );
  });
}

function runBagoSession(args) {
  return new Promise((resolve, reject) => {
    const safe = (Array.isArray(args) ? args : []).map(value => String(value || ''));
    let runtimeRoot;
    try {
      runtimeRoot = resolveBagoRuntimeRoot();
    } catch (error) {
      reject(error);
      return;
    }
    execFile(
      'python',
      ['-m', 'bago_core.session_control', '--base-path', runtimeRoot, ...safe],
      { cwd: runtimeRoot, windowsHide: true, timeout: 180000, maxBuffer: 16 * 1024 * 1024 },
      (error, stdout, stderr) => {
        let parsed;
        try {
          parsed = JSON.parse(String(stdout || '').trim());
        } catch (parseError) {
          reject(new Error(`SessionManager devolvio JSON invalido: ${parseError.message} · ${stderr || stdout}`));
          return;
        }
        if (error || !parsed.ok) {
          reject(new Error(String(parsed.error || stderr || error && error.message || 'SessionManager fallo')));
          return;
        }
        resolve(parsed);
      }
    );
  });
}

function checkTool(name, command, args = ['--version']) {
  return new Promise(resolve => {
    execFile(command, args, { windowsHide: true, timeout: 6000 }, (error, stdout, stderr) => {
      const text = String(stdout || stderr || '').trim().split(/\r?\n/)[0] || '';
      resolve({ name, ok: !error, detail: error ? error.message : text });
    });
  });
}

// P1-07 fix: a single preflight that the Manager runs BEFORE showing the
// install dialog. We check the four hard prerequisites (Python,
// PowerShell, write access to the install dir, disk space) and surface
// the result in a single, easy-to-render object. The previous design
// checked each one inline in the install path, which is why failures
// surfaced late and with no recovery path.
async function runInstallPreflight(targetDir) {
  const dir = targetDir || defaultInstallDir();
  const checks = await Promise.all([
    checkTool('Python', 'python', ['--version']),
    checkTool('PowerShell', 'powershell.exe', ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()']),
    checkTool('Git', 'git', ['--version']),
    checkTool('Ollama', 'ollama', ['--version'])
  ]);
  // Write probe: the destination must be writable by the current user.
  let writeOk = false;
  let writeDetail = '';
  try {
    const probe = path.join(dir, '.bago-preflight-' + Date.now());
    fs.writeFileSync(probe, 'ok');
    fs.unlinkSync(probe);
    writeOk = true;
    writeDetail = 'writable';
  } catch (err) {
    writeDetail = err.message || 'not writable';
  }
  // Disk space: at least 500 MB free on the volume hosting the install dir.
  let diskOk = false;
  let diskDetail = '';
  try {
    const root = path.parse(dir).root;
    if (process.platform === 'win32') {
      const out = require('child_process').spawnSync('powershell.exe',
        ['-NoProfile', '-Command', `(Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null -and ('${root}'.TrimEnd('\\') -like ($_.Root + '*')) } | Select-Object -First 1).Free`],
        { encoding: 'utf8', windowsHide: true, timeout: 6000 });
      const bytes = parseInt(String(out.stdout || '').replace(/[^0-9]/g, ''), 10);
      diskOk = bytes > 500 * 1024 * 1024;
      diskDetail = bytes ? (bytes / (1024 * 1024)).toFixed(0) + ' MB libres' : 'no se pudo leer';
    } else {
      const stat = require('child_process').spawnSync('df', ['-k', dir], { encoding: 'utf8', timeout: 6000 });
      const m = String(stat.stdout || '').split(/\s+/);
      const kb = parseInt(m[3] || '0', 10);
      diskOk = kb > 500 * 1024;
      diskDetail = kb ? (kb / 1024).toFixed(0) + ' MB libres' : 'no se pudo leer';
    }
  } catch (err) {
    diskDetail = err.message || 'no se pudo comprobar';
  }
  // Network probe: try to reach api.github.com so the user gets warned
  // early if the install would fail at the GitHub step.
  let networkOk = false;
  let networkDetail = '';
  try {
    const res = await new Promise(resolve => {
      const req = require('http').get('http://api.github.com', { timeout: 5000 }, r => {
        resolve({ ok: !!r.statusCode, code: r.statusCode });
        r.resume();
      });
      req.on('error', e => resolve({ ok: false, detail: e.message }));
      req.on('timeout', () => { req.destroy(); resolve({ ok: false, detail: 'timeout' }); });
    });
    networkOk = !!res.ok;
    networkDetail = res.ok ? ('HTTP ' + res.code) : (res.detail || 'sin conexion');
  } catch (err) {
    networkDetail = err.message;
  }
  return {
    target_dir: dir,
    checked_at: new Date().toISOString(),
    write: { ok: writeOk, detail: writeDetail },
    disk: { ok: diskOk, detail: diskDetail, minimum_mb: 500 },
    network: { ok: networkOk, detail: networkDetail },
    python: checks[0],
    powershell: checks[1],
    git: checks[2],
    ollama: checks[3]
  };
}

function runSupervisorCmd(args) {
  return new Promise((resolve, reject) => {
    let runtimeRoot;
    try {
      runtimeRoot = resolveBagoRuntimeRoot();
    } catch (error) {
      reject(error);
      return;
    }
    const script = path.join(runtimeRoot, 'scripts', 'bago_supervisor.py');
    if (!fs.existsSync(script)) {
      reject(new Error('bago_supervisor.py no encontrado en ' + runtimeRoot));
      return;
    }
    execFile(
      'python',
      [script, ...args],
      { cwd: runtimeRoot, windowsHide: true, timeout: 15000, maxBuffer: 4 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(`${error.message}${stderr ? ` · ${stderr.trim()}` : ''}`));
          return;
        }
        try {
          const parsed = JSON.parse(stdout.trim());
          resolve({ ok: true, data: parsed, raw: stdout });
        } catch {
          resolve({ ok: true, text: stdout.trim(), raw: stdout });
        }
      }
    );
  });
}

async function cleanupZombies() {
  // P1-06 fix: NEVER kill a python.exe that we cannot prove belongs to
  // BAGO. We only target processes whose `CommandLine` mentions a path we
  // know is part of BAGO (the install root, the bundled runtime, the
  // home-managed .bago directory) OR a script we ship (bago launcher /
  // bridge / webchat). Any python process outside that allowlist is left
  // alone so we do not interfere with other Python projects on the
  // machine.
  const managedPaths = [];
  try { managedPaths.push(resolveBundledRuntimeRoot()); } catch {}
  try { managedPaths.push(resolveInstalledRuntimeRoot()); } catch {}
  try { managedPaths.push(path.join(os.homedir(), '.bago')); } catch {}
  const allowList = managedPaths.filter(Boolean).map(p => p.replace(/\\/g, '\\\\').replace(/'/g, "''"));
  // Hard-coded script names that always identify a BAGO-owned python process.
  const scriptMarkers = ['launcher.py', 'bago_webchat.py', 'bago_supervisor.py', 'bridge.py'];
  const allowListJson = JSON.stringify(allowList);
  const markersJson = JSON.stringify(scriptMarkers);
  const command = `
    $ports = @(11434, 8080, 8081, 8082, 8083);
    $allowPaths = ${allowListJson} | Where-Object { $_ -and (Test-Path -LiteralPath $_) };
    $scriptMarkers = ${markersJson};
    $killed = 0;
    $matched = @();
    function Test-IsBagoProcess {
      param([string]$cmd, [string]$name)
      if (-not $cmd) { return $false }
      foreach ($p in $allowPaths) { if ($cmd -like ('*' + $p + '*')) { return $true } }
      foreach ($m in $scriptMarkers) { if ($cmd -like ('*' + $m)) { return $true } }
      # Some BAGO invocations go through "python -m bago_core.x"; match
      # against the module name as a last resort.
      if ($cmd -match 'bago_core[\\\\\\.\\s]') { return $true }
      if ($cmd -match 'bago[_-]?(webchat|supervisor|bridge|launcher|node_control)') { return $true }
      return $false
    }
    foreach ($p in $ports) {
      $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'TimeWait' -or $_.State -eq 'CloseWait' -or $_.State -eq 'FinWait2' };
      foreach ($c in $conns) {
        try {
          $proc = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $c.OwningProcess) -ErrorAction SilentlyContinue;
          if ($proc -and (Test-IsBagoProcess -cmd $proc.CommandLine -name $proc.Name)) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue;
            $killed++;
            $matched += [ordered]@{ pid = $c.OwningProcess; reason = 'stale-port'; cmd = $proc.CommandLine }
          }
        } catch {}
      }
    }
    # Also walk python processes and only kill the ones that match the
    # BAGO allowlist. This used to also kill orphaned python (no parent),
    # which is unsafe on a multi-project workstation.
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
      try {
        if (Test-IsBagoProcess -cmd $_.CommandLine -name $_.Name) {
          Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue;
          $killed++;
          $matched += [ordered]@{ pid = $_.ProcessId; reason = 'bago-process'; cmd = $_.CommandLine }
        }
      } catch {}
    }
    $payload = [ordered]@{ ok = $true; cleaned = $killed; matched = $matched; allowlist = $allowPaths }
    Write-Output ($payload | ConvertTo-Json -Depth 4 -Compress)
  `;
  return new Promise((resolve, reject) => {
    execFile(
      'powershell.exe',
      ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
      { windowsHide: true, timeout: 20000 },
      (error, stdout) => {
        if (error) {
          reject(error);
          return;
        }
        try {
          resolve(JSON.parse(stdout.trim()));
        } catch {
          resolve({ ok: true, text: stdout.trim() });
        }
      }
    );
  });
}

// P1-03 fix: the React UI (ui-react) and any other web surface need to
// open the Manager without hardcoding a dev port. We expose the actual URL
// from the main process so the URL is computed once and never goes stale.
function getManagerUrl() {
  // Prefer the file:// URL of the packaged Manager HTML; that always works
  // because loadFile() uses a real file path on disk.
  if (app.isPackaged) {
    try {
      return 'file:///' + MANAGER_HTML.replace(/\\/g, '/').replace(/^\//, '');
    } catch {
      // fall through to http case
    }
  }
  // When the local API is up we point at the same host on which it serves
  // the Manager; this is the only path that lets the React app link to the
  // Manager when it is hosted by the API and not by the Electron shell.
  const apiPort = (webChatState && webChatState.port) || process.env.BAGO_API_PORT || '';
  if (apiPort) return `http://${CHAT_HOST}:${apiPort}/manager/index.html`;
  return 'manager/index.html';
}

async function managerHealth() {
  let runtimeError = '';
  try {
    runtimeRoot = resolveBagoRuntimeRoot();
  } catch (error) {
    runtimeError = error.message;
  }
  const checks = await Promise.all([
    checkTool('Python', 'python', ['--version']),
    checkTool('PowerShell', 'powershell.exe', ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()']),
    checkTool('Git', 'git', ['--version']),
    checkTool('Ollama', 'ollama', ['--version'])
  ]);
  checks.unshift({
    name: 'BAGO runtime',
    ok: !!runtimeRoot,
    detail: runtimeRoot || runtimeError
  });
  checks.push({
    name: 'Node/Electron',
    ok: true,
    detail: `node ${process.versions.node} · electron ${process.versions.electron || 'dev'}`
  });
  return {
    checked_at: new Date().toISOString(),
    runtime_root: runtimeRoot,
    // P1-01 fix: report the Manager version (this Electron app) and the
    // runtime version (BAGO itself) separately so the UI can warn when
    // they drift instead of silently showing only one of the two.
    manager_version: readManagerVersion(),
    runtime_version: readRuntimeVersion(runtimeRoot),
    mutation: activeNodeMutation,
    lifecycle_job: releaseJobs && releaseJobs.activeLifecycleJob || '',
    release_jobs: releaseJobs ? releaseJobs.listJobs().length : 0,
    checks
  };
}

// P1-01 fix helpers: surface both the Manager and runtime versions in
// /healthz so the UI can detect drift and recommend a reinstall.
function readManagerVersion() {
  try {
    const pkg = require(path.join(ROOT_DIR, 'package.json'));
    if (pkg && pkg.version) return String(pkg.version);
  } catch {}
  try {
    const v = path.join(ROOT_DIR, 'release_version.txt');
    if (fs.existsSync(v)) return fs.readFileSync(v, 'utf8').trim();
  } catch {}
  return 'unknown';
}
function readRuntimeVersion(runtimeRoot) {
  if (!runtimeRoot) return '';
  try {
    const v = path.join(runtimeRoot, 'release_version.txt');
    if (fs.existsSync(v)) return fs.readFileSync(v, 'utf8').trim();
  } catch {}
  try {
    const v = path.join(runtimeRoot, 'install_manifest.json');
    if (fs.existsSync(v)) {
      const m = JSON.parse(fs.readFileSync(v, 'utf8'));
      if (m && m.runtime_version) return String(m.runtime_version);
    }
  } catch {}
  return '';
}

function requireReleaseJobs() {
  if (!releaseJobs) throw new Error('Release Job Manager no inicializado');
  return releaseJobs;
}

function initReleaseJobs() {
  releaseJobs = new ReleaseJobManager({
    rootDir: path.join(os.homedir(), '.bago', 'manager', 'release-jobs')
  });
  releaseJobs.on('changed', job => {
    for (const win of BrowserWindow.getAllWindows()) {
      if (!win.isDestroyed()) win.webContents.send('bago:release-job-changed', job);
    }
  });
}

// P0-05 fix: instead of `app.quit()`-ing on install errors, the Manager now
// keeps the window alive and pushes the install state to every renderer so
// the UI can offer a recovery panel (repair / change path / install as user /
// copy diagnostic). The state is also exposed via `bago:install-state` IPC.
let lastInstallState = { phase: 'pending', runtime: '', error: '', installDir: '' };
function emitInstallState(patch) {
  lastInstallState = { ...lastInstallState, ...patch, ts: Date.now() };
  for (const win of BrowserWindow.getAllWindows()) {
    if (!win.isDestroyed()) win.webContents.send('bago:install-state', lastInstallState);
  }
}
function getInstallState() { return lastInstallState; }

function createWindow() {
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

  win.loadFile(MANAGER_HTML);
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

app.setAppUserModelId('com.bago.installation-manager');

// Propagar INSTALLS_ROOT al preload vía env var para que scanInstallations lo incluya
process.env.BAGO_INSTALLS_ROOT = INSTALLS_ROOT;

ipcMain.handle('bago:supervisor-cmd', (_event, args) => runSupervisorCmd(args));
ipcMain.handle('bago:zombie-cleanup', () => cleanupZombies());
ipcMain.handle('bago:install-state-get', () => getInstallState());
ipcMain.handle('bago:open-web-chat', (_event, options) => openWebChat(options || {}));
ipcMain.handle('bago:open-cli-chat', (_event, options) => openCliChat(options || {}));
ipcMain.handle('bago:web-chat-status', () => webChatStatus());
ipcMain.handle('bago:manager-health', () => managerHealth());
// P1-07 fix: preflight endpoint the Manager calls BEFORE showing the
// install dialog. We return Python / PowerShell / write / disk / network
// in one payload so the UI can render a single panel.
ipcMain.handle('bago:install-preflight', (_event, payload) => runInstallPreflight(payload && payload.targetDir));
// P1-03 fix: report the URL where the Manager can be reached from a web
// view. In a packaged build this is a local file:// path or an
// http://127.0.0.1:<port> URL depending on the surface; the React app
// must not assume a fixed dev port.
ipcMain.handle('bago:get-installs-root', () => INSTALLS_ROOT);
ipcMain.handle('bago:manager-url', () => getManagerUrl());
// Tab BAGO dentro del manager: inicia el servidor web chat y devuelve la URL
// sin abrir una BrowserWindow separada. La ventana del manager embebe el chat
// como iframe dentro de su propia pestaña BAGO.
ipcMain.handle('bago:get-chat-url', async () => {
  const state = await ensureWebChatServer({});
  return state.url;
});
ipcMain.handle('bago:install-action', async (_event, payload) => {
  const { action, targetDir, sourceRoot, branch } = payload || {};
  let packagedRoot = '';
  const requirePackagedRoot = () => {
    if (!packagedRoot) packagedRoot = findPackagedRuntimeRoot();
    if (!packagedRoot) {
      throw new Error('No se encontró el runtime empaquetado.');
    }
    return packagedRoot;
  };
  let installDir = targetDir;
  if (action === 'repair') {
    const runtimePack = requirePackagedRoot();
    if (!installDir) {
      try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para reparar: ' + e.message); }
    }
    emitInstallState({ phase: 'repairing', installDir });
    try {
      await runInstallScript(runtimePack, installDir, ['-RepairOnly'], 'Reparando configuración…');
    } finally {
      emitInstallState({ phase: 'ready', installDir });
    }
    return { ok: true, action: 'repair', installDir };
  }
  if (action === 'reinstall') {
    const runtimePack = requirePackagedRoot();
    if (!installDir) {
      try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para reinstalar: ' + e.message); }
    }
    emitInstallState({ phase: 'reinstalling', installDir });
    try {
      await runInstallScript(runtimePack, installDir, [], 'Reinstalando BAGO…');
    } finally {
      emitInstallState({ phase: 'ready', installDir });
    }
    return { ok: true, action: 'reinstall', installDir };
  }
  if (action === 'new-copy') {
    const runtimePack = requirePackagedRoot();
    if (!installDir) throw new Error('Se requiere targetDir para nueva copia.');
    emitInstallState({ phase: 'installing', installDir });
    try {
      await runInstallScript(runtimePack, installDir, [], 'Instalando nueva copia…');
    } finally {
      emitInstallState({ phase: 'ready', installDir });
    }
    return { ok: true, action: 'new-copy', installDir };
  }
  if (action === 'source-update') {
    const rawSource = String(sourceRoot || '').trim();
    if (!rawSource) throw new Error('Se requiere sourceRoot para actualizar desde fuente/branch.');
    const cleanSource = path.resolve(rawSource);
    if (!fs.existsSync(path.join(cleanSource, 'install-v4.ps1')) || !fs.existsSync(path.join(cleanSource, 'bago_core', 'launcher.py'))) {
      throw new Error('La fuente no contiene install-v4.ps1 y bago_core/launcher.py.');
    }
    if (!installDir) {
      try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para actualizar: ' + e.message); }
    }
    const branchName = String(branch || 'main').trim() || 'main';
    await runGitPull(cleanSource, branchName);
    emitInstallState({ phase: 'reinstalling', installDir });
    try {
      await runInstallScript(cleanSource, installDir, [], `Actualizando desde fuente/branch (${branchName})…`);
    } finally {
      emitInstallState({ phase: 'ready', installDir });
    }
    return { ok: true, action: 'source-update', installDir, sourceRoot: cleanSource, branch: branchName };
  }
  throw new Error(`Acción desconocida: ${action}`);
});
ipcMain.handle('bago:session-cmd', (_event, args) => runBagoSession(args));
ipcMain.handle('bago:release-jobs-list', () => requireReleaseJobs().listJobs());
ipcMain.handle('bago:release-job-preflight', (_event, payload) => requireReleaseJobs().preflight(payload || {}));
ipcMain.handle('bago:release-job-start', (_event, payload) => requireReleaseJobs().startPrepare(payload || {}));
ipcMain.handle('bago:release-job-cancel', (_event, id) => requireReleaseJobs().cancel(id));
ipcMain.handle('bago:release-job-resume', (_event, id) => requireReleaseJobs().resume(id));
ipcMain.handle('bago:release-job-install', (_event, id) => requireReleaseJobs().install(id));
ipcMain.handle('bago:release-job-rollback', (_event, id) => requireReleaseJobs().rollback(id));
ipcMain.handle('bago:release-job-logs', (_event, id, limit) => requireReleaseJobs().getLogs(id, limit));
ipcMain.handle('bago:node-cmd', async (_event, args) => {
  const result = await runBagoNode(args);
  // JSON node commands return parsed data; mutation commands also emit JSON.
  const wantsJson = Array.isArray(args) && args.includes('--json');
  if (wantsJson || String(result.stdout || '').trim().startsWith('{')) {
    try {
      const parsed = JSON.parse(result.stdout);
      return { ok: true, data: parsed, raw: result.stdout, cmd: result.cmd, cwd: result.cwd };
    } catch (e) {
      return { ok: false, error: `JSON parse falló: ${e.message}`, raw: result.stdout, cmd: result.cmd };
    }
  }
  return { ok: true, text: result.stdout, cmd: result.cmd, cwd: result.cwd };
});

app.whenReady().then(async () => {
  // P0-05 fix: create the Manager window FIRST so the user always sees a
  // recovery/loading UI. The install/repair runs in parallel; its progress
  // is streamed to the renderer through `bago:install-state` events.
  // The window is the first thing the user sees; everything else (install,
  // release jobs) is wired up after the UI is on screen.
  createWindow();
  initReleaseJobs();
  ensureBagoInstalled().catch(err => {
    emitInstallState({ phase: 'failed', error: String(err && err.message || err) });
  });
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
