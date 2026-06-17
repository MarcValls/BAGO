function createRuntimeService(ctx) {
  const {
    app,
    shell,
    execFile,
    spawn,
    fs,
    path,
    os,
    BrowserWindow,
    ROOT_DIR,
    ICON_PATH,
    CHAT_HOST,
    CHAT_START_PORT,
    resolveBagoRuntimeRoot,
    resolveUiDist,
    resolveBundledRuntimeRoot,
    resolveInstalledRuntimeRoot,
    runVisiblePowerShell
  } = ctx;

  const MUTATING_NODE_COMMANDS = new Set(['connect', 'disconnect', 'set-mode']);
  const MANAGER_HTML = path.join(ROOT_DIR, 'manager', 'index.html');

  let activeNodeMutation = null;
  let webChatProcess = null;
  let webChatWindow = null;
  let webChatState = null;

  function isExternalUrl(url) {
    return /^https?:\/\//i.test(url);
  }

  function psSingleArg(value) {
    return `'${String(value || '').replace(/'/g, "''")}'`;
  }

  function webChatStatus() {
    const procAlive = !!(webChatProcess && webChatProcess.exitCode === null && !webChatProcess.killed);
    const windowAlive = !!(webChatWindow && !webChatWindow.isDestroyed());
    return {
      running: !!(webChatState && (procAlive || windowAlive)),
      process_alive: procAlive,
      window_alive: windowAlive,
      ...(webChatState || {})
    };
  }

  async function probeWebChat(port) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 1200);
    try {
      const response = await fetch(`http://${CHAT_HOST}:${port}/session`, { signal: controller.signal });
      if (!response.ok) return false;
      const data = await response.json();
      return !!(data && data.session_id && data.provider);
    } catch {
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  async function waitForWebChat(port, timeoutMs = 12000) {
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      if (await probeWebChat(port)) return true;
      await new Promise(resolve => setTimeout(resolve, 350));
    }
    return false;
  }

  async function ensureWebChatServer(options = {}) {
    const requestedBasePath = String(options.basePath || '').trim();
    const runtimeRoot = resolveBagoRuntimeRoot();
    const basePath = requestedBasePath || runtimeRoot;
    const uiDist = resolveUiDist(runtimeRoot);
    const mayReuseExternal = !requestedBasePath || requestedBasePath === runtimeRoot;
    if (!uiDist) {
      throw new Error(`ui-react/dist no encontrado para ${runtimeRoot}`);
    }

    if (webChatState && webChatState.base_path === basePath && await probeWebChat(webChatState.port)) {
      return webChatState;
    }

    for (let port = CHAT_START_PORT; port < CHAT_START_PORT + 12; port += 1) {
      if (await probeWebChat(port)) {
        if (!mayReuseExternal) continue;
        webChatState = {
          host: CHAT_HOST,
          port,
          url: `http://${CHAT_HOST}:${port}/`,
          runtime_root: runtimeRoot,
          base_path: basePath,
          ui_dist: uiDist,
          reused: true
        };
        return webChatState;
      }

      const child = spawn(
        'python',
        [
          '-m', 'bago_core.launcher',
          '--base-path', basePath,
          'serve',
          '--host', CHAT_HOST,
          '--port', String(port),
          '--ui-dist', uiDist
        ],
        {
          cwd: runtimeRoot,
          stdio: 'ignore',
          windowsHide: true
        }
      );
      webChatProcess = child;
      child.once('exit', () => {
        if (webChatProcess === child) webChatProcess = null;
      });
      child.unref();

      if (await waitForWebChat(port)) {
        webChatState = {
          host: CHAT_HOST,
          port,
          url: `http://${CHAT_HOST}:${port}/`,
          pid: child.pid,
          runtime_root: runtimeRoot,
          base_path: basePath,
          ui_dist: uiDist,
          reused: false
        };
        return webChatState;
      }

      try { child.kill(); } catch {}
    }

    throw new Error('No se pudo arrancar BAGO web chat en un puerto local libre');
  }

  async function openWebChat(options = {}) {
    const state = await ensureWebChatServer(options || {});
    if (webChatWindow && !webChatWindow.isDestroyed()) {
      webChatWindow.focus();
      return { ...state, focused: true };
    }

    webChatWindow = new BrowserWindow({
      width: 1320,
      height: 900,
      minWidth: 980,
      minHeight: 680,
      title: 'BAGO Web Chat',
      icon: ICON_PATH,
      backgroundColor: '#080b12',
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true
      }
    });
    webChatWindow.removeMenu();
    webChatWindow.on('closed', () => {
      webChatWindow = null;
    });
    webChatWindow.webContents.setWindowOpenHandler(({ url }) => {
      if (isExternalUrl(url)) shell.openExternal(url);
      return { action: 'deny' };
    });
    await webChatWindow.loadURL(state.url);
    return { ...state, focused: false };
  }

  function openCliChat(options = {}) {
    const runtimeRoot = resolveBagoRuntimeRoot();
    const basePath = String(options.basePath || '').trim() || runtimeRoot;
    const command = [
      `Set-Location -LiteralPath ${psSingleArg(runtimeRoot)}`,
      `python -m bago_core.launcher --base-path ${psSingleArg(basePath)} chat`
    ].join('; ');
    return runVisiblePowerShell(command);
  }

  function nodeAction(args) {
    const safe = Array.isArray(args) ? args.map(value => String(value || '')) : [];
    const nodeIndex = safe.indexOf('node');
    return nodeIndex >= 0 ? safe[nodeIndex + 1] || '' : '';
  }

  function runBagoNode(args) {
    return new Promise((resolve, reject) => {
      const safe = (Array.isArray(args) ? args : []).map(a => String(a || ''));
      let runtimeRoot;
      try {
        runtimeRoot = resolveBagoRuntimeRoot();
      } catch (error) {
        reject(error);
        return;
      }
      const action = nodeAction(safe);
      const mutating = MUTATING_NODE_COMMANDS.has(action);
      if (mutating && activeNodeMutation) {
        reject(new Error(`Mutacion bloqueada: ${activeNodeMutation.action} sigue activa`));
        return;
      }
      if (mutating) {
        activeNodeMutation = {
          action,
          started_at: new Date().toISOString(),
          args: safe.slice()
        };
      }
      const cmd = `python -m bago_core.launcher ${safe.map(a => /[\s'"&|<>^]/.test(a) ? `"${a.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"` : a).join(' ')}`;
      execFile(
        'python',
        ['-m', 'bago_core.launcher', ...safe],
        { cwd: runtimeRoot, windowsHide: true, maxBuffer: 16 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (mutating) activeNodeMutation = null;
          if (error) {
            reject(new Error(`${error.message}${stderr ? ` · ${stderr.trim()}` : ''} · cwd=${runtimeRoot} · cmd=${cmd}`));
            return;
          }
          resolve({ stdout, stderr, cmd, cwd: runtimeRoot });
        }
      );
    });
  }

  function runBagoSession(args) {
    return new Promise((resolve, reject) => {
      const safe = (Array.isArray(args) ? args : []).map(value => String(value || ''));
      let runtimeRoot;
      try {
        runtimeRoot = resolveBagoRuntimeRoot();
      } catch (error) {
        reject(error);
        return;
      }
      execFile(
        'python',
        ['-m', 'bago_core.session_control', '--base-path', runtimeRoot, ...safe],
        { cwd: runtimeRoot, windowsHide: true, timeout: 180000, maxBuffer: 16 * 1024 * 1024 },
        (error, stdout, stderr) => {
          let parsed;
          try {
            parsed = JSON.parse(String(stdout || '').trim());
          } catch (parseError) {
            reject(new Error(`SessionManager devolvio JSON invalido: ${parseError.message} · ${stderr || stdout}`));
            return;
          }
          if (error || !parsed.ok) {
            reject(new Error(String(parsed.error || stderr || error && error.message || 'SessionManager fallo')));
            return;
          }
          resolve(parsed);
        }
      );
    });
  }

  function runSupervisorCmd(args) {
    return new Promise((resolve, reject) => {
      let runtimeRoot;
      try {
        runtimeRoot = resolveBagoRuntimeRoot();
      } catch (error) {
        reject(error);
        return;
      }
      const script = path.join(runtimeRoot, 'scripts', 'bago_supervisor.py');
      if (!fs.existsSync(script)) {
        reject(new Error('bago_supervisor.py no encontrado en ' + runtimeRoot));
        return;
      }
      execFile(
        'python',
        [script, ...args],
        { cwd: runtimeRoot, windowsHide: true, timeout: 15000, maxBuffer: 4 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (error) {
            reject(new Error(`${error.message}${stderr ? ` · ${stderr.trim()}` : ''}`));
            return;
          }
          try {
            const parsed = JSON.parse(stdout.trim());
            resolve({ ok: true, data: parsed, raw: stdout });
          } catch {
            resolve({ ok: true, text: stdout.trim(), raw: stdout });
          }
        }
      );
    });
  }

  async function cleanupZombies() {
    const managedPaths = [];
    try { managedPaths.push(resolveBundledRuntimeRoot()); } catch {}
    try { managedPaths.push(resolveInstalledRuntimeRoot()); } catch {}
    try { managedPaths.push(path.join(os.homedir(), '.bago')); } catch {}
    const allowList = managedPaths.filter(Boolean).map(p => p.replace(/\\/g, '\\\\').replace(/'/g, "''"));
    const scriptMarkers = ['launcher.py', 'bago_webchat.py', 'bago_supervisor.py', 'bridge.py'];
    const allowListJson = JSON.stringify(allowList);
    const markersJson = JSON.stringify(scriptMarkers);
    const command = `
      $ports = @(11434, 8080, 8081, 8082, 8083);
      $allowPaths = ${allowListJson} | Where-Object { $_ -and (Test-Path -LiteralPath $_) };
      $scriptMarkers = ${markersJson};
      $killed = 0;
      $matched = @();
      function Test-IsBagoProcess {
        param([string]$cmd, [string]$name)
        if (-not $cmd) { return $false }
        foreach ($p in $allowPaths) { if ($cmd -like ('*' + $p + '*')) { return $true } }
        foreach ($m in $scriptMarkers) { if ($cmd -like ('*' + $m)) { return $true } }
        if ($cmd -match 'bago_core[\\\\\\.\\s]') { return $true }
        if ($cmd -match 'bago[_-]?(webchat|supervisor|bridge|launcher|node_control)') { return $true }
        return $false
      }
      foreach ($p in $ports) {
        $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'TimeWait' -or $_.State -eq 'CloseWait' -or $_.State -eq 'FinWait2' };
        foreach ($c in $conns) {
          try {
            $proc = Get-CimInstance Win32_Process -Filter ('ProcessId=' + $c.OwningProcess) -ErrorAction SilentlyContinue;
            if ($proc -and (Test-IsBagoProcess -cmd $proc.CommandLine -name $proc.Name)) {
              Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue;
              $killed++;
              $matched += [ordered]@{ pid = $c.OwningProcess; reason = 'stale-port'; cmd = $proc.CommandLine }
            }
          } catch {}
        }
      }
      Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
        try {
          if (Test-IsBagoProcess -cmd $_.CommandLine -name $_.Name) {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue;
            $killed++;
            $matched += [ordered]@{ pid = $_.ProcessId; reason = 'bago-process'; cmd = $_.CommandLine }
          }
        } catch {}
      }
      $payload = [ordered]@{ ok = $true; cleaned = $killed; matched = $matched; allowlist = $allowPaths }
      Write-Output ($payload | ConvertTo-Json -Depth 4 -Compress)
    `;
    return new Promise((resolve, reject) => {
      execFile(
        'powershell.exe',
        ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', command],
        { windowsHide: true, timeout: 20000 },
        (error, stdout) => {
          if (error) {
            reject(error);
            return;
          }
          try {
            resolve(JSON.parse(stdout.trim()));
          } catch {
            resolve({ ok: true, text: stdout.trim() });
          }
        }
      );
    });
  }

  function getManagerUrl() {
    if (app.isPackaged) {
      try {
        return 'file:///' + MANAGER_HTML.replace(/\\/g, '/').replace(/^\//, '');
      } catch {
        // fall through
      }
    }
    const apiPort = (webChatState && webChatState.port) || process.env.BAGO_API_PORT || '';
    if (apiPort) return `http://${CHAT_HOST}:${apiPort}/manager/index.html`;
    return 'manager/index.html';
  }

  function getState() {
    return { mutation: activeNodeMutation };
  }

  return {
    webChatStatus,
    ensureWebChatServer,
    openWebChat,
    openCliChat,
    runBagoNode,
    runBagoSession,
    runSupervisorCmd,
    cleanupZombies,
    getManagerUrl,
    getState
  };
}

module.exports = { createRuntimeService };
