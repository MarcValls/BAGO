function createDependencyService(ctx) {
  const {
    app,
    execFile,
    fs,
    path,
    ROOT_DIR,
    resolveBagoRuntimeRoot,
    prepareProviderCredential,
    getManagerState,
    runVisiblePowerShell
  } = ctx;

  const CORE_DEPENDENCIES = [
    {
      id: 'python',
      label: 'Python',
      required: true,
      wingetId: 'Python.Python.3.14',
      installCommand: 'winget install -e --id Python.Python.3.14 --accept-package-agreements --accept-source-agreements'
    },
    {
      id: 'powershell',
      label: 'PowerShell',
      required: true,
      wingetId: '',
      installCommand: ''
    },
    {
      id: 'git',
      label: 'Git',
      required: false,
      wingetId: 'Git.Git',
      installCommand: 'winget install -e --id Git.Git --accept-package-agreements --accept-source-agreements'
    },
    {
      id: 'ollama',
      label: 'Ollama',
      required: false,
      wingetId: 'Ollama.Ollama',
      installCommand: 'winget install -e --id Ollama.Ollama --accept-package-agreements --accept-source-agreements'
    }
  ];

  const PROVIDER_ONBOARDING = {
    'ollama-local': {
      label: 'Ollama local',
      authModes: ['install'],
      installTarget: 'ollama',
      primaryKey: 'OLLAMA_HOST',
      optionalKeys: []
    },
    'ollama-cloud': {
      label: 'Ollama Cloud',
      authModes: ['api'],
      primaryKey: 'OLLAMA_CLOUD_KEY',
      optionalKeys: ['OLLAMA_CLOUD_URL']
    },
    copilot: {
      label: 'GitHub Copilot',
      authModes: ['api', 'login'],
      primaryKey: 'GITHUB_TOKEN',
      optionalKeys: [],
      loginCommand: 'copilot login'
    },
    anthropic: {
      label: 'Anthropic',
      authModes: ['api'],
      primaryKey: 'ANTHROPIC_API_KEY',
      optionalKeys: []
    },
    codex: {
      label: 'Codex / OpenAI',
      authModes: ['api', 'login'],
      primaryKey: 'OPENAI_API_KEY',
      optionalKeys: ['OPENAI_ORG_ID'],
      loginCommand: 'codex login'
    },
    openrouter: {
      label: 'OpenRouter',
      authModes: ['api'],
      primaryKey: 'OPENROUTER_API_KEY',
      optionalKeys: ['OPENROUTER_HTTP_REFERER']
    },
    opencode: {
      label: 'OpenCode',
      authModes: ['api'],
      primaryKey: 'OPENCODE_API_KEY',
      optionalKeys: ['OPENCODE_BASE_URL']
    }
  };

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
    const releaseVersion = normalizeVersionTag(readManagerVersion());
    if (releaseVersion) return releaseVersion;
    try {
      return normalizeVersionTag(require(path.join(ROOT_DIR, 'package.json')).version);
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

  function readManagerVersion() {
    try {
      const pkg = require(path.join(ROOT_DIR, 'package.json'));
      if (pkg && pkg.version) return String(pkg.version);
    } catch {}
    try {
      const v = path.join(ROOT_DIR, 'release_version.txt');
      if (fs.existsSync(v)) return fs.readFileSync(v, 'utf8').trim();
    } catch {}
    return 'unknown';
  }

  function readRuntimeVersion(runtimeRoot) {
    if (!runtimeRoot) return '';
    try {
      const v = path.join(runtimeRoot, 'release_version.txt');
      if (fs.existsSync(v)) return fs.readFileSync(v, 'utf8').trim();
    } catch {}
    try {
      const v = path.join(runtimeRoot, 'install_manifest.json');
      if (fs.existsSync(v)) {
        const m = JSON.parse(fs.readFileSync(v, 'utf8'));
        if (m && m.runtime_version) return String(m.runtime_version);
      }
    } catch {}
    return '';
  }

  function dependencyCatalog() {
    return {
      core: CORE_DEPENDENCIES.map(item => ({ ...item })),
      providers: Object.fromEntries(
        Object.entries(PROVIDER_ONBOARDING).map(([name, spec]) => [name, { ...spec }])
      )
    };
  }

  function buildStartupHealth(checks) {
    const byName = new Map((checks || []).map(check => [String(check.name || '').toLowerCase(), check]));
    const missingCore = CORE_DEPENDENCIES
      .filter(dep => byName.get(dep.id)?.ok === false)
      .map(dep => ({
        id: dep.id,
        label: dep.label,
        required: !!dep.required,
        detail: byName.get(dep.id)?.detail || '',
        install_command: dep.installCommand || '',
        winget_id: dep.wingetId || ''
      }));
    return {
      ready: missingCore.length === 0,
      missing_core: missingCore,
      required_missing: missingCore.filter(item => item.required),
      recommended_missing: missingCore.filter(item => !item.required),
      prompt: missingCore.length
        ? (missingCore.some(item => item.required)
            ? 'Faltan dependencias obligatorias para el arranque'
            : 'Faltan dependencias recomendadas')
        : 'Arranque listo'
    };
  }

  function checkTool(name, command, args = ['--version']) {
    return new Promise(resolve => {
      execFile(command, args, { windowsHide: true, timeout: 6000 }, (error, stdout, stderr) => {
        const text = String(stdout || stderr || '').trim().split(/\r?\n/)[0] || '';
        resolve({ name, ok: !error, detail: error ? error.message : text });
      });
    });
  }

  async function saveProviderCredential(payload) {
    const provider = String(payload && payload.provider || '').trim();
    const key = String(payload && payload.key || '').trim();
    const value = String(payload && payload.value || '').trim();
    if (!provider) throw new Error('Falta provider');
    if (!key) throw new Error('Falta key');
    if (!value) throw new Error('Falta value');
    if (key !== 'api_key') throw new Error('Solo se admite escribir el campo api_key.');
    if (typeof prepareProviderCredential !== 'function') throw new Error('credential.write no está conectado al Manager.');
    return prepareProviderCredential({ provider, value });
  }

  function buildDependencyCommand(payload) {
    const action = String(payload && payload.action || '').trim();
    const target = String(payload && payload.target || '').trim().toLowerCase();
    const catalog = dependencyCatalog();
    if (action === 'install') {
      const dep = catalog.core.find(item => item.id === target);
      if (!dep || !dep.installCommand) {
        throw new Error(`No hay comando de instalación definido para ${target || 'dependency'}`);
      }
      return dep.installCommand;
    }
    if (action === 'install-all') {
      const targets = Array.isArray(payload && payload.targets) ? payload.targets : [];
      const commands = targets
        .map(name => catalog.core.find(item => item.id === String(name || '').trim().toLowerCase()))
        .filter(item => item && item.installCommand)
        .map(item => item.installCommand);
      if (!commands.length) throw new Error('No hay dependencias instalables en la lista');
      return commands.join('; ');
    }
    if (action === 'login') {
      const provider = catalog.providers[target];
      if (!provider || !provider.loginCommand) {
        throw new Error(`No hay login definido para ${target || 'provider'}`);
      }
      return provider.loginCommand;
    }
    return '';
  }

  async function runDependencyAction(payload) {
    const action = String(payload && payload.action || '').trim();
    if (action === 'set-credential') {
      return saveProviderCredential(payload);
    }
    const command = buildDependencyCommand(payload);
    if (!command) throw new Error('Acción de dependencia no soportada');
    if (action === 'login') {
      return {
        ok: true,
        mode: 'manual-command',
        command,
        message: 'Comando de login preparado para ejecucion manual'
      };
    }
    return runVisiblePowerShell(command, {
      visible: false,
      noExit: false,
      cwd: ROOT_DIR
    });
  }

  async function runInstallPreflight(targetDir) {
    const dir = targetDir || path.join(app.getPath('home'), '.gabo', 'active');
    const checks = await Promise.all([
      checkTool('Python', 'python', ['--version']),
      checkTool('PowerShell', 'powershell.exe', ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()']),
      checkTool('Git', 'git', ['--version']),
      checkTool('Ollama', 'ollama', ['--version'])
    ]);
    let writeOk = false;
    let writeDetail = '';
    try {
      fs.accessSync(dir, fs.constants.W_OK);
      writeOk = true;
      writeDetail = 'permisos de escritura disponibles';
    } catch (err) {
      writeDetail = err.message || 'not writable';
    }
    let diskOk = false;
    let diskDetail = '';
    try {
      const stat = fs.statfsSync(dir);
      const bytes = Number(stat.bavail) * Number(stat.bsize);
      diskOk = bytes > 500 * 1024 * 1024;
      diskDetail = Number.isFinite(bytes) && bytes > 0 ? (bytes / (1024 * 1024)).toFixed(0) + ' MB libres' : 'no se pudo leer';
    } catch (err) {
      diskDetail = err.message || 'no se pudo comprobar';
    }
    let networkOk = false;
    let networkDetail = '';
    try {
      const res = await new Promise(resolve => {
        const req = require('http').get('http://api.github.com', { timeout: 5000 }, r => {
          resolve({ ok: !!r.statusCode, code: r.statusCode });
          r.resume();
        });
        req.on('error', e => resolve({ ok: false, detail: e.message }));
        req.on('timeout', () => { req.destroy(); resolve({ ok: false, detail: 'timeout' }); });
      });
      networkOk = !!res.ok;
      networkDetail = res.ok ? ('HTTP ' + res.code) : (res.detail || 'sin conexion');
    } catch (err) {
      networkDetail = err.message;
    }
    return {
      target_dir: dir,
      checked_at: new Date().toISOString(),
      write: { ok: writeOk, detail: writeDetail },
      disk: { ok: diskOk, detail: diskDetail, minimum_mb: 500 },
      network: { ok: networkOk, detail: networkDetail },
      python: checks[0],
      powershell: checks[1],
      git: checks[2],
      ollama: checks[3]
    };
  }

  async function managerHealth() {
    let runtimeError = '';
    let runtimeRoot = '';
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
    const managerState = typeof getManagerState === 'function' ? getManagerState() : {};
    return {
      checked_at: new Date().toISOString(),
      runtime_root: runtimeRoot,
      manager_version: readManagerVersion(),
      runtime_version: readRuntimeVersion(runtimeRoot),
      mutation: managerState.mutation || null,
      lifecycle_job: managerState.lifecycle_job || '',
      release_jobs: Number(managerState.release_jobs || 0),
      startup: buildStartupHealth(checks),
      dependency_catalog: dependencyCatalog(),
      checks
    };
  }

  return {
    CORE_DEPENDENCIES,
    PROVIDER_ONBOARDING,
    dependencyCatalog,
    buildStartupHealth,
    runInstallPreflight,
    runDependencyAction,
    managerHealth,
    checkTool,
    readManagerVersion,
    readRuntimeVersion,
    currentManagerVersion,
    isFutureReleaseTag
  };
}

module.exports = { createDependencyService };
