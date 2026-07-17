const { contextBridge, clipboard, ipcRenderer } = require('electron');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');
const ROOT_DIR = path.join(__dirname, '..');

function resolveUserRoot() {
  const overrides = [
    process.env.BAGO_USER_ROOT,
    process.env.USER_BAGO_ROOT,
    process.env.BAGO_ROOT
  ];
  for (const candidate of overrides) {
    const clean = asPath(candidate);
    if (clean) return full(clean);
  }
  if (process.env.LOCALAPPDATA) return path.join(process.env.LOCALAPPDATA, 'BAGO');
  return path.join(os.homedir(), 'AppData', 'Local', 'BAGO');
}

const USER_ROOT = resolveUserRoot();

function asPath(p) {
  return String(p || '').trim();
}

function exists(p) {
  try { return fs.existsSync(p); } catch { return false; }
}

function readText(p) {
  try { return fs.readFileSync(p, 'utf8').trim(); } catch { return ''; }
}

function readVersionsCurrent(root) {
  try {
    const payload = JSON.parse(readText(path.join(root, 'versions.json')) || '{}');
    if (payload && typeof payload.current === 'string' && payload.current.trim()) {
      return payload.current.trim().replace(/^v/i, '');
    }
  } catch {}
  return '';
}

function readReleaseVersion() {
  const candidates = [
    path.join(ROOT_DIR, 'release_version.txt'),
    path.join(ROOT_DIR, '.gabo', 'release_version.txt'),
  ];
  for (const candidate of candidates) {
    const text = readText(candidate);
    if (text) return text.replace(/^v/i, '').trim();
  }
  return readVersionsCurrent(ROOT_DIR);
}

function firstExistingPath(paths) {
  for (const candidate of paths) {
    if (candidate && exists(candidate)) return candidate;
  }
  return '';
}

function resolveDefaultInstallDir() {
  const envCandidates = [
    process.env.BAGO_INSTALL_DIR,
    process.env.BAGO_INSTALL_ROOT,
    process.env.BAGO_INSTALLS_ROOT,
    process.env.BAGO_ROOT
  ];
  for (const candidate of envCandidates) {
    const clean = asPath(candidate);
    if (clean) return full(clean);
  }
  const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
  return path.join(programFiles, 'BAGO');
}

function pidAlive(pid) {
  const n = Number(pid || 0);
  if (!n) return false;
  try {
    process.kill(n, 0);
    return true;
  } catch {
    return false;
  }
}

function full(p) {
  try { return path.resolve(p); } catch { return asPath(p); }
}

function shortSig(filePath) {
  try {
    if (!fs.statSync(filePath).isFile()) return '';
    return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex').slice(0, 16) + '...';
  } catch {
    return '';
  }
}

const INSTALL_ROLES = ['active', 'dev', 'launch', 'writer', 'illustrator'];
const ROLE_LABELS = {
  active: 'Copia activa',
  dev: 'Copia de desarrollo',
  launch: 'Arranque principal',
  writer: 'Escritor',
  illustrator: 'Ilustrador'
};

function selectionPath() {
  return path.join(USER_ROOT, 'install_selection.json');
}

function emptySelection() {
  return { version: 1, updated_at: '', roles: {} };
}

function readInstallSelection() {
  const file = selectionPath();
  if (!exists(file)) return { ...emptySelection(), selection_file: file };
  try {
    const data = JSON.parse(readText(file) || '{}');
    const roles = data && typeof data.roles === 'object' && data.roles ? data.roles : {};
    return { version: 1, updated_at: data.updated_at || '', roles, selection_file: file };
  } catch {
    return { ...emptySelection(), selection_file: file };
  }
}

function normalizeForCompare(p) {
  return full(p).toLowerCase();
}

function rolePaths(selection = readInstallSelection()) {
  const out = {};
  const roles = selection.roles || {};
  for (const role of INSTALL_ROLES) {
    const entry = roles[role];
    if (entry && entry.path) out[role] = String(entry.path);
  }
  return out;
}

function rolesForPath(root, selection = readInstallSelection()) {
  const needle = normalizeForCompare(root);
  return Object.entries(rolePaths(selection))
    .filter(([, selected]) => normalizeForCompare(selected) === needle)
    .map(([role]) => role);
}

function writeInstallSelection(role, installPath) {
  const cleanRole = String(role || '').trim();
  const cleanPath = full(installPath);
  if (!INSTALL_ROLES.includes(cleanRole)) throw new Error(`Rol no valido: ${cleanRole}`);
  if (!exists(cleanPath)) throw new Error(`Ruta no encontrada: ${cleanPath}`);
  const file = selectionPath();
  const selection = readInstallSelection();
  selection.roles = selection.roles || {};
  selection.roles[cleanRole] = {
    path: cleanPath,
    label: ROLE_LABELS[cleanRole] || cleanRole,
    updated_at: new Date().toISOString()
  };
  selection.version = 1;
  selection.updated_at = new Date().toISOString();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(selection, null, 2) + '\n', 'utf8');
  fs.renameSync(tmp, file);
  selection.selection_file = file;
  return selection;
}

function chainRegistryPath() {
  return path.join(USER_ROOT, 'manager', 'chains.json');
}

function emptyChainRegistry() {
  return { version: 1, updated_at: '', chains: [] };
}

function readChainRegistry() {
  const file = chainRegistryPath();
  if (!exists(file)) return { ...emptyChainRegistry(), registry_file: file };
  try {
    const data = JSON.parse(readText(file) || '{}');
    const chains = data && Array.isArray(data.chains) ? data.chains : [];
    return { version: 1, updated_at: data.updated_at || '', chains, registry_file: file };
  } catch {
    return { ...emptyChainRegistry(), registry_file: file };
  }
}

function writeChainRegistry(payload) {
  const file = chainRegistryPath();
  const chains = payload && Array.isArray(payload.chains) ? payload.chains : [];
  const registry = { version: 1, updated_at: new Date().toISOString(), chains };
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(registry, null, 2) + '\n', 'utf8');
  fs.renameSync(tmp, file);
  registry.registry_file = file;
  return registry;
}

function readTag(root) {
  try {
    const tagsDir = path.join(root, 'bago_core', 'tags');
    if (!fs.statSync(tagsDir).isDirectory()) return '';
    const files = fs.readdirSync(tagsDir).filter(name => /^v.*\.json$/i.test(name));
    if (!files.length) return '';
    files.sort((a, b) => {
      const am = fs.statSync(path.join(tagsDir, a)).mtimeMs;
      const bm = fs.statSync(path.join(tagsDir, b)).mtimeMs;
      return bm - am;
    });
    return path.parse(files[0]).name;
  } catch {
    return '';
  }
}

function readVersion(root) {
  const candidates = [path.join(root, 'release_version.txt'), path.join(root, '.gabo', 'release_version.txt')];
  for (const candidate of candidates) {
    const text = readText(candidate);
    if (text) return text;
  }
  return readVersionsCurrent(root);
}

function classifyInstall(root, mode, description, selection = readInstallSelection()) {
  const has = rel => exists(path.join(root, rel));
  const statePath = firstExistingPath([
    path.join(root, 'state', 'supervisor.json'),
    path.join(USER_ROOT, 'state', 'supervisor.json')
  ]);
  let supervisorState = null;
  let supervisorAlive = false;
  if (statePath) {
    try {
      const payload = JSON.parse(readText(statePath));
      supervisorState = {
        pid: payload.pid,
        version: payload.version,
        started: payload.started_at,
        events: payload.events || 0
      };
      supervisorAlive = pidAlive(payload.pid);
    } catch (err) {
      supervisorState = { error: `${err.name}: ${err.message}` };
    }
  }
  const selectedRoles = rolesForPath(root, selection);
  const result = {
    path: full(root),
    exists: exists(root),
    mode: exists(root) ? mode : 'missing',
    description,
    version: readVersion(root),
    tag: readTag(root),
    has_bago_ps1: has('bago.ps1'),
    has_bago_cmd: has('bago.cmd'),
    has_bago_sh: has('bago.sh'),
    has_supervisor: has(path.join('scripts', 'bago_supervisor.py')),
    has_supervisor_pyw: has(path.join('scripts', 'bago_supervisor.pyw')),
    has_probe: has(path.join('scripts', 'probe.py')),
    has_cli: has(path.join('bago_core', 'cli.py')),
    release_sig_short: shortSig(path.join(root, 'release.sig')),
    supervisor_state: supervisorState,
    supervisor_alive: supervisorAlive,
    selection_roles: selectedRoles
  };
  for (const role of INSTALL_ROLES) {
    result[`selected_${role}`] = selectedRoles.includes(role);
  }
  return result;
}

function scanInstallations(extraPaths = []) {
  const pf = process.env.ProgramFiles || 'C:\\Program Files';
  const home = process.env.USERPROFILE || os.homedir();
  const installsRoot = process.env.BAGO_INSTALLS_ROOT || '';
  const selection = readInstallSelection();

  // Instalaciones gestionadas por el Manager (tienen prioridad)
  const managed = [];
  if (installsRoot) {
    try {
      fs.readdirSync(installsRoot, { withFileTypes: true })
        .filter(d => d.isDirectory())
        .forEach(d => managed.push([
          path.join(installsRoot, d.name),
          'managed',
          `Gestionada por Manager: ${d.name}`
        ]));
    } catch {}
  }

  const known = [
    ...managed,
    [path.join(pf, 'BAGO'), 'system', 'Instalación de sistema'],
    [USER_ROOT, 'user', 'User root (default work)'],
    [path.join(USER_ROOT, 'active'), 'work', 'Active / work'],
    [path.join(USER_ROOT, 'launch'), 'ign', 'Ignition / launch'],
    [path.join(USER_ROOT, 'dev'), 'dev', 'Dev tree (user)'],
    [path.join(home, 'BAGO'), 'source', 'Source tree']
  ];
  for (const p of extraPaths) {
    if (p) known.push([p, 'manual', 'Manual path']);
  }
  const selectedMode = { active: 'work', dev: 'dev', launch: 'ign', writer: 'manual', illustrator: 'manual' };
  for (const [role, selected] of Object.entries(rolePaths(selection))) {
    if (selected) known.push([selected, selectedMode[role] || 'manual', `Seleccion ${role}`]);
  }
  const seen = new Set();
  const installations = [];
  for (const [root, mode, description] of known) {
    const fullRoot = full(root);
    const key = fullRoot.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    installations.push(classifyInstall(fullRoot, mode, description, selection));
  }
  const active = installations.filter(i => i.exists);
  const alive = active.filter(i => i.supervisor_alive);
  return {
    summary: {
      scanned_at: new Date().toISOString(),
      platform: process.platform,
      node: process.versions.node,
      home,
      total_paths: installations.length,
      existing: active.length,
      missing: installations.length - active.length,
      with_supervisor: active.filter(i => i.has_supervisor).length,
      with_supervisor_alive: alive.length
    },
    selection: {
      file: selection.selection_file || selectionPath(),
      roles: rolePaths(selection)
    },
    installations
  };
}

async function fetchReleases() {
  const res = await fetch('https://api.github.com/repos/MarcValls/BAGO/releases?per_page=100', {
    headers: { Accept: 'application/vnd.github+json' }
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const releases = await res.json();
  return (Array.isArray(releases) ? releases : [])
    .filter(r => !r.draft)
    .sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0))
    .map(r => ({
      tag_name: r.tag_name || '',
      html_url: r.html_url || '',
      prerelease: !!r.prerelease,
      published_at: r.published_at || '',
      name: r.name || r.tag_name || '',
      assets: Array.isArray(r.assets) ? r.assets.map(a => ({
        name: a.name || '',
        browser_download_url: a.browser_download_url || '',
        content_type: a.content_type || '',
        size: Number(a.size || 0),
        digest: a.digest || '',
        state: a.state || '',
        updated_at: a.updated_at || '',
        download_count: Number(a.download_count || 0)
      })) : []
    }));
}

function psSingle(s) {
  return `'${String(s || '').replace(/'/g, "''")}'`;
}

function psEncoded(script) {
  return `powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand ${Buffer.from(String(script || ''), 'utf16le').toString('base64')}`;
}

function buildInstallCommand(tag, installDir, mode = 'Express') {
  const cleanTag = String(tag || '').trim();
  const cleanDir = String(installDir || resolveDefaultInstallDir()).trim();
  const cleanMode = String(mode || 'Express').trim();
  const releaseVersion = readReleaseVersion();
  const releaseTag = releaseVersion ? `v${releaseVersion}` : '';
  const targetTag = cleanTag || releaseTag;
  const bundledInstall = path.join(
    process.resourcesPath || ROOT_DIR,
    'app.asar.unpacked',
    'install-remote.ps1'
  );
  const fallbackInstall = path.join(ROOT_DIR, 'install-remote.ps1');
  const installScript = exists(bundledInstall) ? bundledInstall : fallbackInstall;
  return psEncoded([
    `$s = ${psSingle(installScript)}`,
    `& $s -Tag ${psSingle(targetTag)} -InstallDir ${psSingle(cleanDir)} -Mode ${psSingle(cleanMode)}`
  ].join('; '));
}

function buildSourceInstallCommand(sourceRoot, installDir, branch = 'main', mode = 'Express') {
  const cleanSource = full(String(sourceRoot || '').trim());
  const cleanDir = full(String(installDir || resolveDefaultInstallDir()).trim());
  const cleanBranch = String(branch || 'main').trim() || 'main';
  const cleanMode = String(mode || 'Express').trim();
  const installScript = path.join(cleanSource, 'install-v4.ps1');
  return [
    `$src = ${psSingle(cleanSource)}`,
    `$branch = ${psSingle(cleanBranch)}`,
    `Set-Location ${psSingle(cleanSource)}`,
    'git fetch --all --prune',
    `git pull --ff-only origin $branch`,
    `& ${psSingle(installScript)} -SourceRoot ${psSingle(cleanSource)} -InstallDir ${psSingle(cleanDir)} -Profile stable -Mode ${psSingle(cleanMode)}`
  ].join('; ');
}

function buildUninstallCommand(installDir, purgeState = false) {
  const root = String(installDir || '').trim();
  const script = path.join(root, 'bago-uninstall.ps1');
  const args = [`-InstallDir ${psSingle(root)}`];
  if (purgeState) args.push('-PurgeState');
  return `& ${psSingle(script)} ${args.join(' ')}`;
}

function buildRoleCommand(role, installDir) {
  const cleanRole = String(role || '').trim();
  const root = full(String(installDir || '').trim());
  const label = ROLE_LABELS[cleanRole] || cleanRole;
  const script = [
    `$role = ${psSingle(cleanRole)}`,
    `$root = ${psSingle(root)}`,
    `$label = ${psSingle(label)}`,
    "$userRoot = if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'BAGO' } else { Join-Path $env:USERPROFILE 'AppData\\Local\\BAGO' }",
    "$file = Join-Path $userRoot 'install_selection.json'",
    '$roles = @{}',
    "if (Test-Path $file) { try { $data = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json; if ($data.roles) { foreach ($p in $data.roles.PSObject.Properties) { $roles[$p.Name] = $p.Value } } } catch {} }",
    "$now = (Get-Date).ToUniversalTime().ToString('o')",
    '$roles[$role] = [ordered]@{ path = $root; label = $label; updated_at = $now }',
    '$out = [ordered]@{ version = 1; updated_at = $now; roles = $roles }',
    'New-Item -ItemType Directory -Force -Path (Split-Path -Parent $file) | Out-Null',
    '$out | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $file -Encoding UTF8',
    'Write-Host ("BAGO role " + $role + " -> " + $root)'
  ].join('; ');
  return psEncoded(script);
}

contextBridge.exposeInMainWorld('bagoElectron', {
  readClipboardText: () => clipboard.readText(),
  writeClipboardText: (text) => clipboard.writeText(String(text || '')),
  openWebChat: (options) => ipcRenderer.invoke('bago:open-web-chat', options || {}),
  openCliChat: (options) => ipcRenderer.invoke('bago:open-cli-chat', options || {}),
  webChatStatus: () => ipcRenderer.invoke('bago:web-chat-status'),
  shutdown: () => ipcRenderer.invoke('bago:shutdown'),
  scanInstallations: (extraPaths) => Promise.resolve(scanInstallations(Array.isArray(extraPaths) ? extraPaths : [])),
  readInstallSelection: () => Promise.resolve(readInstallSelection()),
  writeInstallSelection: (role, installPath) => Promise.resolve(writeInstallSelection(role, installPath)),
  readChainRegistry: () => Promise.resolve(readChainRegistry()),
  writeChainRegistry: (payload) => Promise.resolve(writeChainRegistry(payload || {})),
  fetchReleases: () => ipcRenderer.invoke('bago:fetch-releases'),
  buildInstallCommand,
  buildSourceInstallCommand,
  buildUninstallCommand,
  buildRoleCommand,
  getUserRoot: () => USER_ROOT,
  getInstallSelectionPath: () => selectionPath(),
  defaultInstallDir: () => resolveDefaultInstallDir(),
  installAction: (payload) => ipcRenderer.invoke('bago:install-action', payload || {}),
  managerHealth: () => ipcRenderer.invoke('bago:manager-health'),
  dependencyAction: (payload) => ipcRenderer.invoke('bago:dependency-action', payload || {}),
  runInstallPreflight: (payload) => ipcRenderer.invoke('bago:install-preflight', payload || {}),
  getManagerUrl: () => ipcRenderer.invoke('bago:manager-url'),
  onInstanceActive: (callback) => {
    if (typeof callback !== 'function') return;
    ipcRenderer.on('bago:instance-active', (_event, payload) => callback(payload));
  },
  chooseWorkspaceRoot: (options) => ipcRenderer.invoke('bago:workspace-choose-root', options || {}),
  chooseProjectRoot: (options) => ipcRenderer.invoke('bago:workspace-choose-root', options || {}),
  linkProjectRoot: (root) => ipcRenderer.invoke('bago:workspace-link-root', String(root || '')),
  getChatUrl: (options) => ipcRenderer.invoke('bago:get-chat-url', options || {}),
  getInstallsRoot: () => ipcRenderer.invoke('bago:get-installs-root'),
  getVersion: () => Promise.resolve(readReleaseVersion() || 'dev'),
  getInstallState: () => ipcRenderer.invoke('bago:install-state-get'),
  onInstallState: (callback) => {
    if (typeof callback !== 'function') return;
    ipcRenderer.on('bago:install-state', (_event, state) => callback(state));
  },
  runSessionCommand: (args) => ipcRenderer.invoke('bago:session-cmd', Array.isArray(args) ? args.map(String) : []),
  listReleaseJobs: () => ipcRenderer.invoke('bago:release-jobs-list'),
  preflightRelease: (payload) => ipcRenderer.invoke('bago:release-job-preflight', payload || {}),
  startReleaseJob: (payload) => ipcRenderer.invoke('bago:release-job-start', payload || {}),
  cancelReleaseJob: (id) => ipcRenderer.invoke('bago:release-job-cancel', String(id || '')),
  resumeReleaseJob: (id) => ipcRenderer.invoke('bago:release-job-resume', String(id || '')),
  installReleaseJob: (id) => ipcRenderer.invoke('bago:release-job-install', String(id || '')),
  rollbackReleaseJob: (id) => ipcRenderer.invoke('bago:release-job-rollback', String(id || '')),
  deleteReleaseJob: (id) => ipcRenderer.invoke('bago:release-job-delete', String(id || '')),
  releaseJobLogs: (id, limit = 200) => ipcRenderer.invoke('bago:release-job-logs', String(id || ''), Number(limit || 200)),
  projectAudit: () => ipcRenderer.invoke('bago:project-audit'),
  bagoAudit: () => ipcRenderer.invoke('bago:bago-audit'),
  eventLedger: (limit = 60) => ipcRenderer.invoke('bago:event-ledger', Number(limit || 60)),
  onReleaseJobChanged: (callback) => {
    if (typeof callback !== 'function') return;
    ipcRenderer.on('bago:release-job-changed', (_event, job) => callback(job));
  },
  // Node Control: invoca bago node <args> y devuelve {ok, data?, text?, raw?, cmd, error?}
  runNodeCommand: (args) => ipcRenderer.invoke('bago:node-cmd', Array.isArray(args) ? args.map(String) : []),
  runNodeStatus: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'status', '--json']),
  runNodeMatrix: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'matrix', '--json']),
  runNodePieces: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'pieces', '--json']),
  runNodeConnectors: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'connectors', '--json']),
  runNodeEvidence: (limit = 40) => ipcRenderer.invoke('bago:node-cmd', ['node', 'evidence', '--limit', String(limit), '--json']),
  runNodePreview: (installation, piece, mode) => ipcRenderer.invoke(
    'bago:node-cmd',
    ['node', 'preview', '--installation', String(installation || ''), '--piece', String(piece || ''), '--mode', String(mode || ''), '--json']
  ),
  runNodeValidate: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'validate', '--json']),
  runSupervisorCommand: (args) => ipcRenderer.invoke('bago:supervisor-cmd', Array.isArray(args) ? args.map(String) : []),
  cleanupZombies: () => ipcRenderer.invoke('bago:zombie-cleanup')
});
