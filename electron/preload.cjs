const { contextBridge, clipboard, ipcRenderer } = require('electron');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');

function asPath(p) {
  return String(p || '').trim();
}

function exists(p) {
  try { return fs.existsSync(p); } catch { return false; }
}

function readText(p) {
  try { return fs.readFileSync(p, 'utf8').trim(); } catch { return ''; }
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
  const candidates = [path.join(root, 'release_version.txt'), path.join(root, '.bago', 'release_version.txt')];
  for (const candidate of candidates) {
    const text = readText(candidate);
    if (text) return text;
  }
  return '';
}

function classifyInstall(root, mode, description) {
  const has = rel => exists(path.join(root, rel));
  const statePath = [path.join(root, 'state', 'supervisor.json'), path.join(os.homedir(), '.bago', 'state', 'supervisor.json')].find(exists);
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
  return {
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
    has_seal: has(path.join('scripts', 'seal_release_415.py')),
    has_cli: has(path.join('bago_core', 'cli.py')),
    release_sig_short: shortSig(path.join(root, 'release.sig')),
    supervisor_state: supervisorState,
    supervisor_alive: supervisorAlive
  };
}

function scanInstallations(extraPaths = []) {
  const pf = process.env.ProgramFiles || 'C:\\Program Files';
  const home = process.env.USERPROFILE || os.homedir();
  const known = [
    [path.join(pf, 'BAGO'), 'system', 'Instalación de sistema'],
    [path.join(home, '.bago'), 'user', 'User root (default work)'],
    [path.join(home, '.bago', 'active'), 'work', 'Active / work'],
    [path.join(home, '.bago', 'launch'), 'ign', 'Ignition / launch'],
    [path.join(home, '.bago', 'dev'), 'dev', 'Dev tree (user)'],
    [path.join(home, 'BAGO'), 'source', 'Source tree']
  ];
  for (const p of extraPaths) {
    if (p) known.push([p, 'manual', 'Manual path']);
  }
  const seen = new Set();
  const installations = [];
  for (const [root, mode, description] of known) {
    const fullRoot = full(root);
    const key = fullRoot.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    installations.push(classifyInstall(fullRoot, mode, description));
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
        content_type: a.content_type || ''
      })) : []
    }));
}

function psSingle(s) {
  return `'${String(s || '').replace(/'/g, "''")}'`;
}

function buildInstallCommand(tag, installDir, mode = 'Express') {
  const cleanTag = String(tag || '').trim();
  const cleanDir = String(installDir || 'C:\\Program Files\\BAGO').trim();
  const cleanMode = String(mode || 'Express').trim();
  return [
    '$s = Join-Path $env:TEMP \'install-remote.ps1\'',
    "Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/MarcValls/BAGO/main/install-remote.ps1' -OutFile $s -UseBasicParsing",
    `& $s -Tag ${psSingle(cleanTag)} -InstallDir ${psSingle(cleanDir)} -Mode ${psSingle(cleanMode)}`
  ].join('; ');
}

function buildUninstallCommand(installDir, purgeState = false) {
  const root = String(installDir || '').trim();
  const script = path.join(root, 'bago-uninstall.ps1');
  const args = [`-InstallDir ${psSingle(root)}`];
  if (purgeState) args.push('-PurgeState');
  return `& ${psSingle(script)} ${args.join(' ')}`;
}

contextBridge.exposeInMainWorld('bagoElectron', {
  readClipboardText: () => clipboard.readText(),
  writeClipboardText: (text) => clipboard.writeText(String(text || '')),
  runCommand: (command) => ipcRenderer.invoke('bago:run-command', String(command || '')),
  scanInstallations: (extraPaths) => Promise.resolve(scanInstallations(Array.isArray(extraPaths) ? extraPaths : [])),
  fetchReleases,
  buildInstallCommand,
  buildUninstallCommand,
  // Node Control: invoca bago node <args> y devuelve {ok, data?, text?, raw?, cmd, error?}
  runNodeCommand: (args) => ipcRenderer.invoke('bago:node-cmd', Array.isArray(args) ? args.map(String) : []),
  runNodeStatus: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'status', '--json']),
  runNodeMatrix: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'matrix', '--json']),
  runNodePieces: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'pieces', '--json']),
  runNodeConnectors: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'connectors', '--json']),
  runNodeValidate: () => ipcRenderer.invoke('bago:node-cmd', ['node', 'validate', '--json'])
});
