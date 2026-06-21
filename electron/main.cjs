const { app, BrowserWindow, ipcMain, shell, dialog } = require('electron');
const { spawn, execFile } = require('child_process');
const fs = require('fs');
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
if (SMOKE_TEST) {
  app.disableHardwareAcceleration();
  app.setPath('userData', path.join(os.tmpdir(), 'bago-manager-smoke'));
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
      resolveDevelopmentRuntimeRoot,
      runVisiblePowerShell
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
      getDependencyService
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
      getDependencyService
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

// Propagar INSTALLS_ROOT al preload vía env var para que scanInstallations lo incluya
process.env.BAGO_INSTALLS_ROOT = INSTALLS_ROOT;
registerIpcHandlers({
  ipcMain,
  INSTALLS_ROOT,
  getDependencyService,
  getRuntimeService,
  getInstallService,
  getReleaseService,
  getAuditService
});

app.whenReady().then(async () => {
  // P0-05 fix: create the Manager window FIRST so the user always sees a
  // recovery/loading UI. The install/repair runs in parallel; its progress
  // is streamed to the renderer through `bago:install-state` events.
  // The window is the first thing the user sees; everything else (install,
  // release jobs) is wired up after the UI is on screen.
  createManagerWindow();
  getReleaseService().initReleaseJobs();
  getInstallService().ensureBagoInstalled().catch(err => {
    getInstallService().emitInstallState({ phase: 'failed', error: String(err && err.message || err) });
  });
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createManagerWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
