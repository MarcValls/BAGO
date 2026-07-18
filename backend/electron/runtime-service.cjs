function createRuntimeService(ctx) {
  const {
    app,
    dialog,
    shell,
    execFile,
    spawn,
    fs,
    net,
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
    resolveDevelopmentRuntimeRoot,
    resolvePythonCommand,
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

  function resolveDefaultBasePath(runtimeRoot) {
    const installedRoot = resolveInstalledRuntimeRoot();
    if (installedRoot) return installedRoot;
    const devRoot = resolveDevelopmentRuntimeRoot();
    if (devRoot) return devRoot;
    return runtimeRoot;
  }

  function pythonRuntime() {
    return resolvePythonCommand();
  }

  function pythonArgs(args) {
    const runtime = pythonRuntime();
    return { runtime, args: [...runtime.argsPrefix, ...args] };
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
    const timer = setTimeout(() => controller.abort(), 2500);
    try {
      const response = await fetch(`http://${CHAT_HOST}:${port}/health`, { signal: controller.signal });
      if (!response.ok) return false;
      const data = await response.json();
      return !!(data && data.ok && data.ready);
    } catch {
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  async function isTcpPortOccupied(port) {
    return await new Promise((resolve) => {
      const socket = net.createConnection({ host: CHAT_HOST, port });
      const finish = (occupied) => {
        socket.removeAllListeners();
        try { socket.destroy(); } catch {}
        resolve(occupied);
      };
      socket.setTimeout(700);
      socket.once('connect', () => finish(true));
      socket.once('timeout', () => finish(false));
      socket.once('error', (error) => {
        const code = String(error && error.code || '');
        if (code === 'ECONNREFUSED' || code === 'EHOSTUNREACH' || code === 'ENETUNREACH' || code === 'EADDRNOTAVAIL') {
          finish(false);
          return;
        }
        finish(true);
      });
    });
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
    const basePath = requestedBasePath || resolveDefaultBasePath(runtimeRoot);
    const uiDist = resolveUiDist(runtimeRoot);
    const mayReuseExternal = Boolean(options.reuseExternal) && (!requestedBasePath || requestedBasePath === runtimeRoot);
    if (!uiDist) {
      throw new Error(`ui-react/dist no encontrado para ${runtimeRoot}`);
    }

    const sessionId = String(options.sessionId || '').trim();
    const provider = String(options.provider || '').trim();
    const model = String(options.model || '').trim();
    const bridges = Array.isArray(options.bridges)
      ? options.bridges.map(value => String(value || '').trim()).filter(Boolean)
      : [];
    if (sessionId && provider) {
      const sessionArgs = ['apply', '--session-id', sessionId, '--provider', provider];
      if (model) sessionArgs.push('--model', model);
      if (bridges.length) sessionArgs.push('--bridges', bridges.join(','));
      sessionArgs.push('--force');
      try {
        await runBagoSession(sessionArgs);
      } catch (error) {
        throw new Error(`No se pudo sincronizar la sesión activa antes de abrir el chat: ${error.message}`);
      }
    }

    if (webChatState && webChatState.base_path === basePath && await probeWebChat(webChatState.port)) {
      return webChatState;
    }

    const startPort = Number.isFinite(CHAT_START_PORT) && CHAT_START_PORT > 0 ? CHAT_START_PORT : 8080;
    for (let port = startPort; port < startPort + 32; port += 1) {
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

      if (await isTcpPortOccupied(port)) {
        continue;
      }

      const invocation = pythonArgs([
          '-m', 'bago_core.launcher',
          '--base-path', basePath,
          'serve',
          '--host', CHAT_HOST,
          '--port', String(port),
          '--ui-dist', uiDist
        ]);
      let spawnError = null;
      let stderrText = '';
      const child = spawn(
        invocation.runtime.command,
        invocation.args,
        {
          cwd: runtimeRoot,
          env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
          stdio: ['ignore', 'ignore', 'pipe'],
          windowsHide: true
        }
      );
      webChatProcess = child;
      child.once('error', (error) => {
        spawnError = error;
      });
      if (child.stderr) {
        child.stderr.on('data', (chunk) => {
          if (stderrText.length < 8192) stderrText += String(chunk || '');
        });
      }
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
      if (spawnError || child.exitCode !== null || stderrText.trim()) {
        const details = [
          `python=${invocation.runtime.display}`,
          `cwd=${runtimeRoot}`,
          `base_path=${basePath}`,
          `port=${port}`,
        ];
        if (spawnError) details.push(`spawn=${spawnError.message}`);
        if (child.exitCode !== null) details.push(`exit=${child.exitCode}`);
        if (stderrText.trim()) details.push(`stderr=${stderrText.trim()}`);
        throw new Error(`No se pudo arrancar BAGO web chat (${details.join(' · ')})`);
      }
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

  function stopWebChatProcess() {
    if (webChatWindow && !webChatWindow.isDestroyed()) {
      try { webChatWindow.removeAllListeners('closed'); } catch {}
      try { webChatWindow.close(); } catch {}
      try { webChatWindow.destroy(); } catch {}
      webChatWindow = null;
    }
    if (webChatProcess && webChatProcess.exitCode === null && !webChatProcess.killed) {
      try {
        if (process.platform === 'win32' && webChatProcess.pid) {
          spawn('taskkill.exe', ['/PID', String(webChatProcess.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' }).unref();
        } else {
          webChatProcess.kill('SIGTERM');
        }
      } catch {}
    }
    webChatProcess = null;
    webChatState = null;
  }

  async function chooseWorkspaceRoot(options = {}) {
    if (!dialog || typeof dialog.showOpenDialog !== 'function') {
      throw new Error('Dialog de sistema no disponible');
    }
    const defaultPath = String(options.defaultPath || options.basePath || options.initialPath || '').trim();
    const result = await dialog.showOpenDialog({
      defaultPath: defaultPath || undefined,
      properties: ['openDirectory', 'createDirectory', 'promptToCreate']
    });
    if (result.canceled || !Array.isArray(result.filePaths) || !result.filePaths.length) {
      return { ok: false, canceled: true, message: 'Selección cancelada' };
    }
    const root = String(result.filePaths[0] || '').trim();
    return { ok: true, canceled: false, path: root, filePath: root, filePaths: [root] };
  }

  function linkProjectRoot(root) {
    return new Promise((resolve, reject) => {
      const cleanRoot = String(root || '').trim();
      if (!cleanRoot) {
        reject(new Error('Ruta de workspace vacía'));
        return;
      }
      const scriptCandidates = [
        path.join(ROOT_DIR, '.bago', 'tools', 'project_memory.py'),
        path.join(ROOT_DIR, '.gabo', 'tools', 'project_memory.py')
      ];
      const script = scriptCandidates.find(candidate => fs.existsSync(candidate));
      if (!script) {
        reject(new Error(`project_memory.py no encontrado en ${ROOT_DIR}`));
        return;
      }
      execFile(
        'python',
        [script, '--root', cleanRoot, 'link'],
        { cwd: ROOT_DIR, windowsHide: true, timeout: 15000, maxBuffer: 4 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (error) {
            reject(new Error(`${error.message}${stderr ? ` · ${stderr.trim()}` : ''}`));
            return;
          }
          resolve({
            ok: true,
            canceled: false,
            path: cleanRoot,
            root: cleanRoot,
            message: `workspace vinculado: ${cleanRoot}`,
            stdout: String(stdout || '').trim()
          });
        }
      );
    });
  }

  function openCliChat(options = {}) {
    const developmentRoot = resolveDevelopmentRuntimeRoot();
    const runtimeRoot = developmentRoot || resolveBagoRuntimeRoot();
    const basePath = String(options.basePath || '').trim() || resolveDefaultBasePath(runtimeRoot);
    const provider = String(options.provider || '').trim();
    const model = String(options.model || '').trim();
    const sessionId = String(options.sessionId || '').trim();
    if (sessionId && provider) {
      const sessionArgs = ['apply', '--session-id', sessionId, '--provider', provider];
      if (model) sessionArgs.push('--model', model);
      sessionArgs.push('--force');
      return runBagoSession(sessionArgs).then(() => {
        const providerArgs = provider ? ` --provider ${psSingleArg(provider)}` : '';
        const modelArgs = model ? ` --model ${psSingleArg(model)}` : '';
        const python = pythonRuntime();
        const command = [
          `Set-Location -LiteralPath ${psSingleArg(runtimeRoot)}`,
          `& ${psSingleArg(python.command)} ${python.argsPrefix.map(psSingleArg).join(' ')} -m bago_core.launcher --base-path ${psSingleArg(basePath)}${providerArgs}${modelArgs} chat`.replace('  ', ' ')
        ].join('; ');
        return {
          ok: true,
          mode: 'manual-command',
          command,
          cwd: runtimeRoot,
          base_path: basePath,
          development_root: developmentRoot || ''
        };
      });
    }
      const providerArgs = provider ? ` --provider ${psSingleArg(provider)}` : '';
      const modelArgs = model ? ` --model ${psSingleArg(model)}` : '';
      const python = pythonRuntime();
      const command = [
          `Set-Location -LiteralPath ${psSingleArg(runtimeRoot)}`,
          `& ${psSingleArg(python.command)} ${python.argsPrefix.map(psSingleArg).join(' ')} -m bago_core.launcher --base-path ${psSingleArg(basePath)}${providerArgs}${modelArgs} chat`.replace('  ', ' ')
    ].join('; ');
    return {
      ok: true,
      mode: 'manual-command',
      command,
      cwd: runtimeRoot,
      base_path: basePath,
      development_root: developmentRoot || ''
    };
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
      const basePath = resolveDefaultBasePath(runtimeRoot);
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
      const formatCmdArg = (arg) => {
        const s = String(arg || '');
        if (!/[\s'"&|<>^]/.test(s)) return s;
        return `"${s.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
      };
      const invocation = pythonArgs(['-m', 'bago_core.launcher', ...safe]);
      const cmd = `${formatCmdArg(invocation.runtime.display)} ${invocation.args.map(formatCmdArg).join(' ')}`;
      execFile(
        invocation.runtime.command,
        invocation.args,
        { cwd: runtimeRoot, env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }, windowsHide: true, maxBuffer: 16 * 1024 * 1024 },
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
      const basePath = resolveDefaultBasePath(runtimeRoot);
      const invocation = pythonArgs(['-m', 'bago_core.session_control', '--base-path', basePath, ...safe]);
      execFile(
        invocation.runtime.command,
        invocation.args,
        { cwd: runtimeRoot, env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' }, windowsHide: true, timeout: 180000, maxBuffer: 16 * 1024 * 1024 },
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

  async function cleanupManagedRuntime() {
    const cleanRoot = String(ROOT_DIR || '').replace(/\\/g, '\\\\').replace(/'/g, "''");
    const command = `
      $root = '${cleanRoot}';
      $patterns = @(
        ('-m bago_core.launcher'),
        ('--base-path ' + $root),
        ('bago_core\\\\launcher.py'),
        ('bago_core/session_control'),
        ('bago_webchat'),
        ('--ui-dist ' + $root)
      );
      $pids = @();
      Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -in @('python.exe', 'pythonw.exe', 'node.exe') -and $_.CommandLine
      } | ForEach-Object {
        $cmd = $_.CommandLine;
        $match = $false;
        foreach ($pattern in $patterns) {
          if ($cmd -like ('*' + $pattern + '*')) { $match = $true; break; }
        }
        if ($match) {
          $pids += $_.ProcessId;
        }
      }
      $pids = $pids | Select-Object -Unique;
      foreach ($pid in $pids) {
        try {
          Start-Process -FilePath taskkill.exe -ArgumentList @('/PID', [string]$pid, '/T', '/F') -WindowStyle Hidden -Wait -ErrorAction SilentlyContinue | Out-Null
        } catch {}
      }
      [ordered]@{ ok = $true; cleaned = $pids.Count; pids = $pids } | ConvertTo-Json -Depth 4 -Compress
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

  async function shutdown() {
    stopWebChatProcess();
    try {
      await cleanupManagedRuntime();
    } catch {}
    try {
      await cleanupZombies();
    } catch {}
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
    chooseWorkspaceRoot,
    linkProjectRoot,
    runBagoNode,
    runBagoSession,
    runSupervisorCmd,
    cleanupZombies,
    shutdown,
    getManagerUrl,
    getState
  };
}

module.exports = { createRuntimeService };
