const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn, execFile } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { ReleaseJobManager } = require('./release-job-manager.cjs');

const ROOT_DIR = path.join(__dirname, '..');
const PACKAGED_RUNTIME_ROOT = path.join(process.resourcesPath || ROOT_DIR, 'app.asar.unpacked');
const MANAGER_HTML = path.join(ROOT_DIR, 'manager', 'index.html');
const ICON_PATH = path.join(ROOT_DIR, 'bago.ico');
const PRELOAD_PATH = path.join(__dirname, 'preload.cjs');
const MUTATING_NODE_COMMANDS = new Set(['connect', 'disconnect', 'set-mode']);
const SMOKE_TEST = process.env.BAGO_MANAGER_SMOKE_TEST === '1';
let activeNodeMutation = null;
let releaseJobs = null;
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

function hasBagoRuntime(root) {
  return !!root && fs.existsSync(path.join(root, 'bago_core', 'launcher.py'));
}

function resolveBagoRuntimeRoot() {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
  const packagedFirst = app.isPackaged
    ? [PACKAGED_RUNTIME_ROOT, ROOT_DIR]
    : [ROOT_DIR, PACKAGED_RUNTIME_ROOT];
  const candidates = [
    ...packagedFirst,
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

ipcMain.handle('bago:run-command', (_event, command) => runVisiblePowerShell(command));
ipcMain.handle('bago:manager-health', () => managerHealth());
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

app.whenReady().then(() => {
  initReleaseJobs();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
