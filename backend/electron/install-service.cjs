function createInstallService(ctx) {
  const {
    app,
    dialog,
    fs,
    path,
    BrowserWindow,
    INSTALLS_ROOT,
    ICON_PATH,
    resolveBagoRuntimeRoot,
    findPackagedRuntimeRoot,
    prepareSystemInstall,
    prepareSystemSourceUpdate,
    prepareSystemUninstall
  } = ctx;

  const PREFS_PATH = path.join(app.getPath('userData'), 'bago-manager-prefs.json');
  let lastInstallState = { phase: 'pending', runtime: '', error: '', installDir: '' };
  let _defaultInstallDirCache = '';

  function emitInstallState(patch) {
    lastInstallState = { ...lastInstallState, ...patch, ts: Date.now() };
    for (const win of BrowserWindow.getAllWindows()) {
      if (!win.isDestroyed()) win.webContents.send('bago:install-state', lastInstallState);
    }
  }

  function getInstallState() {
    return lastInstallState;
  }

  function defaultInstallDir() {
    if (_defaultInstallDirCache) return _defaultInstallDirCache;
    _defaultInstallDirCache = path.join(INSTALLS_ROOT, 'active');
    return _defaultInstallDirCache;
  }

  function loadPrefs() {
    try {
      return JSON.parse(fs.readFileSync(PREFS_PATH, 'utf8'));
    } catch {
      return {};
    }
  }

  function savePrefs(prefs) {
    try {
      fs.writeFileSync(PREFS_PATH, JSON.stringify(prefs, null, 2));
    } catch {}
  }

  function parseInstallResult(stdout) {
    const lines = String(stdout || '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    for (let i = lines.length - 1; i >= 0; i -= 1) {
      try {
        const payload = JSON.parse(lines[i]);
        if (payload && typeof payload === 'object' && payload.installed_to) {
          return payload;
        }
      } catch {}
    }
    return null;
  }

  function buildInstallDetail(runtimePath, installResult) {
    const lines = [`Ubicación: ${runtimePath}`];
    const shortcuts = installResult && installResult.shortcuts ? installResult.shortcuts : null;
    const explorerContextMenu = installResult && installResult.explorer_context_menu ? installResult.explorer_context_menu : null;
    const profilePaths = installResult && Array.isArray(installResult.profile_paths) ? installResult.profile_paths : [];
    if (shortcuts && shortcuts.desktop && shortcuts.start_menu) {
      lines.push('Accesos directos:');
      lines.push(`- Escritorio: ${shortcuts.desktop}`);
      lines.push(`- Inicio: ${shortcuts.start_menu}`);
    }
    if (explorerContextMenu && explorerContextMenu.directory) {
      lines.push('Menu contextual:');
      lines.push(`- Directorios: ${explorerContextMenu.directory}`);
      if (explorerContextMenu.background) {
        lines.push(`- Fondo: ${explorerContextMenu.background}`);
      }
    }
    if (profilePaths.length) {
      lines.push('PowerShell bootstrap:');
      for (const profilePath of profilePaths) {
        lines.push(`- ${profilePath}`);
      }
    }
    return lines.join('\n');
  }

  async function applyInstallThroughGateway({ action, sourceRoot, installDir, mode = 'Express', configuration }) {
    if (typeof prepareSystemInstall !== 'function') throw new Error('system.install.apply no está conectado al Manager.');
    const execute = await prepareSystemInstall({
      action,
      tag: action,
      source_root: sourceRoot,
      helper_path: path.join(sourceRoot, 'install-v4.ps1'),
      install_dir: installDir,
      package_sha256: '',
      mode,
      options: {},
      ...(configuration ? { configuration } : {})
    });
    if (!execute) return null;
    return execute();
  }

  async function ensureBagoInstalled() {
    let runtimeRoot = '';
    emitInstallState({ phase: 'detecting' });
    try {
      runtimeRoot = resolveBagoRuntimeRoot();
    } catch {
      runtimeRoot = '';
    }

    const packagedRoot = findPackagedRuntimeRoot();

    if (!runtimeRoot) {
      if (!packagedRoot) {
        emitInstallState({ phase: 'failed', error: 'runtime-empaketado-ausente', installDir: '' });
        await dialog.showErrorBox('BAGO Installation Manager', 'No se encontró el runtime de BAGO empaquetado. El instalador puede estar corrupto.');
        return '';
      }

      const result = await dialog.showMessageBox({
        type: 'question',
        buttons: ['Instalar ahora', 'Cancelar'],
        defaultId: 0,
        cancelId: 1,
        title: 'BAGO no está instalado',
        message: 'No se detectó una instalación de BAGO en este equipo.',
        detail: 'El Installation Manager puede instalar BAGO automáticamente usando el paquete incluido.',
        icon: ICON_PATH
      });

      if (result.response !== 0) {
        emitInstallState({ phase: 'cancelled' });
        return '';
      }

      let installDir = defaultInstallDir();
      let installResult = null;
      emitInstallState({ phase: 'installing', installDir });
      try {
        installResult = await applyInstallThroughGateway({ action: 'install', sourceRoot: packagedRoot, installDir });
        if (!installResult) {
          emitInstallState({ phase: 'cancelled', installDir });
          return '';
        }
      } catch (err) {
        emitInstallState({ phase: 'failed', error: String(err && err.message || err), installDir });
        return '';
      }
      const verified = resolveBagoRuntimeRoot();
      emitInstallState({ phase: 'ready', runtime: verified, installDir });
      await dialog.showMessageBox({
        type: 'info', buttons: ['OK'], title: 'Instalación completada',
          message: 'BAGO se instaló correctamente.', detail: buildInstallDetail(verified, null)
      });
      return verified;
    }

    const prefs = loadPrefs();
    if (prefs.skipInstallPrompt) {
      emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
      return runtimeRoot;
    }

    const result = await dialog.showMessageBox({
      type: 'info',
      buttons: ['Continuar', 'Reparar configuración', 'Reinstalar / Actualizar', 'Nueva copia…'],
      defaultId: 0,
      cancelId: 0,
      title: 'BAGO ya está instalado',
      message: `Se detectó BAGO en:\n${runtimeRoot}`,
      detail: 'Puedes continuar, reparar la configuración, reinstalar desde cero o crear otra copia en un directorio diferente.',
      checkboxLabel: 'No volver a preguntar al inicio',
      checkboxChecked: false,
      icon: ICON_PATH
    });

    if (result.checkboxChecked) {
      prefs.skipInstallPrompt = true;
      savePrefs(prefs);
    }

    try {
      switch (result.response) {
        case 0: {
          emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
          return runtimeRoot;
        }
        case 1: {
          emitInstallState({ phase: 'repairing', installDir: runtimeRoot });
          const repairResult = await applyInstallThroughGateway({ action: 'repair', sourceRoot: packagedRoot, installDir: runtimeRoot });
          if (!repairResult) { emitInstallState({ phase: 'cancelled', runtime: runtimeRoot, installDir: runtimeRoot }); return runtimeRoot; }
          emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
          await dialog.showMessageBox({
            type: 'info', buttons: ['OK'], title: 'Reparación completada',
            message: 'La configuración de BAGO se reparó correctamente.', detail: buildInstallDetail(runtimeRoot, null)
          });
          return runtimeRoot;
        }
        case 2: {
          emitInstallState({ phase: 'reinstalling', installDir: runtimeRoot });
          const reinstallResult = await applyInstallThroughGateway({ action: 'reinstall', sourceRoot: packagedRoot, installDir: runtimeRoot });
          if (!reinstallResult) { emitInstallState({ phase: 'cancelled', runtime: runtimeRoot, installDir: runtimeRoot }); return runtimeRoot; }
          const verified = resolveBagoRuntimeRoot();
          emitInstallState({ phase: 'ready', runtime: verified, installDir: runtimeRoot });
          await dialog.showMessageBox({
            type: 'info', buttons: ['OK'], title: 'Reinstalación completada',
            message: 'BAGO se reinstaló correctamente.', detail: buildInstallDetail(verified, null)
          });
          return verified;
        }
        case 3: {
          if (!packagedRoot) {
            emitInstallState({ phase: 'failed', error: 'runtime-empaketado-ausente' });
            await dialog.showErrorBox('Error', 'No se encontró el runtime empaquetado para crear una nueva copia.');
            return runtimeRoot;
          }
          const { filePaths } = await dialog.showOpenDialog({
            title: 'Seleccionar directorio para la nueva copia de BAGO',
            defaultPath: path.join(path.dirname(defaultInstallDir()), 'BAGO-dev'),
            properties: ['openDirectory', 'createDirectory', 'promptToCreate']
          });
          if (!filePaths || !filePaths[0]) {
            emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
            return runtimeRoot;
          }
          const newDir = filePaths[0];
          emitInstallState({ phase: 'installing', installDir: newDir });
          const copyResult = await applyInstallThroughGateway({ action: 'new-copy', sourceRoot: packagedRoot, installDir: newDir });
          if (!copyResult) { emitInstallState({ phase: 'cancelled', runtime: runtimeRoot, installDir: newDir }); return runtimeRoot; }
          emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: newDir });
          await dialog.showMessageBox({
            type: 'info', buttons: ['OK'], title: 'Nueva copia completada',
            message: 'La nueva copia de BAGO se instaló correctamente.', detail: buildInstallDetail(newDir, null)
          });
          return runtimeRoot;
        }
        default:
          emitInstallState({ phase: 'ready', runtime: runtimeRoot, installDir: runtimeRoot });
          return runtimeRoot;
      }
    } catch (err) {
      emitInstallState({ phase: 'failed', error: String(err && err.message || err) });
      await dialog.showErrorBox('BAGO Installation Manager', 'Fallo en la operacion de instalacion: ' + (err && err.message || err));
      return '';
    }
  }

  async function performInstallAction(payload) {
    const { action, targetDir, sourceRoot, branch, purgeState } = payload || {};
    let packagedRoot = '';
    const requirePackagedRoot = () => {
      if (!packagedRoot) packagedRoot = findPackagedRuntimeRoot();
      if (!packagedRoot) {
        throw new Error('No se encontró el runtime empaquetado.');
      }
      return packagedRoot;
    };
    let installDir = targetDir;
    if (action === 'repair') {
      const runtimePack = requirePackagedRoot();
      if (!installDir) {
        try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para reparar: ' + e.message); }
      }
      emitInstallState({ phase: 'repairing', installDir });
      try {
        const receipt = await applyInstallThroughGateway({ action: 'repair', sourceRoot: runtimePack, installDir });
        if (!receipt) return { ok: false, cancelled: true, action, installDir };
      } finally {
        emitInstallState({ phase: 'ready', installDir });
      }
      return { ok: true, action: 'repair', installDir };
    }
    if (action === 'reinstall') {
      const runtimePack = requirePackagedRoot();
      if (!installDir) {
        try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para reinstalar: ' + e.message); }
      }
      emitInstallState({ phase: 'reinstalling', installDir });
      try {
        const receipt = await applyInstallThroughGateway({ action: 'reinstall', sourceRoot: runtimePack, installDir });
        if (!receipt) return { ok: false, cancelled: true, action, installDir };
      } finally {
        emitInstallState({ phase: 'ready', installDir });
      }
      return { ok: true, action: 'reinstall', installDir };
    }
    if (action === 'new-copy') {
      const runtimePack = requirePackagedRoot();
      if (!installDir) throw new Error('Se requiere targetDir para nueva copia.');
      emitInstallState({ phase: 'installing', installDir });
      try {
        const receipt = await applyInstallThroughGateway({ action: 'new-copy', sourceRoot: runtimePack, installDir });
        if (!receipt) return { ok: false, cancelled: true, action, installDir };
      } finally {
        emitInstallState({ phase: 'ready', installDir });
      }
      return { ok: true, action: 'new-copy', installDir };
    }
    if (action === 'source-update') {
      const rawSource = String(sourceRoot || '').trim();
      if (!rawSource) throw new Error('Se requiere sourceRoot para actualizar desde fuente/branch.');
      const cleanSource = path.resolve(rawSource);
      if (!fs.existsSync(path.join(cleanSource, 'install-v4.ps1')) || !fs.existsSync(path.join(cleanSource, 'bago_core', 'launcher.py'))) {
        throw new Error('La fuente no contiene install-v4.ps1 y bago_core/launcher.py.');
      }
      if (!installDir) {
        try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para actualizar: ' + e.message); }
      }
      const branchName = String(branch || 'main').trim() || 'main';
      if (typeof prepareSystemSourceUpdate !== 'function') throw new Error('system.source.update no está conectado al Manager.');
      const sourceReceipt = await prepareSystemSourceUpdate({ source_root: cleanSource, branch: branchName });
      if (!sourceReceipt) return { ok: false, cancelled: true, action, installDir, sourceRoot: cleanSource, branch: branchName };
      emitInstallState({ phase: 'reinstalling', installDir });
      try {
        const receipt = await applyInstallThroughGateway({ action: 'source-update', sourceRoot: cleanSource, installDir });
        if (!receipt) return { ok: false, cancelled: true, action, installDir, sourceRoot: cleanSource, branch: branchName };
      } finally {
        emitInstallState({ phase: 'ready', installDir });
      }
      return { ok: true, action: 'source-update', installDir, sourceRoot: cleanSource, branch: branchName };
    }
    if (action === 'uninstall') {
      if (!installDir) {
        try { installDir = resolveBagoRuntimeRoot(); } catch (e) { throw new Error('No hay instalación detectada para desinstalar: ' + e.message); }
      }
      installDir = path.resolve(installDir);
      emitInstallState({ phase: 'uninstalling', installDir });
      try {
        if (typeof prepareSystemUninstall !== 'function') throw new Error('system.install.uninstall no está conectado al Manager.');
        const receipt = await prepareSystemUninstall({ install_dir: installDir, purge_state: !!purgeState });
        if (!receipt) return { ok: false, cancelled: true, action, installDir };
      } finally {
        emitInstallState({ phase: 'ready', installDir: '' });
      }
      return { ok: true, action: 'uninstall', installDir };
    }
    throw new Error(`Acción desconocida: ${action}`);
  }

  return {
    emitInstallState,
    getInstallState,
    defaultInstallDir,
    ensureBagoInstalled,
    performInstallAction
  };
}

module.exports = { createInstallService };
