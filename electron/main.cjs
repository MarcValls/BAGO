const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');
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

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
