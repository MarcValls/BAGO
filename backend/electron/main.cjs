const { app, BrowserWindow, ipcMain, shell, dialog, clipboard } = require('electron');
const { spawn, execFile } = require('child_process');
const fs = require('fs');
const net = require('net');
const os = require('os');
const path = require('path');
const {
  ROOT_DIR,
  ICON_PATH,
  INSTALLS_ROOT,
  SMOKE_TEST,
  CHAT_HOST,
  CHAT_START_PORT,
  resolveBagoRuntimeRoot,
  resolveUiDist,
  resolveBundledRuntimeRoot,
  resolveInstalledRuntimeRoot,
  resolveDevelopmentRuntimeRoot,
  resolvePythonCommand,
  runVisiblePowerShell,
  findPackagedRuntimeRoot
} = require('./environment.cjs');
const { createManagerWindow } = require('./window-service.cjs');
const { registerIpcHandlers } = require('./ipc-service.cjs');
const { createRuntimeService } = require('./runtime-service.cjs');
const { createInstallService } = require('./install-service.cjs');
const { createReleaseService } = require('./release-service.cjs');
const { createDependencyService } = require('./dependency-service.cjs');
const { createAuditService } = require('./audit-service.cjs');
let dependencyService = null;
let runtimeService = null;
let installService = null;
let releaseService = null;
let auditService = null;
let shutdownRequested = false;

const ISOLATED_TEST = SMOKE_TEST || process.env.BAGO_MANAGER_AUTOMATION_TEST === '1';
if (ISOLATED_TEST) {
  app.disableHardwareAcceleration();
  app.setPath(
    'userData',
    process.env.BAGO_MANAGER_SMOKE_USER_DATA || path.join(os.tmpdir(), `bago-manager-smoke-${process.pid}`)
  );
}

const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
  app.quit();
  process.exit(0);
}

function getDependencyService() {
  if (!dependencyService) {
    dependencyService = createDependencyService({
      app,
      dialog,
      execFile,
      spawn,
      fs,
      path,
      ROOT_DIR,
      resolveBagoRuntimeRoot,
      prepareProviderCredential: (...args) => getRuntimeService().prepareProviderCredential(...args),
      getManagerState: () => ({
        mutation: getRuntimeService().getState().mutation,
        ...getReleaseService().getState()
      }),
      runVisiblePowerShell
    });
  }
  return dependencyService;
}

function getRuntimeService() {
  if (!runtimeService) {
    runtimeService = createRuntimeService({
      app,
      dialog,
      shell,
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
      resolvePythonCommand
    });
  }
  return runtimeService;
}

function getInstallService() {
  if (!installService) {
    installService = createInstallService({
      app,
      dialog,
      fs,
      path,
      BrowserWindow,
      INSTALLS_ROOT,
      ICON_PATH,
      resolveBagoRuntimeRoot,
      findPackagedRuntimeRoot,
      prepareSystemInstall: (...args) => getRuntimeService().prepareSystemInstall(...args),
      prepareSystemSourceUpdate: (...args) => getRuntimeService().prepareSystemSourceUpdate(...args),
      prepareSystemUninstall: (...args) => getRuntimeService().prepareSystemUninstall(...args)
    });
  }
  return installService;
}

function getReleaseService() {
  if (!releaseService) {
    releaseService = createReleaseService({
      BrowserWindow,
      os,
      path,
      getDependencyService,
      verifyReleaseSignature: (...args) => getRuntimeService().verifyReleaseSignature(...args),
      stageReleaseBundle: (...args) => getRuntimeService().stageReleaseBundle(...args),
      downloadReleaseAsset: (...args) => getRuntimeService().downloadReleaseAsset(...args),
      persistReleaseJob: (...args) => getRuntimeService().persistReleaseJob(...args),
      appendReleaseJobLog: (...args) => getRuntimeService().appendReleaseJobLog(...args),
      archiveReleaseJob: (...args) => getRuntimeService().archiveReleaseJob(...args),
      prepareSystemInstall: (...args) => getRuntimeService().prepareSystemInstall(...args),
      rollbackSystemInstall: (...args) => getRuntimeService().rollbackSystemInstall(...args)
    });
  }
  return releaseService;
}

function getAuditService() {
  if (!auditService) {
    auditService = createAuditService({
      ROOT_DIR,
      resolveInstalledRuntimeRoot,
      getDependencyService,
      getReleaseService
    });
  }
  return auditService;
}

app.setAppUserModelId('com.bago.installation-manager');

app.on('second-instance', () => {
  const windows = BrowserWindow.getAllWindows().filter((win) => win && !win.isDestroyed());
  if (windows.length > 0) {
    const win = windows[0];
    if (win.isMinimized()) win.restore();
    win.show();
    win.focus();
    try {
      win.webContents.send('bago:instance-active', {
        ok: true,
        message: 'BAGO ya está abierto: se ha traído la ventana actual al frente.'
      });
    } catch {}
  }
});

// Propagar INSTALLS_ROOT al preload vía env var para que scanInstallations lo incluya
process.env.BAGO_INSTALLS_ROOT = INSTALLS_ROOT;
registerIpcHandlers({
  ipcMain,
  clipboard,
  dialog,
  INSTALLS_ROOT,
  getDependencyService,
  getRuntimeService,
  getInstallService,
  getReleaseService,
  getAuditService
});

app.whenReady().then(async () => {
  try {
    await getRuntimeService().ensureWebChatServer({ reuseExternal: !ISOLATED_TEST });
  } catch (error) {
    const message = `BAGO backend warmup failed: ${error && error.message ? error.message : error}`;
    console.error(message);
    dialog.showErrorBox('BAGO backend no disponible', String(message));
    app.quit();
    return;
  }
  // P0-05 fix: create the Manager window FIRST so the user always sees a
  // recovery/loading UI. The install/repair runs in parallel; its progress
  // is streamed to the renderer through `bago:install-state` events.
  // The window is the first thing the user sees; everything else (install,
  // release jobs) is wired up after the UI is on screen.
  createManagerWindow({ getRuntimeService });
  await getReleaseService().initReleaseJobs();
  getInstallService().ensureBagoInstalled().catch(err => {
    getInstallService().emitInstallState({ phase: 'failed', error: String(err && err.message || err) });
  });
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createManagerWindow({ getRuntimeService });
  });
});

async function shutdownBago() {
  if (shutdownRequested) return false;
  shutdownRequested = true;
  try {
    if (runtimeService && typeof runtimeService.shutdown === 'function') {
      const result = await runtimeService.shutdown();
      if (result && result.canceled) {
        shutdownRequested = false;
        return false;
      }
    }
    return true;
  } catch (error) {
    console.error(`BAGO shutdown cleanup failed: ${error && error.message ? error.message : error}`);
    shutdownRequested = false;
    return false;
  }
}

app.on('before-quit', (event) => {
  if (shutdownRequested) {
    return;
  }
  event.preventDefault();
  void shutdownBago().then(shouldQuit => {
    if (shouldQuit) app.quit();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
