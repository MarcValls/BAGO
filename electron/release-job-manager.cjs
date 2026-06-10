const { EventEmitter } = require('events');
const { spawn, execFile, execFileSync } = require('child_process');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const TERMINAL_STATES = new Set([
  'ready',
  'completed',
  'cancelled',
  'failed',
  'rolled-back'
]);
const ACTIVE_STATES = new Set([
  'queued',
  'downloading-checksum',
  'downloading-signature',
  'downloading',
  'verifying',
  'staging',
  'installing',
  'rolling-back'
]);

function nowIso() {
  return new Date().toISOString();
}

function safeName(value) {
  return String(value || 'asset').replace(/[^A-Za-z0-9._-]/g, '_').slice(0, 180);
}

function psQuote(value) {
  return `'${String(value || '').replace(/'/g, "''")}'`;
}

function normalizeTag(value) {
  return String(value || '').trim().replace(/^v/i, '');
}

function pathKey(value) {
  return path.resolve(String(value || '')).replace(/[\\/]+$/, '').toLowerCase();
}

function isInside(candidate, parent) {
  const childKey = pathKey(candidate);
  const parentKey = pathKey(parent);
  return childKey === parentKey || childKey.startsWith(parentKey + path.sep.toLowerCase());
}

function assetContract(release) {
  const assets = Array.isArray(release && release.assets) ? release.assets : [];
  const bundles = assets
    .filter(asset => /\.zip$/i.test(asset.name || '') && !/\.sha256$/i.test(asset.name || ''))
    .sort((a, b) => {
      const aIsRuntime = /^bago-v/i.test(String(a.name || ''));
      const bIsRuntime = /^bago-v/i.test(String(b.name || ''));
      if (aIsRuntime !== bIsRuntime) return aIsRuntime ? -1 : 1;
      return String(a.name || '').localeCompare(String(b.name || ''));
    });
  const exactChecksum = bundle => assets.find(
    asset => String(asset.name || '').toLowerCase() === `${bundle.name}.sha256`.toLowerCase()
  ) || null;
  const bundle = bundles.find(item => exactChecksum(item)) || bundles[0] || null;
  const checksum = bundle ? exactChecksum(bundle) : null;
  const signature = bundle && (
    assets.find(asset => String(asset.name || '').toLowerCase() === `${bundle.name}.sig`.toLowerCase())
    || assets.find(asset => String(asset.name || '').toLowerCase() === `${bundle.name}.asc`.toLowerCase())
  ) || null;
  return { bundle, checksum, signature };
}

function parseExpectedSha256(text, bundleName) {
  const lines = String(text || '').split(/\r?\n/).filter(Boolean);
  const named = lines.find(line => line.toLowerCase().includes(String(bundleName || '').toLowerCase()));
  const match = String(named || lines[0] || '').match(/\b([a-f0-9]{64})\b/i);
  return match ? match[1].toLowerCase() : '';
}

function readVersion(root) {
  for (const file of [
    path.join(root, 'release_version.txt'),
    path.join(root, '.bago', 'release_version.txt')
  ]) {
    try {
      const value = fs.readFileSync(file, 'utf8').trim();
      if (value) return value;
    } catch {}
  }
  return '';
}

function existingAncestor(target) {
  let current = path.resolve(target);
  while (!fs.existsSync(current)) {
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return current;
}

function directorySize(root, maxEntries = 250000) {
  if (!root || !fs.existsSync(root)) return 0;
  let bytes = 0;
  let entries = 0;
  const pending = [root];
  while (pending.length && entries < maxEntries) {
    const current = pending.pop();
    let children = [];
    try { children = fs.readdirSync(current, { withFileTypes: true }); } catch { continue; }
    for (const child of children) {
      entries += 1;
      if (entries >= maxEntries) break;
      const full = path.join(current, child.name);
      if (child.isSymbolicLink()) continue;
      if (child.isDirectory()) pending.push(full);
      else {
        try { bytes += fs.statSync(full).size; } catch {}
      }
    }
  }
  return bytes;
}

function diskFreeBytes(target) {
  try {
    const stat = fs.statfsSync(existingAncestor(target));
    return Number(stat.bavail) * Number(stat.bsize);
  } catch {
    return null;
  }
}

function findSourceRoot(root, maxDepth = 4) {
  const queue = [{ dir: root, depth: 0 }];
  while (queue.length) {
    const item = queue.shift();
    if (
      fs.existsSync(path.join(item.dir, 'install-v4.ps1'))
      && fs.existsSync(path.join(item.dir, 'bago_core', 'launcher.py'))
    ) {
      return item.dir;
    }
    if (item.depth >= maxDepth) continue;
    let children = [];
    try { children = fs.readdirSync(item.dir, { withFileTypes: true }); } catch { continue; }
    for (const child of children) {
      if (child.isDirectory() && !child.isSymbolicLink()) {
        queue.push({ dir: path.join(item.dir, child.name), depth: item.depth + 1 });
      }
    }
  }
  return '';
}

function processesUnder(target) {
  if (process.platform !== 'win32' || !target || !fs.existsSync(target)) return [];
  const script = [
    '$target = [string]$env:BAGO_TARGET_PATH',
    '$items = Get-CimInstance Win32_Process | Where-Object {',
    '  $_.ExecutablePath -and $_.ExecutablePath.StartsWith($target, [System.StringComparison]::OrdinalIgnoreCase)',
    '} | Select-Object ProcessId,Name,ExecutablePath',
    '$items | ConvertTo-Json -Compress'
  ].join('; ');
  try {
    const raw = execFileSync(
      'powershell.exe',
      ['-NoProfile', '-Command', script],
      {
        encoding: 'utf8',
        timeout: 6000,
        windowsHide: true,
        env: { ...process.env, BAGO_TARGET_PATH: path.resolve(target) }
      }
    ).trim();
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return (Array.isArray(parsed) ? parsed : [parsed]).map(item => ({
      pid: item.ProcessId,
      name: item.Name,
      path: item.ExecutablePath
    }));
  } catch {
    return [];
  }
}

function execFilePromise(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    execFile(command, args, options, (error, stdout, stderr) => {
      if (error) {
        error.stdout = stdout;
        error.stderr = stderr;
        reject(error);
        return;
      }
      resolve({ stdout, stderr });
    });
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

class ReleaseJobManager extends EventEmitter {
  constructor(options = {}) {
    super();
    this.rootDir = path.resolve(options.rootDir || path.join(process.cwd(), '.bago-manager-jobs'));
    this.jobsDir = path.join(this.rootDir, 'jobs');
    this.cacheDir = path.join(this.rootDir, 'cache');
    this.stagingDir = path.join(this.rootDir, 'staging');
    this.logsDir = path.join(this.rootDir, 'logs');
    this.allowedHosts = new Set(options.allowedHosts || [
      'github.com',
      'api.github.com',
      'objects.githubusercontent.com',
      'release-assets.githubusercontent.com',
      'github-releases.githubusercontent.com'
    ]);
    this.allowInsecureHosts = new Set(options.allowInsecureHosts || []);
    this.powerShell = options.powerShell || 'powershell.exe';
    this.jobs = new Map();
    this.activeLifecycleJob = '';
    this.runtime = new Map();
    this._init();
  }

  _init() {
    for (const dir of [this.rootDir, this.jobsDir, this.cacheDir, this.stagingDir, this.logsDir]) {
      fs.mkdirSync(dir, { recursive: true });
    }
    for (const name of fs.readdirSync(this.jobsDir)) {
      if (!name.endsWith('.json')) continue;
      try {
        const job = JSON.parse(fs.readFileSync(path.join(this.jobsDir, name), 'utf8'));
        if (ACTIVE_STATES.has(job.state)) {
          job.state = 'cancelled';
          job.error = 'Interrumpido al cerrar el gestor; se puede reanudar.';
          job.updated_at = nowIso();
        }
        this.jobs.set(job.id, job);
        this._persist(job);
      } catch {}
    }
  }

  _jobFile(id) {
    return path.join(this.jobsDir, `${safeName(id)}.json`);
  }

  _public(job) {
    return JSON.parse(JSON.stringify(job));
  }

  _persist(job) {
    const file = this._jobFile(job.id);
    const tmp = `${file}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(job, null, 2) + '\n', 'utf8');
    fs.renameSync(tmp, file);
  }

  _emit(job) {
    this._persist(job);
    const payload = this._public(job);
    this.emit('changed', payload);
    return payload;
  }

  _update(job, patch) {
    Object.assign(job, patch, { updated_at: nowIso() });
    return this._emit(job);
  }

  _log(job, message, level = 'info') {
    const line = JSON.stringify({ timestamp: nowIso(), level, message: String(message || '') });
    fs.appendFileSync(job.log_file, line + '\n', 'utf8');
    job.last_log = String(message || '');
    job.updated_at = nowIso();
    this._emit(job);
  }

  _get(id) {
    const job = this.jobs.get(String(id || ''));
    if (!job) throw new Error(`Job no encontrado: ${id}`);
    return job;
  }

  _validateUrl(raw) {
    const url = new URL(String(raw || ''));
    if (url.protocol !== 'https:' && !this.allowInsecureHosts.has(url.hostname)) {
      throw new Error(`URL no permitida: ${url.protocol}//${url.hostname}`);
    }
    if (!this.allowedHosts.has(url.hostname)) {
      throw new Error(`Host no permitido: ${url.hostname}`);
    }
    return url.toString();
  }

  _unsafeTarget(target) {
    const resolved = path.resolve(target);
    const root = path.parse(resolved).root;
    const protectedRoots = [
      root,
      process.env.USERPROFILE,
      process.env.ProgramFiles,
      process.env.ProgramData,
      this.rootDir
    ].filter(Boolean);
    return protectedRoots.some(item => pathKey(item) === pathKey(resolved));
  }

  listJobs() {
    return [...this.jobs.values()]
      .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
      .map(job => this._public(job));
  }

  getJob(id) {
    return this._public(this._get(id));
  }

  getLogs(id, limit = 200) {
    const job = this._get(id);
    let lines = [];
    try { lines = fs.readFileSync(job.log_file, 'utf8').split(/\r?\n/).filter(Boolean); } catch {}
    return lines.slice(-Math.max(1, Number(limit || 200))).map(line => {
      try { return JSON.parse(line); } catch { return { timestamp: '', level: 'info', message: line }; }
    });
  }

  preflight(payload = {}) {
    const release = payload.release || {};
    const rawTarget = String(payload.target || '').trim();
    const target = rawTarget ? path.resolve(rawTarget) : '';
    const action = String(payload.action || 'install');
    const uninstall = action === 'uninstall';
    const contract = assetContract(release);
    const warnings = [];
    const blockers = [];
    const prepareBlockers = [];
    const blockPrepare = message => {
      prepareBlockers.push(message);
      blockers.push(message);
    };
    if (!uninstall) {
      if (!contract.bundle) blockPrepare('La release no publica bundle ZIP.');
      if (!contract.checksum) blockPrepare('La release no publica checksum .sha256.');
      if (payload.require_signature && !contract.signature) blockPrepare('La política exige firma y la release no publica .sig/.asc.');
      if (!payload.require_signature && !contract.signature) warnings.push('Firma detached no publicada; SHA256 sigue siendo obligatorio.');
    }
    if (!target || this._unsafeTarget(target)) blockPrepare(`Destino inseguro: ${target || '(vacio)'}`);

    const targetExists = !!target && fs.existsSync(target);
    if (uninstall && !targetExists) blockers.push('La instalación indicada no existe.');
    const activeProcesses = targetExists ? processesUnder(target) : [];
    if (activeProcesses.length) {
      const sample = activeProcesses.slice(0, 4).map(item => `${item.name || 'process'}(${item.pid || '?'})`).join(', ');
      blockers.push(`Procesos activos dentro del destino: ${sample}. Cierra BAGO/gestor antes de instalar o actualizar.`);
    }
    const targetSize = targetExists ? directorySize(target) : 0;
    const ancestor = target ? existingAncestor(target) : '';
    let writable = false;
    if (ancestor) {
      try { fs.accessSync(ancestor, fs.constants.W_OK); writable = true; } catch {}
    }
    const programFiles = process.env.ProgramFiles || 'C:\\Program Files';
    const requiresElevation = !!target && isInside(target, programFiles) && !writable;
    if (!writable) blockers.push(requiresElevation
      ? 'El destino requiere elevación. Inicia el gestor como administrador.'
      : 'No hay permiso de escritura sobre el destino.');

    const bundleSize = Number(contract.bundle && contract.bundle.size || 0);
    const requiredBytes = uninstall
      ? targetSize + 64 * 1024 * 1024
      : Math.max(bundleSize * 3, 256 * 1024 * 1024) + targetSize;
    const freeBytes = target ? diskFreeBytes(target) : null;
    if (freeBytes !== null && freeBytes < requiredBytes) blockers.push('Espacio en disco insuficiente para staging y rollback.');
    if (action === 'update' && !targetExists) warnings.push('El destino no existe; el trabajo se comportará como instalación nueva.');
    if (action === 'separate' && targetExists) warnings.push('La instalación separada sobrescribirá un destino existente con backup.');

    return {
      ok: blockers.length === 0,
      prepare_ready: !uninstall && prepareBlockers.length === 0,
      install_ready: blockers.length === 0,
      checked_at: nowIso(),
      action,
      release: {
        tag_name: release.tag_name || '',
        prerelease: !!release.prerelease,
        published_at: release.published_at || ''
      },
      contract: {
        bundle: contract.bundle || null,
        checksum: contract.checksum || null,
        signature: contract.signature || null,
        checksum_required: true,
        signature_required: !!payload.require_signature
      },
      target: {
        path: target,
        exists: targetExists,
        current_version: targetExists ? readVersion(target) : '',
        size: targetSize,
        writable,
        requires_elevation: requiresElevation,
        owner_check: writable ? 'writable' : 'blocked',
        active_processes: activeProcesses
      },
      disk: {
        free_bytes: freeBytes,
        required_bytes: requiredBytes,
        sufficient: freeBytes === null ? null : freeBytes >= requiredBytes
      },
      impact: {
        backup_required: targetExists,
        shared_pieces_preserved: true,
        connector_registry_preserved: true,
        overwrite_target: !uninstall && targetExists,
        remove_runtime_only: uninstall
      },
      warnings,
      prepare_blockers: prepareBlockers,
      blockers
    };
  }

  startPrepare(payload = {}) {
    const release = payload.release || {};
    const contract = assetContract(release);
    if (!contract.bundle || !contract.checksum) {
      throw new Error('Contrato incompleto: se requieren ZIP y SHA256.');
    }
    const preflight = this.preflight(payload);
    if (!preflight.prepare_ready) throw new Error(preflight.prepare_blockers.join(' '));
    this._validateUrl(contract.bundle.browser_download_url);
    this._validateUrl(contract.checksum.browser_download_url);
    if (contract.signature) this._validateUrl(contract.signature.browser_download_url);
    const id = `release-${Date.now()}-${crypto.randomBytes(3).toString('hex')}`;
    const job = {
      id,
      kind: 'release',
      action: String(payload.action || 'install'),
      state: 'queued',
      created_at: nowIso(),
      updated_at: nowIso(),
      release,
      target: path.resolve(String(payload.target || '')),
      mode: String(payload.mode || 'Express'),
      require_signature: !!payload.require_signature,
      progress: { phase: 'queued', transferred: 0, total: Number(contract.bundle.size || 0), percent: 0 },
      verification: null,
      compatibility: null,
      source_root: '',
      bundle_path: '',
      backup_path: '',
      rollback_available: false,
      cancel_requested: false,
      error: '',
      log_file: path.join(this.logsDir, `${id}.jsonl`)
    };
    this.jobs.set(id, job);
    this._emit(job);
    this._log(job, `Job creado para ${release.tag_name || contract.bundle.name} -> ${job.target}`);
    this._runPrepare(job).catch(error => this._fail(job, error));
    return this._public(job);
  }

  resume(id) {
    const job = this._get(id);
    if (!['cancelled', 'failed'].includes(job.state)) throw new Error(`El job ${id} no se puede reanudar desde ${job.state}.`);
    job.cancel_requested = false;
    job.error = '';
    this._update(job, { state: 'queued', progress: { ...job.progress, phase: 'queued' } });
    this._log(job, 'Job reanudado.');
    this._runPrepare(job).catch(error => this._fail(job, error));
    return this._public(job);
  }

  cancel(id) {
    const job = this._get(id);
    if (TERMINAL_STATES.has(job.state)) return this._public(job);
    job.cancel_requested = true;
    const runtime = this.runtime.get(job.id) || {};
    if (runtime.controller) runtime.controller.abort();
    if (runtime.child) this._killTree(runtime.child.pid);
    this._log(job, 'Cancelación solicitada.', 'warn');
    return this._public(job);
  }

  async install(id) {
    const job = this._get(id);
    if (job.state !== 'ready') throw new Error(`El job ${id} no está listo para instalar.`);
    if (this.activeLifecycleJob) throw new Error(`Trabajo de ciclo de vida activo: ${this.activeLifecycleJob}`);
    const preflight = this.preflight({
      release: job.release,
      target: job.target,
      action: job.action,
      require_signature: job.require_signature
    });
    job.preflight = preflight;
    if (!preflight.ok) {
      this._update(job, { state: 'ready', error: preflight.blockers.join(' ') });
      this._log(job, `Instalación bloqueada por preflight: ${job.error}`, 'warn');
      throw new Error(job.error);
    }
    this.activeLifecycleJob = job.id;
    job.cancel_requested = false;
    this._update(job, { state: 'installing', progress: { phase: 'installing', transferred: 0, total: 1, percent: 0 } });
    this._log(job, `Instalación iniciada sobre ${job.target}.`);
    try {
      await this._prepareAtomicBackup(job);
      await this._runInstaller(job);
      await this._validateInstalled(job);
      this._update(job, {
        state: 'completed',
        rollback_available: !!job.backup_path || !!job.created_target,
        progress: { phase: 'completed', transferred: 1, total: 1, percent: 100 },
        error: ''
      });
      this._log(job, `Instalación validada: ${job.target}.`);
    } catch (error) {
      this._log(job, `Instalación fallida: ${error.message}`, 'error');
      await this._restoreAtomicBackup(job, true);
      if (job.cancel_requested) {
        this._update(job, { state: 'cancelled', error: 'Instalación cancelada y rollback aplicado.' });
      } else {
        this._update(job, { state: 'failed', error: `${error.message}; rollback aplicado.` });
      }
    } finally {
      this.activeLifecycleJob = '';
      this.runtime.delete(job.id);
    }
    return this._public(job);
  }

  async rollback(id) {
    const job = this._get(id);
    if (!job.rollback_available) throw new Error(`El job ${id} no tiene rollback disponible.`);
    if (this.activeLifecycleJob) throw new Error(`Trabajo de ciclo de vida activo: ${this.activeLifecycleJob}`);
    this.activeLifecycleJob = job.id;
    this._update(job, { state: 'rolling-back', progress: { phase: 'rolling-back', transferred: 0, total: 1, percent: 0 } });
    try {
      await this._restoreAtomicBackup(job, false);
      this._update(job, {
        state: 'rolled-back',
        rollback_available: false,
        progress: { phase: 'rolled-back', transferred: 1, total: 1, percent: 100 },
        error: ''
      });
      this._log(job, `Rollback manual completado: ${job.target}.`, 'warn');
    } finally {
      this.activeLifecycleJob = '';
    }
    return this._public(job);
  }

  async waitFor(id, states = [...TERMINAL_STATES], timeoutMs = 30000) {
    const wanted = new Set(states);
    const existing = this._get(id);
    if (wanted.has(existing.state)) return this._public(existing);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.removeListener('changed', listener);
        reject(new Error(`Timeout esperando job ${id}.`));
      }, timeoutMs);
      const listener = job => {
        if (job.id === id && wanted.has(job.state)) {
          clearTimeout(timer);
          this.removeListener('changed', listener);
          resolve(job);
        }
      };
      this.on('changed', listener);
    });
  }

  async _runPrepare(job) {
    const contract = assetContract(job.release);
    const releaseDir = path.join(this.cacheDir, safeName(job.release.tag_name || 'release'));
    fs.mkdirSync(releaseDir, { recursive: true });
    const checksumPath = path.join(releaseDir, safeName(contract.checksum.name));
    const bundlePath = path.join(releaseDir, safeName(contract.bundle.name));
    const signaturePath = contract.signature ? path.join(releaseDir, safeName(contract.signature.name)) : '';
    job.bundle_path = bundlePath;
    job.cancel_requested = false;

    this._update(job, { state: 'downloading-checksum', progress: { phase: 'checksum', transferred: 0, total: Number(contract.checksum.size || 0), percent: 0 } });
    await this._download(job, contract.checksum, checksumPath, false);
    const expected = parseExpectedSha256(fs.readFileSync(checksumPath, 'utf8'), contract.bundle.name);
    if (!expected) throw new Error('El asset SHA256 no contiene un hash válido.');

    if (contract.signature) {
      this._update(job, { state: 'downloading-signature', progress: { phase: 'signature', transferred: 0, total: Number(contract.signature.size || 0), percent: 0 } });
      await this._download(job, contract.signature, signaturePath, false);
    }

    this._update(job, { state: 'downloading', progress: { phase: 'bundle', transferred: 0, total: Number(contract.bundle.size || 0), percent: 0 } });
    const downloadedBundlePath = await this._download(job, contract.bundle, bundlePath, true);
    job.bundle_path = downloadedBundlePath;
    if (job.cancel_requested) throw new Error('cancelled');

    this._update(job, { state: 'verifying', progress: { phase: 'verifying', transferred: 0, total: 1, percent: 0 } });
    const actual = await this._sha256(downloadedBundlePath);
    const publishedDigest = String(contract.bundle.digest || '').replace(/^sha256:/i, '').toLowerCase();
    if (actual !== expected) throw new Error(`SHA256 no coincide: esperado ${expected}, obtenido ${actual}.`);
    if (publishedDigest && actual !== publishedDigest) throw new Error('El digest publicado por GitHub no coincide con el bundle.');
    const magic = Buffer.alloc(4);
    const handle = fs.openSync(downloadedBundlePath, 'r');
    fs.readSync(handle, magic, 0, 4, 0);
    fs.closeSync(handle);
    if (magic[0] !== 0x50 || magic[1] !== 0x4b) throw new Error('El asset no tiene cabecera ZIP válida.');
    const signature = await this._verifySignature(job, signaturePath, downloadedBundlePath);

    this._update(job, { state: 'staging', progress: { phase: 'staging', transferred: 0, total: 1, percent: 0 } });
    const stagePath = path.join(this.stagingDir, safeName(job.id));
    if (fs.existsSync(stagePath)) fs.rmSync(stagePath, { recursive: true, force: true });
    fs.mkdirSync(stagePath, { recursive: true });
    await execFilePromise(this.powerShell, [
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-Command',
      `Expand-Archive -LiteralPath ${psQuote(downloadedBundlePath)} -DestinationPath ${psQuote(stagePath)} -Force`
    ], { windowsHide: true, maxBuffer: 16 * 1024 * 1024 });
    const sourceRoot = findSourceRoot(stagePath);
    if (!sourceRoot) throw new Error('El ZIP no contiene install-v4.ps1 y bago_core/launcher.py compatibles.');
    const stagedVersion = readVersion(sourceRoot);
    const tagMatches = !stagedVersion || normalizeTag(stagedVersion) === normalizeTag(job.release.tag_name);
    if (!tagMatches) throw new Error(`Versión incompatible: release ${job.release.tag_name}, bundle ${stagedVersion}.`);

    job.source_root = sourceRoot;
    job.verification = {
      algorithm: 'sha256',
      expected_sha256: expected,
      actual_sha256: actual,
      github_digest: publishedDigest || '',
      checksum_asset: contract.checksum.name,
      signature,
      zip_magic: magic.toString('hex'),
      verified_at: nowIso()
    };
    job.compatibility = {
      ok: true,
      source_root: sourceRoot,
      release_version: stagedVersion,
      tag_matches: tagMatches,
      required_files: {
        installer: true,
        launcher: true
      }
    };
    this._update(job, {
      state: 'ready',
      error: '',
      progress: { phase: 'ready', transferred: 1, total: 1, percent: 100 }
    });
    this._log(job, `Bundle verificado y preparado: ${contract.bundle.name}.`);
  }

  async _download(job, asset, finalPath, resume) {
    const partPath = `${finalPath}.part`;
    const expectedSize = Number(asset.size || 0);
    const existing = resume && fs.existsSync(partPath) ? fs.statSync(partPath).size : 0;
    const controller = new AbortController();
    this.runtime.set(job.id, { ...(this.runtime.get(job.id) || {}), controller });
    if (resume && existing > 0 && expectedSize > 0) {
      if (existing === expectedSize) {
        return await this._finalizeDownloadedFile(job, partPath, finalPath, asset, true);
      }
      if (existing > expectedSize) {
        fs.rmSync(partPath, { force: true });
      }
    }
    const headers = existing > 0 ? { Range: `bytes=${existing}-` } : {};
    const response = await fetch(this._validateUrl(asset.browser_download_url), {
      headers,
      redirect: 'follow',
      signal: controller.signal
    });
    this._validateUrl(response.url);
    if (response.status === 416) {
      if (expectedSize > 0 && fs.existsSync(partPath) && fs.statSync(partPath).size === expectedSize) {
        this._log(job, `HTTP 416 para ${asset.name}; se reutiliza el archivo completo en caché.`, 'warn');
        return await this._finalizeDownloadedFile(job, partPath, finalPath, asset, true);
      }
      this._log(job, `HTTP 416 para ${asset.name}; se reinicia la descarga desde cero.`, 'warn');
      if (fs.existsSync(partPath)) fs.rmSync(partPath, { force: true });
      return this._download(job, asset, finalPath, false);
    }
    if (!response.ok && response.status !== 206) throw new Error(`Descarga HTTP ${response.status}: ${asset.name}`);
    const appending = existing > 0 && response.status === 206;
    if (!appending && fs.existsSync(partPath)) fs.rmSync(partPath, { force: true });
    const start = appending ? existing : 0;
    const headerLength = Number(response.headers.get('content-length') || 0);
    const total = expectedSize || start + headerLength;
    const stream = fs.createWriteStream(partPath, { flags: appending ? 'a' : 'w' });
    const reader = response.body.getReader();
    let transferred = start;
    let lastEmitAt = 0;
    let lastPercent = -1;
    try {
      while (true) {
        if (job.cancel_requested) throw new Error('cancelled');
        const { done, value } = await reader.read();
        if (done) break;
        if (!stream.write(Buffer.from(value))) {
          await new Promise(resolve => stream.once('drain', resolve));
        }
        transferred += value.byteLength;
        const percent = total ? Math.min(99, Math.floor(transferred * 100 / total)) : 0;
        job.progress = { phase: job.progress.phase, transferred, total, percent };
        job.updated_at = nowIso();
        const now = Date.now();
        if (percent !== lastPercent && now - lastEmitAt >= 120) {
          lastEmitAt = now;
          lastPercent = percent;
          this._emit(job);
        }
      }
      await new Promise((resolve, reject) => stream.end(error => error ? reject(error) : resolve()));
      return await this._finalizeDownloadedFile(job, partPath, finalPath, asset, false);
    } catch (error) {
      stream.destroy();
      if (job.cancel_requested || error.name === 'AbortError' || error.message === 'cancelled') {
        this._update(job, { state: 'cancelled', error: 'Descarga cancelada; archivo parcial conservado para reanudar.' });
        this._log(job, `Descarga cancelada en ${transferred}/${total} bytes.`, 'warn');
        throw new Error('cancelled');
      }
      throw error;
    } finally {
      const runtime = this.runtime.get(job.id) || {};
      delete runtime.controller;
      this.runtime.set(job.id, runtime);
    }
  }

  async _removeFileWithRetry(filePath, attempts = 8, delayMs = 250) {
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        if (fs.existsSync(filePath)) {
          fs.rmSync(filePath, { force: true });
        }
        return true;
      } catch (error) {
        if (attempt + 1 >= attempts) throw error;
        await sleep(delayMs);
      }
    }
    return true;
  }

  async _finalizeDownloadedFile(job, partPath, finalPath, asset, allowCompleteReuse) {
    if (!fs.existsSync(partPath)) {
      if (fs.existsSync(finalPath)) return finalPath;
      throw new Error(`El archivo temporal no existe: ${partPath}`);
    }
    const partSize = fs.statSync(partPath).size;
    const expectedSize = Number(asset.size || 0);
    if (allowCompleteReuse && expectedSize > 0 && partSize === expectedSize && fs.existsSync(finalPath)) {
      try {
        await this._removeFileWithRetry(finalPath, 2, 100);
      } catch (error) {
        this._log(job, `No se pudo liberar ${finalPath}; se reutiliza el ZIP completo en caché.`, 'warn');
        return partPath;
      }
    } else if (fs.existsSync(finalPath)) {
      try {
        await this._removeFileWithRetry(finalPath, 4, 150);
      } catch (error) {
        this._log(job, `No se pudo reemplazar ${finalPath}; se reutiliza el archivo parcial/completo en caché.`, 'warn');
        return partPath;
      }
    }
    try {
      if (fs.existsSync(finalPath)) {
        await this._removeFileWithRetry(finalPath, 2, 100);
      }
      fs.renameSync(partPath, finalPath);
      return finalPath;
    } catch (error) {
      this._log(job, `No se pudo renombrar ${partPath} a ${finalPath}; se conserva el archivo temporal.`, 'warn');
      return partPath;
    }
  }

  async _sha256(file) {
    return new Promise((resolve, reject) => {
      const hash = crypto.createHash('sha256');
      const stream = fs.createReadStream(file);
      stream.on('error', reject);
      stream.on('data', chunk => hash.update(chunk));
      stream.on('end', () => resolve(hash.digest('hex')));
    });
  }

  async _verifySignature(job, signaturePath, bundlePath) {
    if (!signaturePath) {
      if (job.require_signature) throw new Error('Firma requerida pero no publicada.');
      return { status: 'not-published', required: false, tool: '' };
    }
    try {
      await execFilePromise('gpg.exe', ['--batch', '--verify', signaturePath, bundlePath], {
        windowsHide: true,
        timeout: 30000
      });
      return { status: 'verified', required: !!job.require_signature, tool: 'gpg' };
    } catch (error) {
      if (job.require_signature) throw new Error(`Firma no verificable: ${error.message}`);
      return { status: 'unverified', required: false, tool: 'gpg', detail: error.message };
    }
  }

  async _prepareAtomicBackup(job) {
    const target = path.resolve(job.target);
    if (this._unsafeTarget(target)) throw new Error(`Destino inseguro: ${target}`);
    const backup = `${target}.bago-rollback-${safeName(job.id)}`;
    if (fs.existsSync(backup)) fs.rmSync(backup, { recursive: true, force: true });
    job.created_target = !fs.existsSync(target);
    if (fs.existsSync(target)) {
      fs.renameSync(target, backup);
      job.backup_path = backup;
      job.rollback_available = true;
      this._log(job, `Backup atómico creado: ${backup}.`);
    }
    this._emit(job);
  }

  async _runInstaller(job) {
    const script = path.join(job.source_root, 'install-v4.ps1');
    const args = [
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-File', script,
      '-SourceRoot', job.source_root,
      '-InstallDir', job.target,
      '-Mode', job.mode || 'Express',
      '-NoPathUpdate'
    ];
    await new Promise((resolve, reject) => {
      const child = spawn(this.powerShell, args, {
        cwd: job.source_root,
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe']
      });
      this.runtime.set(job.id, { ...(this.runtime.get(job.id) || {}), child });
      const consume = (stream, level) => {
        let pending = '';
        stream.on('data', chunk => {
          pending += String(chunk);
          const lines = pending.split(/\r?\n/);
          pending = lines.pop() || '';
          lines.filter(Boolean).forEach(line => this._log(job, line, level));
        });
        stream.on('end', () => { if (pending) this._log(job, pending, level); });
      };
      consume(child.stdout, 'info');
      consume(child.stderr, 'warn');
      child.once('error', reject);
      child.once('exit', code => code === 0 ? resolve() : reject(new Error(`Instalador terminó con código ${code}.`)));
    });
  }

  async _validateInstalled(job) {
    const launcher = path.join(job.target, 'bago_core', 'launcher.py');
    const installer = path.join(job.target, 'install-v4.ps1');
    if (!fs.existsSync(launcher) || !fs.existsSync(installer)) {
      throw new Error('La instalación final no contiene launcher e instalador requeridos.');
    }
    const installedVersion = readVersion(job.target);
    if (installedVersion && normalizeTag(installedVersion) !== normalizeTag(job.release.tag_name)) {
      throw new Error(`Versión instalada ${installedVersion} no coincide con ${job.release.tag_name}.`);
    }
    job.installed_version = installedVersion;
    this._emit(job);
  }

  async _restoreAtomicBackup(job, automatic) {
    const target = path.resolve(job.target);
    if (this._unsafeTarget(target)) throw new Error(`Rollback bloqueado sobre destino inseguro: ${target}`);
    if (fs.existsSync(target)) {
      if (automatic || job.created_target) {
        fs.rmSync(target, { recursive: true, force: true });
      } else {
        const replaced = `${target}.bago-replaced-${safeName(job.id)}`;
        if (fs.existsSync(replaced)) fs.rmSync(replaced, { recursive: true, force: true });
        fs.renameSync(target, replaced);
        job.replaced_path = replaced;
      }
    }
    if (job.backup_path && fs.existsSync(job.backup_path)) {
      fs.renameSync(job.backup_path, target);
      job.backup_path = '';
    }
    job.rollback_available = false;
    this._emit(job);
  }

  _killTree(pid) {
    if (!pid) return;
    if (process.platform === 'win32') {
      try { spawn('taskkill.exe', ['/PID', String(pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }); } catch {}
      return;
    }
    try { process.kill(pid, 'SIGTERM'); } catch {}
  }

  _fail(job, error) {
    if (job.state === 'cancelled') return;
    const message = error && error.message || String(error);
    if (message === 'cancelled' || job.cancel_requested) {
      this._update(job, { state: 'cancelled', error: 'Trabajo cancelado; se puede reanudar.' });
      return;
    }
    this._update(job, { state: 'failed', error: message });
    this._log(job, message, 'error');
  }
}

module.exports = {
  ReleaseJobManager,
  assetContract,
  parseExpectedSha256
};
