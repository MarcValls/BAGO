const crypto = require('crypto');
const { createSystemInstallClient } = require('./system-install-client.cjs');
const { createManagerSettingsClient } = require('./manager-settings-client.cjs');
const { createProjectWriteClient } = require('./project-write-client.cjs');
const { createProcessExecutionClient } = require('./process-execution-client.cjs');

function createRuntimeService(ctx) {
  const {
    app,
    dialog,
    shell,
    spawn,
    fs,
    net,
    path,
    BrowserWindow,
    ROOT_DIR,
    ICON_PATH,
    CHAT_HOST,
    CHAT_START_PORT,
    resolveBagoRuntimeRoot,
    resolveUiDist,
    resolveInstalledRuntimeRoot,
    resolveDevelopmentRuntimeRoot,
    resolvePythonCommand
  } = ctx;

  const MUTATING_NODE_COMMANDS = new Set(['connect', 'disconnect', 'set-mode']);
  const MANAGER_HTML = path.join(ROOT_DIR, 'manager', 'index.html');
  const systemInstallClient = createSystemInstallClient({
    apiBase: async () => {
      const state = await ensureWebChatServer();
      return `http://${state.host}:${state.port}`;
    },
    confirm: async operation => {
      if (!dialog || typeof dialog.showMessageBox !== 'function') throw new Error('No hay confirmación desktop disponible.');
      const rollback = operation.type === 'rollback';
      const sourceUpdate = operation.type === 'source-update';
      const uninstall = operation.type === 'uninstall';
      const credential = operation.type === 'credential';
      const installAction = String(operation.action || 'release-job');
      const installLabels = {
        install: 'instalar BAGO',
        repair: 'reparar configuración de BAGO',
        reinstall: 'reinstalar BAGO',
        'new-copy': 'crear una copia de BAGO',
        'source-update': 'actualizar BAGO desde la fuente seleccionada',
        'release-job': 'instalar una release verificada'
      };
      const installLabel = installLabels[installAction] || 'aplicar instalación BAGO';
      const result = await dialog.showMessageBox({
        type: 'warning',
        buttons: [rollback ? 'Restaurar runtime' : (sourceUpdate ? 'Actualizar fuente' : (uninstall ? 'Desinstalar BAGO' : (credential ? 'Guardar credencial' : 'Continuar'))), 'Cancelar'],
        defaultId: 1,
        cancelId: 1,
        title: rollback ? 'Autorizar rollback de BAGO' : (sourceUpdate ? 'Autorizar actualización de fuente' : (uninstall ? 'Autorizar desinstalación de BAGO' : (credential ? 'Autorizar credencial del proveedor' : 'Autorizar instalación de BAGO'))),
        message: credential
          ? `¿Guardar la credencial API del proveedor ${operation.provider}?`
          : rollback
          ? `${operation.automatic ? 'La instalación no superó la validación. ' : ''}Restaurar el runtime de ${operation.installDir}?`
          : sourceUpdate
            ? `¿Actualizar ${operation.sourceRoot} desde ${operation.originUrl}, rama ${operation.branch}?`
          : uninstall
            ? `¿Desinstalar BAGO de ${operation.installDir}?`
          : `¿Autorizar ${installLabel}${operation.tag && installAction === 'release-job' ? ` ${operation.tag}` : ''} en ${operation.installDir}?`,
        detail: credential
          ? `La credencial se guardará en el almacén protegido del backend. Configuración ligada: ${operation.configurationDigest}`
          : rollback
          ? [`Backup: ${operation.backupPath || '(instalación nueva)'}`, `Datos desplazados: ${operation.displacedPath}`].join('\n')
          : sourceUpdate
            ? [`HEAD aprobado: ${operation.expectedHead}`, `SHA-256 del origen: ${operation.originSha256}`, 'Después de actualizar la fuente se pedirá una autorización independiente para instalarla.'].join('\n')
          : uninstall
            ? [`Backup ZIP en: ${operation.backupRoot}`, operation.purgeState ? `También se borrará el estado: ${operation.userStateDir}` : `Se conservará el estado: ${operation.userStateDir}`, `Árbol aprobado SHA-256: ${operation.treeSha256}`, `CLI de desinstalación SHA-256: ${operation.cliSha256}`, 'La desinstalación requiere una autorización fuerte y puede solicitar UAC.'].join('\n')
          : [
              `Árbol de fuente SHA-256: ${operation.sourceTreeSha256}`,
              `Helper SHA-256: ${operation.helperSha256}`,
              operation.packageSha256 ? `Bundle SHA-256: ${operation.packageSha256}` : '',
              `Configuración aprobada SHA-256: ${operation.configurationDigest}`,
              `Modo: ${operation.mode}`,
              installAction === 'install' || installAction === 'new-copy'
                ? 'La instalación empieza con providers desactivados y sin credenciales.'
                : 'La acción está ligada a la configuración actualmente instalada.'
            ].filter(Boolean).join('\n')
      });
      return result.response === 0;
    }
  });
  const managerSettingsClient = createManagerSettingsClient({
    apiBase: async () => {
      const state = await ensureWebChatServer();
      return `http://${state.host}:${state.port}`;
    },
    confirm: async target => {
      if (!dialog || typeof dialog.showMessageBox !== 'function') throw new Error('No hay confirmación desktop disponible.');
      const isSelection = target.resource === 'install_selection';
      const result = await dialog.showMessageBox({
        type: 'warning', buttons: ['Guardar', 'Cancelar'], defaultId: 1, cancelId: 1,
        title: 'Autorizar configuración del Manager',
        message: isSelection ? `¿Asignar ${target.install_dir} al rol ${target.role}?` : '¿Guardar el registro de cadenas del Manager?',
        detail: isSelection
          ? `Launcher SHA-256: ${target.launcher_sha256}\nDestino de configuración: ${target.path}`
          : `${target.chain_count} cadenas (${(target.chain_ids || []).join(', ')}) · SHA-256: ${target.chains_sha256}\nDestino de configuración: ${target.path}`
      });
      return result.response === 0;
    }
  });
  const processExecutionClient = createProcessExecutionClient({
    apiBase: async () => {
      const state = await ensureWebChatServer({ skipSessionSync: true });
      return `http://${state.host}:${state.port}`;
    },
    confirm: async operation => {
      if (!dialog || typeof dialog.showMessageBox !== 'function') throw new Error('No hay confirmación desktop disponible.');
      const result = await dialog.showMessageBox({
        type: 'warning', buttons: ['Ejecutar', 'Cancelar'], defaultId: 1, cancelId: 1,
        title: 'Autorizar ejecución BAGO',
        message: `¿Ejecutar la operación ${operation.operation}?`,
        detail: [
          `Programa/efecto: ${operation.python_module || operation.python_script || operation.operation}`,
          `Sesión activa: ${operation.sessionId}`,
          `Directorio: ${operation.cwd}`,
          operation.cleanup_roots ? `Raíces BAGO autorizadas: ${operation.cleanup_roots.join(', ')}` : '',
          operation.process_id ? `Proceso webchat PID: ${operation.process_id} · puerto: ${operation.port} · runtime: ${operation.python_root}` : '',
          `Argumentos exactos: ${operation.argv.map(value => JSON.stringify(value)).join(' ') || '(ninguno)'}`,
          `Timeout: ${operation.timeout_seconds}s`
        ].join('\\n')
      });
      return result.response === 0;
    }
  });
  const projectWriteClient = createProjectWriteClient({
    apiBase: async () => {
      const state = await ensureWebChatServer();
      return `http://${state.host}:${state.port}`;
    },
    confirm: async target => {
      if (!dialog || typeof dialog.showMessageBox !== 'function') throw new Error('No hay confirmación desktop disponible.');
      const result = await dialog.showMessageBox({
        type: 'warning', buttons: ['Vincular', 'Cancelar'], defaultId: 1, cancelId: 1,
        title: 'Autorizar vínculo del proyecto',
        message: `¿Vincular el proyecto ${target.requested_root}?`,
        detail: `Destino aprobado: ${target.path}\nRaíz confiable: ${target.allowed_root}\nSHA-256 de identidad: ${target.root_digest}`
      });
      return result.response === 0;
    }
  });

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
    const explicit = String(process.env.BAGO_MANAGER_BASE_PATH || '').trim();
    if (explicit) return path.resolve(explicit);
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
    if (!options.skipSessionSync && sessionId && provider) {
      const sessionArgs = ['apply', '--session-id', sessionId, '--provider', provider];
      if (model) sessionArgs.push('--model', model);
      if (bridges.length) sessionArgs.push('--bridges', bridges.join(','));
      sessionArgs.push('--force');
      try {
        const synced = await runBagoSession(sessionArgs);
        if (synced.canceled) throw new Error('Apertura cancelada por el usuario.');
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

  async function verifyReleaseSignature(signaturePath, bundlePath) {
    if (!webChatState) throw new Error('BAGO API local no está activa');
    const response = await fetch(`http://${webChatState.host}:${webChatState.port}/release/jobs/verify-signature`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signature_path: signaturePath, bundle_path: bundlePath })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) throw new Error(result.error || `Verificación de firma rechazada (HTTP ${response.status})`);
    return result;
  }

  async function stageReleaseBundle(jobId, bundlePath) {
    if (!webChatState) throw new Error('BAGO API local no está activa');
    const response = await fetch(`http://${webChatState.host}:${webChatState.port}/release/jobs/stage-bundle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, bundle_path: bundlePath })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) throw new Error(result.error || `Preparación del bundle rechazada (HTTP ${response.status})`);
    return result;
  }

  async function downloadReleaseAsset(operation, signal) {
    if (!webChatState) await ensureWebChatServer();
    if (!webChatState) throw new Error('BAGO API local no está activa');
    const response = await fetch(`http://${webChatState.host}:${webChatState.port}/release/jobs/download-asset`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal,
      body: JSON.stringify(operation)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) {
      const error = new Error(result.error || `Descarga del asset rechazada (HTTP ${response.status})`);
      error.code = result.code || '';
      throw error;
    }
    return result;
  }

  async function persistReleaseJob(job) {
    if (!webChatState) throw new Error('BAGO API local no está activa');
    const response = await fetch(`http://${webChatState.host}:${webChatState.port}/release/jobs/persist`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: job.id, state: job })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) throw new Error(result.error || `Persistencia del job rechazada (HTTP ${response.status})`);
    return result;
  }

  async function appendReleaseJobLog(jobId, record) {
    if (!webChatState) throw new Error('BAGO API local no está activa');
    const response = await fetch(`http://${webChatState.host}:${webChatState.port}/release/jobs/append-log`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ job_id: jobId, record })
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) throw new Error(result.error || `Append del log rechazado (HTTP ${response.status})`);
    return result;
  }

  async function archiveReleaseJob(jobId, archivedAt) {
    if (!webChatState) throw new Error('BAGO API local no está activa');
    const interactionId = `release-job-archive:${jobId}:${crypto.randomUUID()}`;
    const base = { job_id: jobId, archived_at: archivedAt, interaction_id: interactionId };
    const requestArchive = async extra => {
      const response = await fetch(`http://${webChatState.host}:${webChatState.port}/release/jobs/archive`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Bago-Channel': 'desktop' },
        body: JSON.stringify({ ...base, ...extra })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || `Archivado rechazado (HTTP ${response.status})`);
      return result;
    };
    const challengeResult = await requestArchive({ authorization_action: 'challenge' });
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    if (!challenge || !challenge.challenge_id) throw new Error('El gateway no devolvió el challenge de archivado.');
    const approval = await requestArchive({
      authorization_action: 'approve', challenge_id: challenge.challenge_id, user_decision: 'approve'
    });
    const permit = approval.authorization && approval.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de archivado.');
    return await requestArchive({ authorization_action: 'execute', authorization_permit: permit.token });
  }

  function prepareSystemInstall(operation) {
    return systemInstallClient.prepare(operation);
  }

  function prepareSystemSourceUpdate(operation) {
    return systemInstallClient.prepareSourceUpdate(operation);
  }

  function prepareSystemUninstall(operation) {
    return systemInstallClient.prepareUninstall(operation);
  }

  function prepareProviderCredential(operation) {
    return systemInstallClient.prepareProviderCredential(operation);
  }

  function writeManagerSetting(operation) {
    return managerSettingsClient.write(operation);
  }

  function rollbackSystemInstall(operation) {
    return systemInstallClient.rollback(operation);
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

  async function stopWebChatProcess() {
    const child = webChatProcess;
    if (child && child.exitCode === null && !child.killed) {
      const result = await processExecutionClient.execute('stop_webchat', []);
      if (result.canceled) return result;
      if (result.termination_scheduled !== true || result.effect_id !== 'process.terminate') {
        throw new Error('ExecutionGateway no confirmó el cierre autorizado del backend.');
      }
      if (child.exitCode === null && !child.killed) {
        await new Promise((resolve, reject) => {
          const timer = setTimeout(() => reject(new Error('El backend no terminó después del efecto process.terminate.')), 5000);
          child.once('exit', () => { clearTimeout(timer); resolve(); });
          if (child.exitCode !== null || child.killed) { clearTimeout(timer); resolve(); }
        });
      }
    }
    if (webChatWindow && !webChatWindow.isDestroyed()) {
      try { webChatWindow.removeAllListeners('closed'); } catch {}
      try { webChatWindow.close(); } catch {}
      try { webChatWindow.destroy(); } catch {}
      webChatWindow = null;
    }
    webChatProcess = null;
    webChatState = null;
    return { ok: true };
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

  async function linkProjectRoot(root) {
    const result = await projectWriteClient.link(root);
    if (!result) return { ok: false, canceled: true, message: 'Vinculación cancelada' };
    return {
      ...result,
      canceled: false,
      path: String(result.data?.root || root || ''),
      root: String(result.data?.root || root || '')
    };
  }

  function openCliChat(options = {}) {
    const developmentRoot = resolveDevelopmentRuntimeRoot();
    const runtimeRoot = developmentRoot || resolveBagoRuntimeRoot();
    const basePath = String(options.basePath || '').trim() || resolveDefaultBasePath(runtimeRoot);
    const provider = String(options.provider || '').trim();
    const model = String(options.model || '').trim();
    const sessionId = String(options.sessionId || '').trim();
    if (!options.skipSessionSync && sessionId && provider) {
      const sessionArgs = ['apply', '--session-id', sessionId, '--provider', provider];
      if (model) sessionArgs.push('--model', model);
      sessionArgs.push('--force');
      return runBagoSession(sessionArgs).then(sync => {
        if (sync.canceled) return { ok: false, canceled: true };
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

  async function runBagoNode(args) {
    const safe = (Array.isArray(args) ? args : []).map(value => String(value ?? ''));
    const action = nodeAction(safe);
    const mutating = MUTATING_NODE_COMMANDS.has(action);
    if (mutating && activeNodeMutation) throw new Error(`Mutacion bloqueada: ${activeNodeMutation.action} sigue activa`);
    if (mutating) activeNodeMutation = { action, started_at: new Date().toISOString(), args: safe.slice() };
    try {
      const result = await processExecutionClient.execute('launcher', safe);
      if (result.canceled) return result;
      if (result.exit_code !== 0) throw new Error(`${result.stderr || `BAGO terminó con código ${result.exit_code}`} · cwd=${result.cwd}`);
      return { stdout: result.stdout, stderr: result.stderr, cmd: `${result.python_module} ${safe.join(' ')}`, cwd: result.cwd };
    } finally {
      if (mutating) activeNodeMutation = null;
    }
  }

  function runBagoSession(args) {
    const safe = (Array.isArray(args) ? args : []).map(value => String(value ?? ''));
    return processExecutionClient.execute('session_control', safe).then(result => {
      if (result.canceled) return result;
      let parsed;
      try { parsed = JSON.parse(String(result.stdout || '').trim()); }
      catch (error) { throw new Error(`SessionManager devolvió JSON inválido: ${error.message} · ${result.stderr || result.stdout}`); }
      if (result.exit_code !== 0 || !parsed.ok) throw new Error(String(parsed.error || result.stderr || `SessionManager terminó con código ${result.exit_code}`));
      return parsed;
    });
  }

  function runSupervisorCmd(args) {
    return processExecutionClient.execute('supervisor', Array.isArray(args) ? args : []).then(result => {
      if (result.canceled) return result;
      if (result.exit_code !== 0) throw new Error(`${result.stderr || `Supervisor terminó con código ${result.exit_code}`} · cwd=${result.cwd}`);
      const stdout = String(result.stdout || '');
      try {
        return { ok: true, data: JSON.parse(stdout.trim()), raw: stdout };
      } catch {
        return { ok: true, text: stdout.trim(), raw: stdout };
      }
    });
  }

  async function cleanupZombies() {
    return processExecutionClient.execute('cleanup_zombies', []);
  }

  async function shutdown() {
    return await stopWebChatProcess();
  }

  function runAuthorizedProcess(operation, argv) {
    if (!['github_cli', 'git_identity'].includes(String(operation || ''))) {
      throw new Error('Operación de proceso externo no permitida');
    }
    return processExecutionClient.execute(operation, Array.isArray(argv) ? argv : []);
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
    verifyReleaseSignature,
    stageReleaseBundle,
    downloadReleaseAsset,
      persistReleaseJob,
      appendReleaseJobLog,
    archiveReleaseJob,
    prepareSystemInstall,
    prepareSystemSourceUpdate,
    prepareSystemUninstall,
    prepareProviderCredential,
    writeManagerSetting,
    rollbackSystemInstall,
    openWebChat,
    openCliChat,
    chooseWorkspaceRoot,
    linkProjectRoot,
    runBagoNode,
    runAuthorizedProcess,
    runBagoSession,
    runSupervisorCmd,
    cleanupZombies,
    shutdown,
    getManagerUrl,
    getState
  };
}

module.exports = { createRuntimeService };
