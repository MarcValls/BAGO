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

function resolveBagoRuntimeRoot() {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
  const packagedFirst = app.isPackaged
    ? [PACKAGED_RUNTIME_ROOT, ROOT_DIR]
    : [ROOT_DIR, PACKAGED_RUNTIME_ROOT];
  const candidates = [
    ...packagedFirst,
    DEV_PACKAGED_RUNTIME_ROOT,
    process.env.BAGO_ROOT || '',
    path.join(programFiles, 'BAGO'),
    home ? path.join(home, '.bago', 'active') : ''
  ];
  const found = candidates.find(hasBagoRuntime);
  if (!found) {
    throw new Error('No se encontro runtime BAGO para Node Control');
  }
  return found;
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
  const candidates = app.isPackaged
    ? [PACKAGED_RUNTIME_ROOT, ROOT_DIR]
    : [ROOT_DIR, PACKAGED_RUNTIME_ROOT];
  for (const root of candidates) {
    if (hasBagoRuntime(root)) return root;
  }
  const devRoot = DEV_PACKAGED_RUNTIME_ROOT;
  if (hasBagoRuntime(devRoot)) return devRoot;
  return '';
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

async function ensureBagoInstalled() {
  let runtimeRoot = '';
  try {
    runtimeRoot = resolveBagoRuntimeRoot();
  } catch {
    runtimeRoot = '';
  }

  const packagedRoot = findPackagedRuntimeRoot();

  if (!runtimeRoot) {
    // CASO 1: no hay instalación
    if (!packagedRoot) {
      await dialog.showErrorBox('BAGO Installation Manager', 'No se encontró el runtime de BAGO empaquetado. El instalador puede estar corrupto.');
      app.quit();
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
      app.quit();
      return '';
    }

    const installDir = path.join(process.env.ProgramFiles || 'C:\\Program Files', 'BAGO');
    await runInstallScript(packagedRoot, installDir);

    const verified = resolveBagoRuntimeRoot();
    await dialog.showMessageBox({
      type: 'info', buttons: ['OK'], title: 'Instalación completada',
      message: 'BAGO se instaló correctamente.', detail: `Ubicación: ${verified}`
    });
    return verified;
  }

  // CASO 2: hay instalación existente
  const prefs = loadPrefs();
  if (prefs.skipInstallPrompt) {
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

  switch (result.response) {
    case 0: {
      return runtimeRoot;
    }
    case 1: {
      await runInstallScript(packagedRoot, runtimeRoot, ['-RepairOnly'], 'Reparando configuración…');
      await dialog.showMessageBox({
        type: 'info', buttons: ['OK'], title: 'Reparación completada',
        message: 'La configuración de BAGO se reparó correctamente.', detail: `Ubicación: ${runtimeRoot}`
      });
      return runtimeRoot;
    }
    case 2: {
      await runInstallScript(packagedRoot, runtimeRoot, [], 'Reinstalando BAGO…');
      const verified = resolveBagoRuntimeRoot();
      await dialog.showMessageBox({
        type: 'info', buttons: ['OK'], title: 'Reinstalación completada',
        message: 'BAGO se reinstaló correctamente.', detail: `Ubicación: ${verified}`
      });
      return verified;
    }
    case 3: {
      if (!packagedRoot) {
        await dialog.showErrorBox('Error', 'No se encontró el runtime empaquetado para crear una nueva copia.');
        return runtimeRoot;
      }
      const { filePaths } = await dialog.showOpenDialog({
        title: 'Seleccionar directorio para la nueva copia de BAGO',
        defaultPath: path.join(process.env.ProgramFiles || 'C:\\Program Files', 'BAGO-dev'),
        properties: ['openDirectory', 'createDirectory', 'promptToCreate']
      });
      if (!filePaths || !filePaths[0]) return runtimeRoot;
      const newDir = filePaths[0];
      await runInstallScript(packagedRoot, newDir, [], 'Instalando nueva copia…');
      await dialog.showMessageBox({
        type: 'info', buttons: ['OK'], title: 'Nueva copia completada',
        message: 'La nueva copia de BAGO se instaló correctamente.', detail: `Ubicación: ${newDir}`
      });
      return runtimeRoot;
    }
    default:
      return runtimeRoot;
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
    const cmd = `python -m bago_core.launcher ${safe.map(a => /[\s'"&|<>^]/.test(a) ? `"${a.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"` : a).join(' ')}`;
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
  const command = `
    $ports = @(11434, 8080, 8081, 8082, 8083);
    $killed = 0;
    foreach ($p in $ports) {
      $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'TimeWait' -or $_.State -eq 'CloseWait' -or $_.State -eq 'FinWait2' };
      foreach ($c in $conns) {
        try {
          $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue;
          if ($proc -and ($proc.ProcessName -like '*python*' -or $proc.ProcessName -like '*node*' -or $proc.ProcessName -like '*electron*')) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue;
            $killed++;
          }
        } catch {}
      }
    }
    # Also kill orphaned python processes without parent that match BAGO patterns
    Get-WmiObject Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
      try {
        $parent = Get-Process -Id $_.ParentProcessId -ErrorAction SilentlyContinue;
        if (-not $parent -or $parent.HasExited) {
          Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue;
          $killed++;
        }
      } catch {}
    }
    Write-Output ('{\"ok\":true,\"cleaned\":' + $killed + '}');
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

async function managerHealth() {
  let runtimeRoot = '';
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
    mutation: activeNodeMutation,
    lifecycle_job: releaseJobs && releaseJobs.activeLifecycleJob || '',
    release_jobs: releaseJobs ? releaseJobs.listJobs().length : 0,
    checks
  };
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
          && result.views >= 7
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

ipcMain.handle('bago:supervisor-cmd', (_event, args) => runSupervisorCmd(args));
ipcMain.handle('bago:zombie-cleanup', () => cleanupZombies());
ipcMain.handle('bago:run-command', (_event, command) => runVisiblePowerShell(command));
ipcMain.handle('bago:open-web-chat', (_event, options) => openWebChat(options || {}));
ipcMain.handle('bago:open-cli-chat', (_event, options) => openCliChat(options || {}));
ipcMain.handle('bago:web-chat-status', () => webChatStatus());
ipcMain.handle('bago:manager-health', () => managerHealth());
ipcMain.handle('bago:install-action', async (_event, payload) => {
  const { action, targetDir } = payload || {};
  const packagedRoot = findPackagedRuntimeRoot();
  if (!packagedRoot) {
    throw new Error('No se encontró el runtime empaquetado.');
  }
  let installDir = targetDir;
  if (action === 'repair') {
    if (!installDir) {
      try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para reparar: ' + e.message); }
    }
    await runInstallScript(packagedRoot, installDir, ['-RepairOnly'], 'Reparando configuración…');
    return { ok: true, action: 'repair', installDir };
  }
  if (action === 'reinstall') {
    if (!installDir) {
      try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para reinstalar: ' + e.message); }
    }
    await runInstallScript(packagedRoot, installDir, [], 'Reinstalando BAGO…');
    return { ok: true, action: 'reinstall', installDir };
  }
  if (action === 'new-copy') {
    if (!installDir) throw new Error('Se requiere targetDir para nueva copia.');
    await runInstallScript(packagedRoot, installDir, [], 'Instalando nueva copia…');
    return { ok: true, action: 'new-copy', installDir };
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
  await ensureBagoInstalled();
  initReleaseJobs();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
