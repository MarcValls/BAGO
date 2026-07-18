function registerIpcHandlers({
  ipcMain,
  dialog,
  INSTALLS_ROOT,
  getDependencyService,
  getRuntimeService,
  getInstallService,
  getReleaseService,
  getAuditService
}) {
  if (!ipcMain) {
    throw new Error('ipcMain es obligatorio');
  }

  const handle = (channel, handler) => ipcMain.handle(channel, handler);

  handle('bago:supervisor-cmd', (_event, args) => getRuntimeService().runSupervisorCmd(args));
  handle('bago:zombie-cleanup', () => getRuntimeService().cleanupZombies());
  handle('bago:install-state-get', () => getInstallService().getInstallState());
  handle('bago:open-web-chat', (_event, options) => getRuntimeService().openWebChat(options || {}));
  handle('bago:open-cli-chat', (_event, options) => getRuntimeService().openCliChat(options || {}));
  handle('bago:web-chat-status', () => getRuntimeService().webChatStatus());
  handle('bago:shutdown', () => getRuntimeService().shutdown());
  handle('bago:manager-health', () => getDependencyService().managerHealth());
  handle('bago:dependency-catalog', () => getDependencyService().dependencyCatalog());
  handle('bago:dependency-action', async (_event, payload) => getDependencyService().runDependencyAction(payload || {}));
  handle('bago:install-preflight', (_event, payload) => getDependencyService().runInstallPreflight(payload && payload.targetDir));
  handle('bago:get-installs-root', () => INSTALLS_ROOT);
  handle('bago:fetch-releases', () => getReleaseService().fetchReleases());
  handle('bago:manager-url', () => getRuntimeService().getManagerUrl());
  handle('bago:workspace-choose-root', async (_event, options) => getRuntimeService().chooseWorkspaceRoot(options || {}));
  handle('bago:workspace-link-root', (_event, root) => getRuntimeService().linkProjectRoot(root));
  handle('bago:get-chat-url', async (_event, options) => {
    const state = await getRuntimeService().ensureWebChatServer(options || {});
    return state.url;
  });
  handle('bago:install-action', async (_event, payload) => getInstallService().performInstallAction(payload || {}));
  handle('bago:session-cmd', (_event, args) => getRuntimeService().runBagoSession(args));
  handle('bago:release-jobs-list', () => getReleaseService().requireReleaseJobs().listJobs());
  handle('bago:release-job-preflight', (_event, payload) => getReleaseService().requireReleaseJobs().preflight(payload || {}));
  handle('bago:release-job-start', (_event, payload) => getReleaseService().requireReleaseJobs().startPrepare(payload || {}));
  handle('bago:release-job-cancel', (_event, id) => getReleaseService().requireReleaseJobs().cancel(id));
  handle('bago:release-job-resume', (_event, id) => getReleaseService().requireReleaseJobs().resume(id));
  handle('bago:release-job-install', (_event, id) => getReleaseService().requireReleaseJobs().install(id));
  handle('bago:release-job-rollback', (_event, id) => getReleaseService().requireReleaseJobs().rollback(id));
  handle('bago:release-job-logs', (_event, id, limit) => getReleaseService().requireReleaseJobs().getLogs(id, limit));
  handle('bago:release-job-delete', (_event, id) => getReleaseService().requireReleaseJobs().deleteJob(id));
  handle('bago:project-audit', () => getAuditService().projectAudit());
  handle('bago:bago-audit', () => getAuditService().bagoAudit());
  handle('bago:event-ledger', (_event, limit) => getAuditService().eventLedger(limit));
  handle('bago:node-cmd', async (_event, args) => {
    const result = await getRuntimeService().runBagoNode(args);
    const wantsJson = Array.isArray(args) && args.includes('--json');
    if (wantsJson || String(result.stdout || '').trim().startsWith('{')) {
      try {
        const parsed = JSON.parse(result.stdout);
        return { ok: true, data: parsed, raw: result.stdout, cmd: result.cmd, cwd: result.cwd };
      } catch (e) {
        return { ok: false, error: `JSON parse falló: ${e.message}`, raw: result.stdout, cmd: result.cmd };
      }
    }
    return { ok: true, text: result.stdout, cmd: result.cmd, cwd: result.cwd };
  });
}

module.exports = {
  registerIpcHandlers
};
