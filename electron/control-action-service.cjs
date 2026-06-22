const crypto = require('crypto');
const os = require('os');

const CONTRACT_TTL_MS = 5 * 60 * 1000;
const MAX_PAYLOAD_BYTES = 64 * 1024;
const MAX_AUDIT_LINES = 5000;

const RISK_CONFIRMATION = {
  read: '',
  low: '',
  medium: 'CONFIRMAR',
  high: 'APLICAR',
  destructive: 'CONFIRMAR DESTRUCCION'
};

function isPlainObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;
}

function clone(value) {
  return value == null ? value : JSON.parse(JSON.stringify(value));
}

function nowIso() {
  return new Date().toISOString();
}

function text(value, field, max = 4096) {
  const result = String(value == null ? '' : value).trim();
  if (result.length > max) throw new Error(`${field} supera ${max} caracteres`);
  return result;
}

function requiredText(value, field, max = 4096) {
  const result = text(value, field, max);
  if (!result) throw new Error(`${field} es obligatorio`);
  return result;
}

function enumValue(value, field, allowed) {
  const result = requiredText(value, field, 128);
  if (!allowed.includes(result)) throw new Error(`${field} no permitido: ${result}`);
  return result;
}

function ensurePayload(payload) {
  const value = payload == null ? {} : payload;
  if (!isPlainObject(value)) throw new Error('payload debe ser un objeto simple');
  const serialized = JSON.stringify(value);
  if (Buffer.byteLength(serialized, 'utf8') > MAX_PAYLOAD_BYTES) {
    throw new Error(`payload supera ${MAX_PAYLOAD_BYTES} bytes`);
  }
  return clone(value);
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (isPlainObject(value)) {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]));
  }
  return value;
}

function digest(value) {
  return crypto.createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');
}

function redact(value) {
  if (Array.isArray(value)) return value.map(redact);
  if (!isPlainObject(value)) return value;
  const out = {};
  for (const [key, item] of Object.entries(value)) {
    if (/token|secret|password|credential|api[_-]?key|value/i.test(key)) out[key] = '[REDACTED]';
    else out[key] = redact(item);
  }
  return out;
}

function withTimeout(promise, timeoutMs, label) {
  let timer = null;
  return Promise.race([
    Promise.resolve(promise),
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${label} excedió ${timeoutMs} ms`)), timeoutMs);
    })
  ]).finally(() => clearTimeout(timer));
}

function normalizeResult(result) {
  if (result && result.ok === false) throw new Error(result.error || result.message || 'Operación rechazada');
  return result;
}

function createControlActionService(ctx) {
  const {
    app,
    fs,
    path,
    getDependencyService,
    getRuntimeService,
    getInstallService,
    getReleaseService,
    resolveBagoRuntimeRoot
  } = ctx;

  const prepared = new Map();
  const locks = new Map();
  const auditRoot = path.join(app.getPath('userData'), 'control-actions');
  const auditFile = path.join(auditRoot, 'events.jsonl');
  const roleFile = path.join(os.homedir(), '.bago', 'install_selection.json');

  function appendAudit(event) {
    fs.mkdirSync(auditRoot, { recursive: true });
    fs.appendFileSync(auditFile, JSON.stringify({ timestamp: nowIso(), ...event }) + '\n', 'utf8');
    try {
      const lines = fs.readFileSync(auditFile, 'utf8').split(/\r?\n/).filter(Boolean);
      if (lines.length > MAX_AUDIT_LINES) {
        fs.writeFileSync(auditFile, lines.slice(-MAX_AUDIT_LINES).join('\n') + '\n', 'utf8');
      }
    } catch {}
  }

  function readRoleSelection() {
    try {
      const parsed = JSON.parse(fs.readFileSync(roleFile, 'utf8'));
      return isPlainObject(parsed) ? parsed : { version: 1, roles: {} };
    } catch {
      return { version: 1, roles: {} };
    }
  }

  function writeRoleSelection(role, installPath) {
    const selection = readRoleSelection();
    selection.version = 1;
    selection.roles = isPlainObject(selection.roles) ? selection.roles : {};
    selection.roles[role] = {
      path: installPath,
      label: { active: 'Copia activa / uso', dev: 'Copia de desarrollo', launch: 'Plataforma de lanzamiento' }[role],
      updated_at: nowIso()
    };
    selection.updated_at = nowIso();
    fs.mkdirSync(path.dirname(roleFile), { recursive: true });
    const temporary = `${roleFile}.${process.pid}.tmp`;
    fs.writeFileSync(temporary, JSON.stringify(selection, null, 2) + '\n', 'utf8');
    fs.renameSync(temporary, roleFile);
    return { ok: true, role, path: installPath, selection_file: roleFile };
  }

  function resolveExistingPath(raw, field) {
    const candidate = path.resolve(requiredText(raw, field, 32768));
    if (!fs.existsSync(candidate)) throw new Error(`${field} no existe: ${candidate}`);
    return candidate;
  }

  function releaseJobs() {
    return getReleaseService().requireReleaseJobs();
  }

  async function runNode(args) {
    const result = await getRuntimeService().runBagoNode(args);
    const raw = String(result && result.stdout || '').trim();
    if (raw.startsWith('{') || raw.startsWith('[')) {
      try { return JSON.parse(raw); } catch {}
    }
    return result;
  }

  function jobById(id) {
    const job = releaseJobs().listJobs().find(item => String(item.id) === String(id));
    if (!job) throw new Error(`Job no encontrado: ${id}`);
    return job;
  }

  const specs = {
    'install.role.assign': {
      title: 'Asignar rol a instalación',
      risk: 'medium',
      scope: 'installations',
      timeout_ms: 10000,
      normalize(payload) {
        return {
          role: enumValue(payload.role, 'role', ['active', 'dev', 'launch']),
          path: resolveExistingPath(payload.path, 'path')
        };
      },
      async preflight(payload) {
        const markers = ['release_version.txt', 'bago_core', '.bago'].filter(name => fs.existsSync(path.join(payload.path, name)));
        if (!markers.length) throw new Error('La ruta no parece contener una instalación BAGO');
        return { target: payload.path, role: payload.role, markers, selection_file: roleFile };
      },
      execute: payload => writeRoleSelection(payload.role, payload.path),
      lock: payload => `role:${payload.role}`
    },

    'install.repair': installSpec('repair', 'Reparar instalación', 'high'),
    'install.reinstall': installSpec('reinstall', 'Reinstalar instalación', 'high'),
    'install.new-copy': installSpec('new-copy', 'Crear nueva copia', 'high'),
    'install.source-update': installSpec('source-update', 'Actualizar desde fuente', 'high'),
    'install.uninstall': installSpec('uninstall', 'Desinstalar instalación', 'destructive'),

    'release.prepare': {
      title: 'Preparar release verificada',
      risk: 'high',
      scope: 'releases',
      timeout_ms: 60000,
      normalize(payload) {
        if (!isPlainObject(payload.release)) throw new Error('release es obligatoria');
        return {
          release: clone(payload.release),
          target: path.resolve(requiredText(payload.target, 'target', 32768)),
          action: enumValue(payload.action || 'install', 'action', ['install', 'separate']),
          mode: enumValue(payload.mode || 'Express', 'mode', ['Express', 'Advanced']),
          require_signature: !!payload.require_signature
        };
      },
      async preflight(payload) {
        const result = releaseJobs().preflight(payload);
        const blockers = [
          ...(Array.isArray(result.prepare_blockers) ? result.prepare_blockers : []),
          ...(Array.isArray(result.blockers) ? result.blockers : [])
        ].filter(Boolean);
        if (blockers.length) throw new Error(blockers.join(' · '));
        return result;
      },
      execute: payload => releaseJobs().startPrepare(payload),
      lock: payload => `release:${path.resolve(payload.target).toLowerCase()}`
    },

    'job.cancel': jobSpec('cancel', ['queued', 'downloading-checksum', 'downloading-signature', 'downloading', 'verifying', 'staging', 'installing', 'rolling-back'], 'medium'),
    'job.resume': jobSpec('resume', ['cancelled', 'failed'], 'medium'),
    'job.install': jobSpec('install', ['ready'], 'high'),
    'job.rollback': jobSpec('rollback', ['completed', 'failed'], 'destructive'),
    'job.delete': jobSpec('deleteJob', ['ready', 'completed', 'cancelled', 'failed', 'rolled-back'], 'destructive'),

    'node.validate': {
      title: 'Validar Node Control',
      risk: 'read',
      scope: 'nodes',
      timeout_ms: 60000,
      normalize: () => ({}),
      preflight: async () => ({ runtime_root: resolveBagoRuntimeRoot(), mutation: false }),
      execute: async () => runNode(['node', 'validate', '--json']),
      lock: () => 'node:read'
    },

    'node.mutate': {
      title: 'Modificar conector nodular',
      risk: 'high',
      scope: 'nodes',
      timeout_ms: 120000,
      normalize(payload) {
        return {
          installation: requiredText(payload.installation, 'installation', 4096),
          piece: requiredText(payload.piece, 'piece', 4096),
          mode: enumValue(payload.mode, 'mode', ['connected', 'shadow', 'readonly', 'locked', 'detached'])
        };
      },
      async preflight(payload) {
        const preview = await runNode([
          'node', 'preview',
          '--installation', payload.installation,
          '--piece', payload.piece,
          '--mode', payload.mode,
          '--json'
        ]);
        if (preview && preview.ok === false) throw new Error(preview.error || 'Preview nodular rechazado');
        return preview;
      },
      async execute(payload) {
        const args = payload.mode === 'detached'
          ? ['node', 'disconnect', '--installation', payload.installation, '--piece', payload.piece, '--json']
          : ['node', 'set-mode', '--installation', payload.installation, '--piece', payload.piece, '--mode', payload.mode, '--json'];
        return runNode(args);
      },
      lock: payload => `node:${payload.installation}:${payload.piece}`
    },

    'supervisor.status': supervisorSpec('status', 'read'),
    'supervisor.start': supervisorSpec('start', 'medium'),
    'supervisor.stop': supervisorSpec('stop', 'high'),

    'runtime.cleanup-zombies': {
      title: 'Limpiar procesos BAGO huérfanos',
      risk: 'high',
      scope: 'runtime',
      timeout_ms: 45000,
      normalize: () => ({}),
      preflight: async () => ({
        health: await getDependencyService().managerHealth(),
        policy: 'Solo procesos reconocidos por rutas y marcadores BAGO'
      }),
      execute: () => getRuntimeService().cleanupZombies(),
      lock: () => 'runtime:cleanup'
    },

    'dependency.action': {
      title: 'Configurar dependencia o proveedor',
      risk: 'high',
      scope: 'dependencies',
      timeout_ms: 180000,
      normalize(payload) {
        const action = enumValue(payload.action, 'action', ['install', 'install-all', 'login', 'set-credential']);
        const normalized = { action };
        if (action === 'install-all') normalized.targets = (Array.isArray(payload.targets) ? payload.targets : []).map(item => text(item, 'target', 128)).filter(Boolean);
        else normalized.target = requiredText(payload.target || payload.provider, 'target', 128).toLowerCase();
        if (action === 'set-credential') {
          normalized.provider = requiredText(payload.provider, 'provider', 128);
          normalized.key = requiredText(payload.key, 'key', 128);
          normalized.value = requiredText(payload.value, 'value', 16384);
        }
        return normalized;
      },
      async preflight(payload) {
        const catalog = getDependencyService().dependencyCatalog();
        if (payload.action === 'install') {
          const item = catalog.core.find(dep => dep.id === payload.target);
          if (!item || !item.installCommand) throw new Error(`Dependencia no instalable: ${payload.target}`);
          return { dependency: { id: item.id, label: item.label, required: item.required }, action: payload.action };
        }
        if (payload.action === 'install-all') {
          const allowed = new Set(catalog.core.filter(dep => dep.installCommand).map(dep => dep.id));
          const rejected = payload.targets.filter(item => !allowed.has(item));
          if (rejected.length) throw new Error(`Dependencias no permitidas: ${rejected.join(', ')}`);
          return { targets: payload.targets, action: payload.action };
        }
        if (payload.action === 'login') {
          const provider = catalog.providers[payload.target];
          if (!provider || !provider.loginCommand) throw new Error(`Login no disponible: ${payload.target}`);
          return { provider: payload.target, mode: 'manual-command', action: payload.action };
        }
        const provider = catalog.providers[payload.provider];
        if (!provider) throw new Error(`Proveedor no permitido: ${payload.provider}`);
        const allowedKeys = [provider.primaryKey, ...(provider.optionalKeys || [])].filter(Boolean);
        if (!allowedKeys.includes(payload.key)) throw new Error(`Credencial no permitida para ${payload.provider}: ${payload.key}`);
        return { provider: payload.provider, key: payload.key, action: payload.action, secret: true };
      },
      execute: payload => getDependencyService().runDependencyAction(payload),
      lock: payload => `dependency:${payload.action}:${payload.target || payload.provider || 'all'}`
    }
  };

  const declaredBlocked = {
    'repository.sync': 'Requiere un servicio Git dedicado con allowlist de remoto, rama protegida y política fast-forward.',
    'knowledge.index': 'Requiere un job de indexación con límites de ruta, tamaño, exclusiones y cancelación.',
    'chat.snapshot': 'Debe implementarse en el Session Manager con bundle firmado y exclusión de secretos.',
    'chat.export': 'Debe implementarse con selección explícita de destino y redacción de credenciales.',
    'connector.detach-all': 'Requiere preview agregado y rollback transaccional para múltiples conectores.'
  };

  function installSpec(action, title, risk) {
    return {
      title,
      risk,
      scope: 'installations',
      timeout_ms: 10 * 60 * 1000,
      normalize(payload) {
        const normalized = {
          action,
          targetDir: path.resolve(requiredText(payload.targetDir || payload.path, 'targetDir', 32768)),
          purgeState: !!payload.purgeState
        };
        if (action === 'source-update') {
          normalized.sourceRoot = resolveExistingPath(payload.sourceRoot, 'sourceRoot');
          normalized.branch = requiredText(payload.branch || 'main', 'branch', 256);
          if (!/^[A-Za-z0-9._/-]+$/.test(normalized.branch) || normalized.branch.includes('..')) throw new Error('branch no permitida');
        }
        return normalized;
      },
      async preflight(payload) {
        const dependency = await getDependencyService().runInstallPreflight(payload.targetDir);
        const targetExists = fs.existsSync(payload.targetDir);
        if (action === 'uninstall' && !targetExists) throw new Error('La instalación indicada no existe');
        return { action, target: payload.targetDir, target_exists: targetExists, dependency };
      },
      execute: payload => getInstallService().performInstallAction(payload),
      lock: payload => `install:${path.resolve(payload.targetDir).toLowerCase()}`
    };
  }

  function jobSpec(method, allowedStates, risk) {
    return {
      title: `Job ${method}`,
      risk,
      scope: 'jobs',
      timeout_ms: 10 * 60 * 1000,
      normalize(payload) {
        return { id: requiredText(payload.id, 'id', 256) };
      },
      async preflight(payload) {
        const job = jobById(payload.id);
        const state = String(job.state || job.status || '');
        if (!allowedStates.includes(state)) throw new Error(`Estado ${state} incompatible con ${method}`);
        if (method === 'rollback' && !job.rollback_available) throw new Error('El job no ofrece rollback');
        return { job: clone(job), action: method, allowed_states: allowedStates };
      },
      execute(payload) {
        const manager = releaseJobs();
        if (typeof manager[method] !== 'function') throw new Error(`Método de job no disponible: ${method}`);
        return manager[method](payload.id);
      },
      lock: payload => `job:${payload.id}`
    };
  }

  function supervisorSpec(command, risk) {
    return {
      title: `Supervisor ${command}`,
      risk,
      scope: 'runtime',
      timeout_ms: 30000,
      normalize: () => ({ command }),
      async preflight() {
        let current = null;
        try { current = await getRuntimeService().runSupervisorCmd(['status', '--json']); } catch (error) { current = { ok: false, error: error.message }; }
        return { command, current };
      },
      execute: () => getRuntimeService().runSupervisorCmd([command, '--json']),
      lock: () => 'runtime:supervisor'
    };
  }

  function publicCatalog() {
    const available = Object.entries(specs).map(([id, spec]) => ({
      id,
      title: spec.title,
      risk: spec.risk,
      scope: spec.scope,
      available: true,
      requires_confirmation: !!RISK_CONFIRMATION[spec.risk]
    }));
    const blocked = Object.entries(declaredBlocked).map(([id, reason]) => ({
      id,
      title: id,
      risk: 'blocked',
      scope: id.split('.')[0],
      available: false,
      reason
    }));
    return { version: 1, actions: [...available, ...blocked] };
  }

  function cleanupPrepared() {
    const now = Date.now();
    for (const [token, item] of prepared.entries()) {
      if (item.expires_at_ms <= now || item.consumed) prepared.delete(token);
    }
  }

  async function prepareAction(request) {
    cleanupPrepared();
    const input = ensurePayload(request);
    const action = requiredText(input.action, 'action', 256);
    if (declaredBlocked[action]) {
      appendAudit({ phase: 'blocked', action, reason: declaredBlocked[action] });
      throw new Error(`Acción bloqueada hasta disponer de contrato ejecutable: ${declaredBlocked[action]}`);
    }
    const spec = specs[action];
    if (!spec) throw new Error(`Acción no registrada: ${action}`);
    const payload = spec.normalize(ensurePayload(input.payload));
    const preview = await withTimeout(spec.preflight(payload), Math.min(spec.timeout_ms, 120000), `${action}:preflight`);
    const token = crypto.randomBytes(32).toString('base64url');
    const createdAt = Date.now();
    const item = {
      token,
      action,
      payload,
      payload_hash: digest(payload),
      preview: clone(preview),
      preview_hash: digest(preview),
      risk: spec.risk,
      scope: spec.scope,
      lock_key: spec.lock(payload),
      confirmation_phrase: RISK_CONFIRMATION[spec.risk] || '',
      created_at_ms: createdAt,
      expires_at_ms: createdAt + CONTRACT_TTL_MS,
      consumed: false
    };
    prepared.set(token, item);
    appendAudit({
      phase: 'prepared',
      action,
      token_hash: digest(token),
      payload_hash: item.payload_hash,
      preview_hash: item.preview_hash,
      risk: item.risk,
      scope: item.scope,
      payload: redact(payload)
    });
    return {
      ok: true,
      token,
      action,
      title: spec.title,
      risk: spec.risk,
      scope: spec.scope,
      payload_hash: item.payload_hash,
      preview_hash: item.preview_hash,
      preview: clone(preview),
      expires_at: new Date(item.expires_at_ms).toISOString(),
      requires_confirmation: !!item.confirmation_phrase,
      confirmation_phrase: item.confirmation_phrase
    };
  }

  async function executeAction(request) {
    cleanupPrepared();
    const input = ensurePayload(request);
    const token = requiredText(input.token, 'token', 1024);
    const item = prepared.get(token);
    if (!item) throw new Error('Contrato inexistente, consumido o caducado');
    if (item.expires_at_ms <= Date.now()) {
      prepared.delete(token);
      throw new Error('Contrato caducado');
    }
    if (item.consumed) throw new Error('Contrato ya consumido');
    if (item.confirmation_phrase) {
      const supplied = text(input.confirmation, 'confirmation', 128);
      if (supplied !== item.confirmation_phrase) throw new Error('Confirmación inválida');
    }
    if (locks.has(item.lock_key)) throw new Error(`Operación bloqueada por otra acción activa: ${item.lock_key}`);
    const spec = specs[item.action];
    if (!spec) throw new Error('El contrato perdió su definición de backend');

    item.consumed = true;
    locks.set(item.lock_key, { action: item.action, started_at: nowIso() });
    appendAudit({
      phase: 'started',
      action: item.action,
      token_hash: digest(token),
      payload_hash: item.payload_hash,
      preview_hash: item.preview_hash,
      lock_key: item.lock_key,
      risk: item.risk
    });

    try {
      const result = normalizeResult(await withTimeout(spec.execute(clone(item.payload)), spec.timeout_ms, item.action));
      appendAudit({
        phase: 'completed',
        action: item.action,
        token_hash: digest(token),
        result_hash: digest(result),
        lock_key: item.lock_key,
        result: redact(result)
      });
      prepared.delete(token);
      return { ok: true, action: item.action, result };
    } catch (error) {
      appendAudit({
        phase: 'failed',
        action: item.action,
        token_hash: digest(token),
        lock_key: item.lock_key,
        error: String(error && error.message || error)
      });
      prepared.delete(token);
      throw error;
    } finally {
      locks.delete(item.lock_key);
    }
  }

  function listEvidence(limit = 100) {
    const safeLimit = Math.max(1, Math.min(Number(limit || 100), 1000));
    try {
      return fs.readFileSync(auditFile, 'utf8')
        .split(/\r?\n/)
        .filter(Boolean)
        .slice(-safeLimit)
        .map(line => {
          try { return JSON.parse(line); } catch { return { invalid: true, raw: line }; }
        });
    } catch {
      return [];
    }
  }

  function getState() {
    return {
      prepared: [...prepared.values()].map(item => ({
        action: item.action,
        scope: item.scope,
        risk: item.risk,
        expires_at: new Date(item.expires_at_ms).toISOString(),
        consumed: item.consumed
      })),
      locks: Object.fromEntries(locks.entries()),
      evidence_file: auditFile
    };
  }

  return {
    catalog: publicCatalog,
    prepare: prepareAction,
    execute: executeAction,
    evidence: listEvidence,
    getState
  };
}

module.exports = { createControlActionService };
