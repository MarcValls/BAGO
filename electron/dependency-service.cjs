const { BrowserWindow } = require('electron');

function createDependencyService(ctx) {
  const {
    app,
    dialog,
    execFile,
    spawn,
    fs,
    path,
    ROOT_DIR,
    resolveBagoRuntimeRoot,
    getManagerState,
    runVisiblePowerShell
  } = ctx;

  const CORE_DEPENDENCIES = [
    {
      id: 'python',
      label: 'Python',
      required: true,
      wingetId: 'Python.Python.3.11',
      installCommand: 'winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements'
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

  function buildInstallCommand(packagedRoot, installDir, extraArgs = []) {
    const installScript = path.join(packagedRoot, 'install-v4.ps1');
    if (!fs.existsSync(installScript)) {
      throw new Error(`No se encontró install-v4.ps1 en el paquete. Buscado en: ${installScript}`);
    }
    return [
      'powershell.exe',
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-File', installScript,
      '-SourceRoot', packagedRoot,
      '-InstallDir', installDir,
      '-Profile', 'stable',
      '-Mode', 'Express',
      ...extraArgs
    ];
  }

  function buildUninstallCommand(installDir, extraArgs = []) {
    const installScript = path.join(installDir, 'bago-uninstall.ps1');
    if (!fs.existsSync(installScript)) {
      throw new Error(`No se encontró bago-uninstall.ps1 en el destino. Buscado en: ${installScript}`);
    }
    return [
      'powershell.exe',
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-File', installScript,
      '-InstallDir', installDir,
      ...extraArgs
    ];
  }

  function runPythonInline(script, args = [], cwd = ROOT_DIR, timeout = 20000) {
    return new Promise((resolve, reject) => {
      execFile(
        'python',
        ['-c', script, ...args.map(value => String(value || ''))],
        { cwd, windowsHide: true, timeout, maxBuffer: 16 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (error) {
            reject(new Error(String(stderr || stdout || error.message || 'python failed').trim()));
            return;
          }
          resolve({ stdout: String(stdout || '').trim(), stderr: String(stderr || '').trim() });
        }
      );
    });
  }

  async function saveProviderCredential(payload) {
    const provider = String(payload && payload.provider || '').trim();
    const key = String(payload && payload.key || '').trim();
    const value = String(payload && payload.value || '').trim();
    const runtimeRoot = resolveBagoRuntimeRoot();
    if (!provider) throw new Error('Falta provider');
    if (!key) throw new Error('Falta key');
    if (!value) throw new Error('Falta value');
    const script = [
      'import pathlib, sys',
      'root = pathlib.Path(sys.argv[1])',
      'sys.path.insert(0, str(root / ".bago" / "core"))',
      'from credential_manager import CredentialManager',
      'cm = CredentialManager(base_path=str(root))',
      'cm.set(sys.argv[2], sys.argv[3], sys.argv[4])',
      'print("ok")'
    ].join('; ');
    return runPythonInline(script, [runtimeRoot, provider, key, value], runtimeRoot);
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

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  }

  function showProgressWindow(title) {
    const win = new BrowserWindow({
      width: 480,
      height: 220,
      title: title || 'Procesando…',
      icon: path.join(ROOT_DIR, 'bago.ico'),
      backgroundColor: '#020617',
      resizable: false,
      minimizable: false,
      maximizable: false,
      alwaysOnTop: true,
      webPreferences: { nodeIntegration: false, contextIsolation: true }
    });
    win.removeMenu();
    win.loadURL('data:text/html;base64,' + Buffer.from(`
      <!DOCTYPE html>
      <html style="background:#020617;color:#e2e8f0;font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;">
        <div>
          <div style="font-size:48px;margin-bottom:12px;">⏳</div>
          <h2 style="margin:0 0 8px;font-size:18px;">${escapeHtml(title || 'Procesando…')}</h2>
          <p style="margin:0;color:#94a3b8;font-size:14px;">Esto puede tardar unos minutos.<br>No cierres esta ventana.</p>
        </div>
      </html>
    `).toString('base64'));
    return win;
  }

  async function runInstallScript(packagedRoot, installDir, extraArgs = [], progressTitle = 'Instalando BAGO…') {
    const command = buildInstallCommand(packagedRoot, installDir, extraArgs);
    const progressWin = showProgressWindow(progressTitle);

    return new Promise((resolve, reject) => {
      const child = spawn(command[0], command.slice(1), {
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';
      child.stdout.on('data', d => { stdout += d; });
      child.stderr.on('data', d => { stderr += d; });

      child.on('exit', async (code) => {
        if (progressWin && !progressWin.isDestroyed()) progressWin.close();
        if (code === 0) {
          resolve({ stdout, stderr });
        } else {
          await dialog.showErrorBox(
            'Instalación fallida',
            `El instalador retornó código ${code}.\n\nStdout:\n${stdout}\n\nStderr:\n${stderr}`
          );
          reject(new Error(`install-v4.ps1 exited with ${code}`));
        }
      });

      child.on('error', async (err) => {
        if (progressWin && !progressWin.isDestroyed()) progressWin.close();
        await dialog.showErrorBox('Error al lanzar instalador', err.message);
        reject(err);
      });
    });
  }

  async function runUninstallScript(installDir, extraArgs = [], progressTitle = 'Desinstalando BAGO…') {
    const command = buildUninstallCommand(installDir, extraArgs);
    const progressWin = showProgressWindow(progressTitle);

    return new Promise((resolve, reject) => {
      const child = spawn(command[0], command.slice(1), {
        windowsHide: true,
        stdio: ['ignore', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';
      child.stdout.on('data', d => { stdout += d; });
      child.stderr.on('data', d => { stderr += d; });

      child.on('exit', async (code) => {
        if (progressWin && !progressWin.isDestroyed()) progressWin.close();
        if (code === 0) {
          resolve({ stdout, stderr });
        } else {
          await dialog.showErrorBox(
            'Desinstalación fallida',
            `El desinstalador retornó código ${code}.\n\nStdout:\n${stdout}\n\nStderr:\n${stderr}`
          );
          reject(new Error(`bago-uninstall.ps1 exited with ${code}`));
        }
      });

      child.on('error', async (err) => {
        if (progressWin && !progressWin.isDestroyed()) progressWin.close();
        await dialog.showErrorBox('Error al lanzar desinstalador', err.message);
        reject(err);
      });
    });
  }

  async function runInstallPreflight(targetDir) {
    const dir = targetDir || path.join(app.getPath('home'), '.bago', 'active');
    const checks = await Promise.all([
      checkTool('Python', 'python', ['--version']),
      checkTool('PowerShell', 'powershell.exe', ['-NoProfile', '-Command', '$PSVersionTable.PSVersion.ToString()']),
      checkTool('Git', 'git', ['--version']),
      checkTool('Ollama', 'ollama', ['--version'])
    ]);
    let writeOk = false;
    let writeDetail = '';
    try {
      const probe = path.join(dir, '.bago-preflight-' + Date.now());
      fs.writeFileSync(probe, 'ok');
      fs.unlinkSync(probe);
      writeOk = true;
      writeDetail = 'writable';
    } catch (err) {
      writeDetail = err.message || 'not writable';
    }
    let diskOk = false;
    let diskDetail = '';
    try {
      const root = path.parse(dir).root;
      if (process.platform === 'win32') {
        const out = require('child_process').spawnSync('powershell.exe',
          ['-NoProfile', '-Command', `(Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null -and ('${root}'.TrimEnd('\\') -like ($_.Root + '*')) } | Select-Object -First 1).Free`],
          { encoding: 'utf8', windowsHide: true, timeout: 6000 });
        const bytes = parseInt(String(out.stdout || '').replace(/[^0-9]/g, ''), 10);
        diskOk = bytes > 500 * 1024 * 1024;
        diskDetail = bytes ? (bytes / (1024 * 1024)).toFixed(0) + ' MB libres' : 'no se pudo leer';
      } else {
        const stat = require('child_process').spawnSync('df', ['-k', dir], { encoding: 'utf8', timeout: 6000 });
        const m = String(stat.stdout || '').split(/\s+/);
        const kb = parseInt(m[3] || '0', 10);
        diskOk = kb > 500 * 1024;
        diskDetail = kb ? (kb / 1024).toFixed(0) + ' MB libres' : 'no se pudo leer';
      }
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
    buildInstallCommand,
    buildUninstallCommand,
    runInstallScript,
    runUninstallScript,
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
