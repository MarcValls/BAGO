const { app } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

function hasManagerTree(root) {
  return !!root
    && fs.existsSync(path.join(root, 'package.json'))
    && fs.existsSync(path.join(root, 'electron', 'main.cjs'))
    && fs.existsSync(path.join(root, 'manager', 'index.html'));
}

function resolveRootDir() {
  const candidates = [
    path.resolve(__dirname, '..'),
    path.resolve(process.cwd()),
    path.resolve(app.getAppPath ? app.getAppPath() : ''),
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (hasManagerTree(candidate)) return candidate;
  }
  for (const candidate of candidates) {
    const parent = path.resolve(candidate, '..');
    if (hasManagerTree(parent)) return parent;
  }
  return path.resolve(__dirname, '..');
}

const ROOT_DIR = resolveRootDir();
const PACKAGED_RUNTIME_ROOT = path.join(process.resourcesPath || ROOT_DIR, 'app.asar.unpacked');
const PACKAGED_INSTALL_TREE_ROOT = path.join(process.resourcesPath || ROOT_DIR, 'release', 'v4', 'current');
const DEV_PACKAGED_RUNTIME_ROOT = path.join(ROOT_DIR, 'dist', 'win-unpacked', 'resources', 'app.asar.unpacked');
const DEV_INSTALL_TREE_ROOT = path.join(ROOT_DIR, 'release', 'v4', 'current');
const MANAGER_HTML = path.join(ROOT_DIR, 'manager', 'index.html');
const ICON_PATH = path.join(ROOT_DIR, 'bago.ico');
const PRELOAD_PATH = path.join(__dirname, 'preload.cjs');

// Resolve the React UI dist index.html — primary entry point for the main window
function resolveReactHtml() {
  const candidates = [
    path.join(ROOT_DIR, 'ui-react', 'dist', 'index.html'),
    path.join(ROOT_DIR, 'dist', 'index.html'),
    path.join(PACKAGED_RUNTIME_ROOT, 'ui-react', 'dist', 'index.html'),
    path.join(DEV_PACKAGED_RUNTIME_ROOT, 'ui-react', 'dist', 'index.html'),
  ];
  return candidates.find(c => fs.existsSync(c)) || MANAGER_HTML;
}

const REACT_HTML = resolveReactHtml();
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

function splitPathEntries(value) {
  return String(value || '')
    .split(path.delimiter)
    .map(item => item.trim())
    .filter(Boolean);
}

function isWindowsAppsAlias(candidate) {
  return /\\windowsapps\\python(?:3)?\.exe$/i.test(String(candidate || ''))
    || /\\windowsapps\\py\.exe$/i.test(String(candidate || ''));
}

function firstExistingExecutable(candidates, { allowWindowsApps = false } = {}) {
  for (const candidate of candidates) {
    if (!candidate) continue;
    try {
      const resolved = path.resolve(String(candidate));
      if (!allowWindowsApps && isWindowsAppsAlias(resolved)) continue;
      if (fs.existsSync(resolved)) return resolved;
    } catch {}
  }
  return '';
}

function collectVersionedPythonDirs(baseDir) {
  const base = String(baseDir || '').trim();
  if (!base || !fs.existsSync(base)) return [];
  try {
    return fs.readdirSync(base, { withFileTypes: true })
      .filter(entry => entry.isDirectory() && /^Python\d[\w.-]*$/i.test(entry.name))
      .map(entry => path.join(base, entry.name, 'python.exe'));
  } catch {
    return [];
  }
}

function resolveUserRoot() {
  const localAppData = process.env.LOCALAPPDATA || '';
  const home = process.env.USERPROFILE || process.env.HOME || '';
  if (localAppData) return path.join(localAppData, 'BAGO');
  if (home) return path.join(home, 'AppData', 'Local', 'BAGO');
  return '';
}

function resolveLegacyUserRoot() {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  return home ? path.join(home, '.bago') : '';
}

function resolvePythonCommand() {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  const localAppData = process.env.LOCALAPPDATA || (home ? path.join(home, 'AppData', 'Local') : '');
  const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
  const systemDrive = process.env.SystemDrive || 'C:';
  const pathCandidates = splitPathEntries(process.env.PATH).flatMap(entry => ([
    path.join(entry, 'python.exe'),
    path.join(entry, 'python3.exe'),
  ]));
  const pythonExe = firstExistingExecutable([
    process.env.BAGO_PYTHON,
    process.env.PYTHON,
    path.join(ROOT_DIR, '.venv', 'Scripts', 'python.exe'),
    path.join(resolveBundledRuntimeRoot(), 'python.exe'),
    path.join(resolveInstalledRuntimeRoot(), 'python.exe'),
    path.join(systemDrive + path.sep, 'Python314', 'python.exe'),
    path.join(systemDrive + path.sep, 'Python313', 'python.exe'),
    path.join(systemDrive + path.sep, 'Python312', 'python.exe'),
    ...collectVersionedPythonDirs(localAppData ? path.join(localAppData, 'Programs', 'Python') : ''),
    ...collectVersionedPythonDirs(programFiles),
    ...pathCandidates,
  ]);
  if (pythonExe) {
    return { command: pythonExe, argsPrefix: [], display: pythonExe };
  }

  const pyLauncher = firstExistingExecutable([
    ...splitPathEntries(process.env.PATH).map(entry => path.join(entry, 'py.exe')),
    path.join(process.env.WINDIR || 'C:\\Windows', 'py.exe'),
  ], { allowWindowsApps: true });
  if (pyLauncher) {
    return { command: pyLauncher, argsPrefix: ['-3'], display: `${pyLauncher} -3` };
  }

  return { command: 'python', argsPrefix: [], display: 'python' };
}

function hasBagoRuntime(root) {
  return !!root
    && fs.existsSync(path.join(root, 'bago_core', 'launcher.py'))
    && fs.existsSync(path.join(root, 'bago_core', 'session_control.py'));
}

function hasInstallManifest(root) {
  return !!root && fs.existsSync(path.join(root, 'install_manifest.json'));
}

function resolveBundledRuntimeRoot() {
  const candidates = app.isPackaged
    ? [PACKAGED_INSTALL_TREE_ROOT, PACKAGED_RUNTIME_ROOT, DEV_INSTALL_TREE_ROOT, DEV_PACKAGED_RUNTIME_ROOT]
    : [DEV_INSTALL_TREE_ROOT, ROOT_DIR, DEV_PACKAGED_RUNTIME_ROOT];
  for (const root of candidates) {
    if (hasBagoRuntime(root)) return root;
  }
  return '';
}

function resolveInstalledRuntimeRoot() {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
  const localAppData = resolveUserRoot();
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
    localAppData,
    home ? path.join(home, 'AppData', 'Local', 'BAGO', 'active') : '',
    home ? path.join(home, 'AppData', 'Local', 'BAGO', 'launch') : '',
    resolveLegacyUserRoot() ? path.join(resolveLegacyUserRoot(), 'active') : '',
    resolveLegacyUserRoot() ? path.join(resolveLegacyUserRoot(), 'launch') : ''
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

function resolveDevelopmentRuntimeRoot() {
  const home = process.env.USERPROFILE || process.env.HOME || '';
  const installed = resolveInstalledRuntimeRoot();
  const selectionFile = resolveUserRoot() ? path.join(resolveUserRoot(), 'install_selection.json') : '';
  const legacySelectionFile = resolveLegacyUserRoot() ? path.join(resolveLegacyUserRoot(), 'install_selection.json') : '';
  const candidates = [];

  for (const file of [selectionFile, legacySelectionFile]) {
    if (!file || !fs.existsSync(file)) continue;
    try {
      const payload = JSON.parse(readText(file) || '{}');
      const selectedDev = payload && payload.roles && payload.roles.dev && payload.roles.dev.path;
      if (selectedDev) candidates.push(String(selectedDev));
    } catch {}
  }

  if (home) {
    candidates.push(path.join(home, 'bago_fw'));
    candidates.push(path.join(home, 'BAGO'));
    candidates.push(path.join(home, 'AppData', 'Local', 'BAGO', 'dev'));
    const legacy = resolveLegacyUserRoot();
    if (legacy) candidates.push(path.join(legacy, 'dev'));
  }

  for (const candidate of candidates) {
    if (!candidate || !hasBagoRuntime(candidate)) continue;
    if (installed && path.resolve(candidate) === path.resolve(installed)) continue;
    return candidate;
  }
  return '';
}

function isUserOwnedLocation(candidate, home) {
  if (!candidate || !home) return false;
  const resolved = path.resolve(candidate).toLowerCase();
  const homeLc = path.resolve(home).toLowerCase();
  const localAppDataLc = (process.env.LOCALAPPDATA || path.join(home, 'AppData', 'Local')).toLowerCase();
  return resolved.startsWith(homeLc) || resolved.startsWith(localAppDataLc);
}

function resolveBagoRuntimeRoot() {
  const bundled = resolveBundledRuntimeRoot();
  if (bundled) return bundled;
  const installed = resolveInstalledRuntimeRoot();
  if (installed) return installed;
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
  REACT_HTML,
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
  resolveDevelopmentRuntimeRoot,
  resolvePythonCommand,
  isUserOwnedLocation,
  resolveBagoRuntimeRoot,
  resolveUiDist,
  findPackagedRuntimeRoot
};
