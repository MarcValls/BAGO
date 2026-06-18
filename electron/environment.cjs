const { app } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const ROOT_DIR = path.join(__dirname, '..');
const PACKAGED_RUNTIME_ROOT = path.join(process.resourcesPath || ROOT_DIR, 'app.asar.unpacked');
const DEV_PACKAGED_RUNTIME_ROOT = path.join(ROOT_DIR, 'dist', 'win-unpacked', 'resources', 'app.asar.unpacked');
const MANAGER_HTML = path.join(ROOT_DIR, 'manager', 'index.html');
const ICON_PATH = path.join(ROOT_DIR, 'bago.ico');
const PRELOAD_PATH = path.join(__dirname, 'preload.cjs');
const INSTALLS_ROOT = app.isPackaged
  ? path.join(path.dirname(app.getPath('exe')), 'installations')
  : path.join(ROOT_DIR, 'installations');
const SMOKE_TEST = process.env.BAGO_MANAGER_SMOKE_TEST === '1';
const CHAT_HOST = '127.0.0.1';
const CHAT_START_PORT = Number(process.env.BAGO_MANAGER_CHAT_PORT || 8080);

function isExternalUrl(url) {
  return /^https?:\/\//i.test(url);
}

function runVisiblePowerShell(command, options = {}) {
  if (!command || typeof command !== 'string') {
    throw new Error('Comando vacío');
  }
  if (command.length > 12000) {
    throw new Error('Comando demasiado largo');
  }
  const visible = options.visible === true;
  const noExit = options.noExit === true;
  const cwd = options.cwd || app.getPath('home');
  const args = [
    ...(visible && noExit ? ['-NoExit'] : []),
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-Command',
    command
  ];
  const child = spawn(
    'powershell.exe',
    args,
    {
      cwd,
      detached: visible,
      stdio: 'ignore',
      windowsHide: !visible
    }
  );
  if (visible) child.unref();
  return { pid: child.pid };
}

function hasBagoRuntime(root) {
  return !!root
    && fs.existsSync(path.join(root, 'bago_core', 'launcher.py'))
    && fs.existsSync(path.join(root, 'bago_core', 'session_control.py'))
    && fs.existsSync(path.join(root, '.bago', 'core', 'version.py'))
    && fs.existsSync(path.join(root, '.bago', 'core', 'context_store.py'));
}

function hasInstallManifest(root) {
  return !!root && fs.existsSync(path.join(root, 'install_manifest.json'));
}

function resolveBundledRuntimeRoot() {
  const candidates = app.isPackaged
    ? [PACKAGED_RUNTIME_ROOT, DEV_PACKAGED_RUNTIME_ROOT]
    : [ROOT_DIR, DEV_PACKAGED_RUNTIME_ROOT];
  for (const root of candidates) {
    if (hasBagoRuntime(root)) return root;
  }
  return '';
}

function resolveInstalledRuntimeRoot() {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
  const localAppData = process.env.LOCALAPPDATA || (home ? path.join(home, 'AppData', 'Local') : '');
  const envOverride = process.env.BAGO_ROOT || '';

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

  const bundled = resolveBundledRuntimeRoot();
  const real = candidates.filter(c => {
    if (!hasBagoRuntime(c)) return false;
    if (bundled && path.resolve(c) === path.resolve(bundled)) return false;
    if (c === envOverride) return true;
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

module.exports = {
  ROOT_DIR,
  PACKAGED_RUNTIME_ROOT,
  DEV_PACKAGED_RUNTIME_ROOT,
  MANAGER_HTML,
  ICON_PATH,
  PRELOAD_PATH,
  INSTALLS_ROOT,
  SMOKE_TEST,
  CHAT_HOST,
  CHAT_START_PORT,
  isExternalUrl,
  runVisiblePowerShell,
  hasBagoRuntime,
  hasInstallManifest,
  resolveBundledRuntimeRoot,
  resolveInstalledRuntimeRoot,
  isUserOwnedLocation,
  resolveBagoRuntimeRoot,
  resolveUiDist,
  findPackagedRuntimeRoot
};
