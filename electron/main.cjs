const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn, execFile } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');
const PACKAGED_RUNTIME_ROOT = path.join(process.resourcesPath || ROOT_DIR, 'app.asar.unpacked');
const MANAGER_HTML = path.join(ROOT_DIR, 'manager.html');
const ICON_PATH = path.join(ROOT_DIR, 'bago.ico');
const PRELOAD_PATH = path.join(__dirname, 'preload.cjs');

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
    const cmd = `python -m bago_core.launcher ${safe.map(a => /[\s'"&|<>^]/.test(a) ? `"${a.replace(/"/g, '\\"')}"` : a).join(' ')}`;
    execFile(
      'python',
      ['-m', 'bago_core.launcher', ...safe],
      { cwd: runtimeRoot, windowsHide: true, maxBuffer: 16 * 1024 * 1024 },
      (error, stdout, stderr) => {
        if (error) {
          reject(new Error(`${error.message}${stderr ? ` · ${stderr.trim()}` : ''} · cwd=${runtimeRoot} · cmd=${cmd}`));
          return;
        }
        resolve({ stdout, stderr, cmd, cwd: runtimeRoot });
      }
    );
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
  win.once('ready-to-show', () => win.show());

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
}

app.setAppUserModelId('com.bago.installation-manager');

ipcMain.handle('bago:run-command', (_event, command) => runVisiblePowerShell(command));
ipcMain.handle('bago:node-cmd', async (_event, args) => {
  const result = await runBagoNode(args);
  // If the user asked for --json, try to parse and return both raw + parsed.
  const wantsJson = Array.isArray(args) && args.includes('--json');
  if (wantsJson) {
    try {
      const parsed = JSON.parse(result.stdout);
      return { ok: true, data: parsed, raw: result.stdout, cmd: result.cmd };
    } catch (e) {
      return { ok: false, error: `JSON parse falló: ${e.message}`, raw: result.stdout, cmd: result.cmd };
    }
  }
  return { ok: true, text: result.stdout, cmd: result.cmd };
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
