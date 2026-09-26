const { EventEmitter } = require('events');
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
  const bundles = assets.filter(asset => /\.zip$/i.test(asset.name || '') && !/\.sha256$/i.test(asset.name || ''));
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

function normalizeVersionTag(value) {
  return String(value || '').trim().replace(/^v/i, '');
}

function parseVersionTag(value) {
  const text = normalizeVersionTag(value);
  const match = text.match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+.*)?$/);
  if (!match) return null;
  return {
    major: Number(match[1]),
    minor: Number(match[2]),
    patch: Number(match[3]),
    prerelease: match[4] ? match[4].split('.') : []
  };
}

function compareVersionTags(left, right) {
  const a = parseVersionTag(left);
  const b = parseVersionTag(right);
  if (!a || !b) return 0;
  for (const key of ['major', 'minor', 'patch']) {
    if (a[key] !== b[key]) return a[key] - b[key];
  }
  if (!a.prerelease.length && !b.prerelease.length) return 0;
  if (!a.prerelease.length) return 1;
  if (!b.prerelease.length) return -1;
  const length = Math.max(a.prerelease.length, b.prerelease.length);
  for (let i = 0; i < length; i += 1) {
    if (i >= a.prerelease.length) return -1;
    if (i >= b.prerelease.length) return 1;
    const leftPart = a.prerelease[i];
    const rightPart = b.prerelease[i];
    const leftNum = /^\d+$/.test(leftPart);
    const rightNum = /^\d+$/.test(rightPart);
    if (leftNum && rightNum) {
      const diff = Number(leftPart) - Number(rightPart);
      if (diff) return diff;
      continue;
    }
    if (leftNum) return -1;
    if (rightNum) return 1;
    const diff = leftPart.localeCompare(rightPart);
    if (diff) return diff;
  }
  return 0;
}

function currentManagerVersion() {
  const root = path.join(__dirname, '..');
  const releaseVersion = normalizeVersionTag(readVersion(root));
  if (releaseVersion) return releaseVersion;
  try {
    return normalizeVersionTag(require(path.join(root, 'package.json')).version);
  } catch {
    return '';
  }
}

function isFutureReleaseTag(tagName, ceiling = currentManagerVersion()) {
  const tag = normalizeVersionTag(tagName);
  const current = normalizeVersionTag(ceiling);
  if (!tag || !current) return false;
  return compareVersionTags(tag, current) > 0;
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
    this.verifySignature = typeof options.verifySignature === 'function' ? options.verifySignature : null;
    this.stageBundle = typeof options.stageBundle === 'function' ? options.stageBundle : null;
    this.downloadAsset = typeof options.downloadAsset === 'function' ? options.downloadAsset : null;
    this.persistJob = typeof options.persistJob === 'function' ? options.persistJob : null;
    this.appendJobLog = typeof options.appendJobLog === 'function' ? options.appendJobLog : null;
    this.archiveJob = typeof options.archiveJob === 'function' ? options.archiveJob : null;
    this.prepareInstall = typeof options.prepareInstall === 'function' ? options.prepareInstall : null;
    this.rollbackInstall = typeof options.rollbackInstall === 'function' ? options.rollbackInstall : null;
    this.jobs = new Map();
    this.activeLifecycleJob = '';
    this.runtime = new Map();
    this.storageQueues = new Map();
    this.recoveredJobs = [];
    this._init();
  }

  _init() {
    let names = [];
    try { names = fs.readdirSync(this.jobsDir); } catch {}
    for (const name of names) {
      if (!name.endsWith('.json')) continue;
      try {
        const job = JSON.parse(fs.readFileSync(path.join(this.jobsDir, name), 'utf8'));
        const wasActive = ACTIVE_STATES.has(job.state);
        if (wasActive) {
          job.state = 'cancelled';
          job.error = 'Interrumpido al cerrar el gestor; se puede reanudar.';
          job.updated_at = nowIso();
        }
        this.jobs.set(job.id, job);
        if (wasActive) this.recoveredJobs.push(job);
      } catch {}
    }
  }

  async initialize() {
    for (const job of this.recoveredJobs) await this._persist(job);
    this.recoveredJobs = [];
  }

  _jobFile(id) {
    return path.join(this.jobsDir, `${safeName(id)}.json`);
  }

  _public(job) {
    return JSON.parse(JSON.stringify(job));
  }

  async _persist(job) {
    if (!this.persistJob) throw new Error('No hay dispatch al adapter gateway de estado de release-job.');
    return await this._serializeStorage(job.id, () => this._persistNow(job));
  }

  async _persistNow(job) {
    const state = this._public(job);
    await this.persistJob(state);
    return state;
  }

  _serializeStorage(jobId, operation) {
    const key = String(jobId || '');
    const previous = this.storageQueues.get(key) || Promise.resolve();
    const next = previous.catch(() => {}).then(operation);
    this.storageQueues.set(key, next);
    return next.finally(() => {
      if (this.storageQueues.get(key) === next) this.storageQueues.delete(key);
    });
  }

  async _emit(job) {
    const payload = this._public(job);
    return await this._serializeStorage(job.id, async () => {
      await this.persistJob(payload);
      this.emit('changed', payload);
      return payload;
    });
  }

  async _update(job, patch) {
    Object.assign(job, patch, { updated_at: nowIso() });
    return await this._emit(job);
  }

  async _log(job, message, level = 'info') {
    if (!this.appendJobLog) throw new Error('No hay dispatch al adapter gateway de log de release-job.');
    return await this._serializeStorage(job.id, async () => {
      await this.appendJobLog(job.id, { timestamp: nowIso(), level, message: String(message || '') });
      job.last_log = String(message || '');
      job.updated_at = nowIso();
      const payload = this._public(job);
      await this.persistJob(payload);
      this.emit('changed', payload);
      return payload;
    });
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
      if (release.tag_name && isFutureReleaseTag(release.tag_name)) {
        blockPrepare(`La release ${release.tag_name} es futura respecto a ${currentManagerVersion()} y este manager solo instala versiones anteriores o iguales.`);
      }
    }
    if (!target || this._unsafeTarget(target)) blockPrepare(`Destino inseguro: ${target || '(vacio)'}`);

    const targetExists = !!target && fs.existsSync(target);
    if (uninstall && !targetExists) blockers.push('La instalación indicada no existe.');
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
        owner_check: writable ? 'writable' : 'blocked'
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

  async startPrepare(payload = {}) {
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
    await this._emit(job);
    await this._log(job, `Job creado para ${release.tag_name || contract.bundle.name} -> ${job.target}`);
    this._runPrepare(job).catch(error => this._fail(job, error));
    return this._public(job);
  }

  async resume(id) {
    const job = this._get(id);
    if (!['cancelled', 'failed'].includes(job.state)) throw new Error(`El job ${id} no se puede reanudar desde ${job.state}.`);
    const preflight = this.preflight({
      release: job.release,
      target: job.target,
      action: job.action,
      require_signature: job.require_signature
    });
    job.preflight = preflight;
    if (!preflight.ok) {
      await this._update(job, { state: 'failed', error: preflight.blockers.join(' ') });
      await this._log(job, `Reanudación bloqueada por preflight: ${job.error}`, 'warn');
      throw new Error(job.error);
    }
    job.cancel_requested = false;
    job.error = '';
    await this._update(job, { state: 'queued', progress: { ...job.progress, phase: 'queued' } });
    await this._log(job, 'Job reanudado.');
    this._runPrepare(job).catch(error => this._fail(job, error));
    return this._public(job);
  }

  async cancel(id) {
    const job = this._get(id);
    if (TERMINAL_STATES.has(job.state)) return this._public(job);
    if (job.state === 'installing') {
      throw new Error('La instalación está ejecutándose bajo ExecutionGateway y no admite cancelación; espera su recibo o usa rollback.');
    }
    job.cancel_requested = true;
    const runtime = this.runtime.get(job.id) || {};
    await this._log(job, 'Cancelación solicitada.', 'warn');
    if (runtime.controller) runtime.controller.abort();
    return this._public(job);
  }

  async deleteJob(id) {
    const job = this._get(id);
    if (!TERMINAL_STATES.has(job.state)) {
      throw new Error(`El job ${id} no se puede eliminar mientras está en ${job.state}. Cancélalo primero.`);
    }
    if (!this.archiveJob) throw new Error('No hay dispatch al adapter gateway de archivado de release-job.');
    const archivedAt = nowIso();
    const receipt = await this._serializeStorage(job.id, () => this.archiveJob(job.id, archivedAt));
    this.jobs.delete(job.id);
    this.runtime.delete(job.id);
    const archiveDir = String(receipt && receipt.archive_dir || '');
    this.emit('changed', { id: job.id, deleted: true, archived_at: archivedAt, archive_dir: archiveDir, state: 'deleted' });
    return { ok: true, id: job.id, deleted: true, archived_at: archivedAt, archive_dir: archiveDir };
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
      await this._update(job, { state: 'ready', error: preflight.blockers.join(' ') });
      await this._log(job, `Instalación bloqueada por preflight: ${job.error}`, 'warn');
      throw new Error(job.error);
    }
    if (!this.prepareInstall) throw new Error('No hay dispatch autenticado a system.install.apply.');
    const executeInstall = await this.prepareInstall({
      action: 'release-job',
      tag: String(job.release && job.release.tag_name || ''),
      source_root: job.source_root,
      helper_path: path.join(job.source_root, 'install-v4.ps1'),
      install_dir: job.target,
      mode: job.mode || 'Express',
      package_sha256: String(job.verification && job.verification.actual_sha256 || '')
    });
    if (executeInstall === null) return this._public(job);
    if (typeof executeInstall !== 'function') throw new Error('El sistema de autorización no preparó la ejecución del helper.');
    this.activeLifecycleJob = job.id;
    job.cancel_requested = false;
    await this._update(job, { state: 'installing', progress: { phase: 'installing', transferred: 0, total: 1, percent: 0 } });
    await this._log(job, `Instalación iniciada sobre ${job.target}.`);
    try {
      const installReceipt = await this._runInstaller(job, executeInstall);
      job.backup_path = String(installReceipt.backup_path || '');
      job.created_target = !!installReceipt.created_target;
      await this._emit(job);
      await this._validateInstalled(job);
      await this._update(job, {
        state: 'completed',
        rollback_available: !!job.backup_path || job.created_target,
        progress: { phase: 'completed', transferred: 1, total: 1, percent: 100 },
        error: ''
      });
      await this._log(job, `Instalación validada: ${job.target}.`);
    } catch (error) {
      await this._log(job, `Instalación fallida: ${error.message}`, 'error');
      let recoveryError = '';
      if (job.backup_path || job.created_target) {
        try {
          const restored = await this._restoreAtomicBackup(job, true);
          if (!restored) job.rollback_available = true;
        } catch (restoreError) {
          recoveryError = restoreError && restoreError.message || String(restoreError);
          job.rollback_available = true;
        }
      }
      if (job.cancel_requested && !recoveryError) {
        await this._update(job, { state: 'cancelled', error: 'Instalación cancelada; ExecutionGateway resolvió la recuperación del destino.' });
      } else {
        await this._update(job, {
          state: 'failed',
          rollback_available: job.rollback_available,
          error: recoveryError ? `${error.message}; rollback requiere reintento: ${recoveryError}` : error.message
        });
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
    await this._update(job, { state: 'rolling-back', progress: { phase: 'rolling-back', transferred: 0, total: 1, percent: 0 } });
    try {
      const restored = await this._restoreAtomicBackup(job, false);
      if (!restored) {
        await this._update(job, { state: 'completed', rollback_available: true, progress: { phase: 'completed', transferred: 1, total: 1, percent: 100 } });
        return this._public(job);
      }
      await this._update(job, {
        state: 'rolled-back',
        rollback_available: false,
        progress: { phase: 'rolled-back', transferred: 1, total: 1, percent: 100 },
        error: ''
      });
      await this._log(job, `Rollback manual completado: ${job.target}.`, 'warn');
    } catch (error) {
      await this._update(job, {
        state: 'failed',
        rollback_available: true,
        error: `Rollback no confirmado; puede reintentarse: ${error && error.message || error}`
      });
      throw error;
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
    let bundlePath = '';
    let signaturePath = '';
    job.cancel_requested = false;

    await this._update(job, { state: 'downloading-checksum', progress: { phase: 'checksum', transferred: 0, total: Number(contract.checksum.size || 0), percent: 0 } });
    const checksumReceipt = await this._download(job, contract.checksum, 'checksum', false);
    const checksumPath = checksumReceipt.path;
    const expected = parseExpectedSha256(fs.readFileSync(checksumPath, 'utf8'), contract.bundle.name);
    if (!expected) throw new Error('El asset SHA256 no contiene un hash válido.');

    if (contract.signature) {
      await this._update(job, { state: 'downloading-signature', progress: { phase: 'signature', transferred: 0, total: Number(contract.signature.size || 0), percent: 0 } });
      const signatureReceipt = await this._download(job, contract.signature, 'signature', false);
      signaturePath = signatureReceipt.path;
    }

    await this._update(job, { state: 'downloading', progress: { phase: 'bundle', transferred: 0, total: Number(contract.bundle.size || 0), percent: 0 } });
    const bundleReceipt = await this._download(job, contract.bundle, 'bundle', true);
    bundlePath = bundleReceipt.path;
    job.bundle_path = bundlePath;
    if (job.cancel_requested) throw new Error('cancelled');

    await this._update(job, { state: 'verifying', progress: { phase: 'verifying', transferred: 0, total: 1, percent: 0 } });
    const actual = await this._sha256(bundlePath);
    const publishedDigest = String(contract.bundle.digest || '').replace(/^sha256:/i, '').toLowerCase();
    if (actual !== expected) throw new Error(`SHA256 no coincide: esperado ${expected}, obtenido ${actual}.`);
    if (publishedDigest && actual !== publishedDigest) throw new Error('El digest publicado por GitHub no coincide con el bundle.');
    const magic = Buffer.alloc(4);
    const handle = fs.openSync(bundlePath, 'r');
    fs.readSync(handle, magic, 0, 4, 0);
    fs.closeSync(handle);
    if (magic[0] !== 0x50 || magic[1] !== 0x4b) throw new Error('El asset no tiene cabecera ZIP válida.');
    const signature = await this._verifySignature(job, signaturePath, bundlePath);

    await this._update(job, { state: 'staging', progress: { phase: 'staging', transferred: 0, total: 1, percent: 0 } });
    const stagePath = path.join(this.stagingDir, safeName(job.id));
    if (!this.stageBundle) throw new Error('No hay dispatch autenticado al adapter de staging del backend.');
    const staged = await this.stageBundle(safeName(job.id), bundlePath);
    if (!staged || !isInside(staged.staging_path, this.stagingDir) || pathKey(staged.staging_path) !== pathKey(stagePath)) {
      throw new Error('El backend devolvió un destino de staging inesperado.');
    }
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
    await this._update(job, {
      state: 'ready',
      error: '',
      progress: { phase: 'ready', transferred: 1, total: 1, percent: 100 }
    });
    await this._log(job, `Bundle verificado y preparado: ${contract.bundle.name}.`);
  }

  async _download(job, asset, assetKind, resume) {
    if (!this.downloadAsset) throw new Error('No hay dispatch autenticado al owner de descargas release.download.');
    const controller = new AbortController();
    this.runtime.set(job.id, { ...(this.runtime.get(job.id) || {}), controller });
    try {
      const filename = safeName(asset.name);
      const result = await this.downloadAsset({
        job_id: safeName(job.id),
        filename,
        asset_kind: assetKind,
        url: this._validateUrl(asset.browser_download_url),
        digest: String(asset.digest || '').replace(/^sha256:/i, '').toLowerCase(),
        size: Number(asset.size || 0),
        resume: !!resume
      }, controller.signal);
      const expectedPath = path.join(this.cacheDir, safeName(job.id), filename);
      if (!result || result.effect_id !== 'release.download' ||
          pathKey(result.path) !== pathKey(expectedPath) ||
          !/^[a-f0-9]{64}$/.test(String(result.sha256 || '')) ||
          Number(result.bytes_written) !== Number(asset.size)) {
        throw new Error('El owner release.download devolvió un recibo de asset inválido.');
      }
      if (job.cancel_requested) throw new Error('cancelled');
      job.progress = {
        phase: job.progress.phase,
        transferred: Number(result.bytes_written),
        total: Number(asset.size),
        percent: 100
      };
      await this._emit(job);
      return { path: result.path, sha256: result.sha256, bytes_written: Number(result.bytes_written) };
    } catch (error) {
      if (job.cancel_requested || error.name === 'AbortError' || error.message === 'cancelled' || error.code === 'release_download_cancelled') {
        await this._update(job, { state: 'cancelled', error: 'Descarga cancelada; archivo parcial conservado para reanudar.' });
        await this._log(job, `Descarga cancelada: ${asset.name}.`, 'warn');
        throw new Error('cancelled');
      }
      throw error;
    } finally {
      const runtime = this.runtime.get(job.id) || {};
      delete runtime.controller;
      this.runtime.set(job.id, runtime);
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
      if (!this.verifySignature) throw new Error('No hay dispatch autenticado al adapter de firma del backend.');
      await this.verifySignature(signaturePath, bundlePath);
      return { status: 'verified', required: !!job.require_signature, tool: 'gpg' };
    } catch (error) {
      if (job.require_signature) throw new Error(`Firma no verificable: ${error.message}`);
      return { status: 'unverified', required: false, tool: 'gpg', detail: error.message };
    }
  }

  async _runInstaller(job, executeInstall) {
    const result = await executeInstall();
    if (!result || result.effect_id !== 'system.install.apply' || result.status !== 'completed') {
      throw new Error('ExecutionGateway no confirmó la finalización de la instalación.');
    }
    await this._log(job, `system.install.apply completó el helper para ${job.target}.`);
    return result;
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
    await this._emit(job);
  }

  async _restoreAtomicBackup(job, automatic) {
    const target = path.resolve(job.target);
    if (this._unsafeTarget(target)) throw new Error(`Rollback bloqueado sobre destino inseguro: ${target}`);
    const derivedBackup = `${target}.bago-rollback-${safeName(job.id)}`;
    const backup = job.backup_path || (fs.existsSync(derivedBackup) ? derivedBackup : '');
    const displaced = automatic || job.created_target
      ? `${target}.bago-failed-${safeName(job.id)}`
      : `${target}.bago-replaced-${safeName(job.id)}`;
    if (!this.rollbackInstall) throw new Error('No hay dispatch autenticado a system.install.rollback.');
    job.backup_path = backup;
    job.restore_automatic = !!automatic;
    job.replaced_path = displaced;
    job.restore_phase = 'gateway_rollback_requested';
    await this._emit(job);
    const result = await this.rollbackInstall({
      install_dir: target,
      backup_path: backup,
      displaced_path: displaced,
      tag: String(job.release && job.release.tag_name || ''),
      automatic: !!automatic
    });
    if (result === null) return false;
    if (!result || result.effect_id !== 'system.install.rollback' || result.status !== 'completed') {
      throw new Error('ExecutionGateway no confirmó el rollback del release job.');
    }
    job.restore_phase = 'restore_complete';
    job.backup_path = '';
    job.rollback_available = false;
    await this._emit(job);
    return true;
  }

  async _fail(job, error) {
    if (job.state === 'cancelled') return;
    const message = error && error.message || String(error);
    if (message === 'cancelled' || job.cancel_requested) {
      await this._update(job, { state: 'cancelled', error: 'Trabajo cancelado; se puede reanudar.' });
      return;
    }
    await this._update(job, { state: 'failed', error: message });
    await this._log(job, message, 'error');
  }
}

module.exports = {
  ReleaseJobManager,
  assetContract,
  parseExpectedSha256
};
