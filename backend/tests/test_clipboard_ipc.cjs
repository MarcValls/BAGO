const assert = require('assert');
const { registerIpcHandlers } = require('../electron/ipc-service.cjs');

async function main() {
  const handlers = new Map();
  const ipcMain = { handle: (channel, handler) => handlers.set(channel, handler) };
  const writes = [];
  const image = {
    isEmpty: () => false,
    toPNG: () => Buffer.from('png'),
    toDataURL: () => 'data:image/png;base64,cG5n'
  };
  const clipboard = {
    readText: () => 'texto copiado',
    readImage: () => image,
    writeText: (value) => writes.push(value)
  };
  const noop = () => ({ ok: true });
  registerIpcHandlers({
    ipcMain,
    clipboard,
    dialog: {},
    INSTALLS_ROOT: '',
    getDependencyService: () => ({ managerHealth: noop, dependencyCatalog: noop, runDependencyAction: noop, runInstallPreflight: noop }),
    getRuntimeService: () => ({ runSupervisorCmd: noop, cleanupZombies: noop, openWebChat: noop, openCliChat: noop, webChatStatus: noop, shutdown: noop, getManagerUrl: noop, chooseWorkspaceRoot: noop, linkProjectRoot: noop, ensureWebChatServer: noop, runBagoSession: noop, runBagoNode: noop, getState: noop }),
    getInstallService: () => ({ getInstallState: noop, performInstallAction: noop }),
    getReleaseService: () => ({ fetchReleases: noop, requireReleaseJobs: () => ({ listJobs: noop, preflight: noop, startPrepare: noop, cancel: noop, resume: noop, install: noop, rollback: noop, getLogs: noop, deleteJob: noop }) }),
    getAuditService: () => ({ projectAudit: noop, bagoAudit: noop, eventLedger: noop })
  });

  assert.deepStrictEqual([...handlers.keys()].filter((channel) => channel.includes('clipboard')), [
    'bago:clipboard-read-text',
    'bago:clipboard-read-payload',
    'bago:clipboard-write-text'
  ]);
  assert.strictEqual(await handlers.get('bago:clipboard-read-text')(), 'texto copiado');
  assert.deepStrictEqual(await handlers.get('bago:clipboard-read-payload')(), {
    text: 'texto copiado',
    imageDataUrl: 'data:image/png;base64,cG5n',
    imageMimeType: 'image/png',
    imageBytes: 3,
    error: ''
  });
  await handlers.get('bago:clipboard-write-text')({}, 42);
  assert.deepStrictEqual(writes, ['42']);
  console.log(JSON.stringify({ ok: true, channels: 3, payload: 'text-image', coercion: 'string' }));
}

main().catch((error) => {
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
