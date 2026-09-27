const assert = require('node:assert/strict');
const { createSystemInstallClient } = require('../electron/system-install-client.cjs');

async function main() {
  const calls = [];
  const request = {
    action: 'release-job',
    source_root: 'C:/stage/job/source',
    helper_path: 'C:/stage/job/source/install-v4.ps1',
    install_dir: 'C:/Program Files/BAGO',
    package_sha256: 'a'.repeat(64),
    mode: 'Express',
    options: { no_path_update: true }
  };
  const target = {
    schema: 'bago.system-install-plan.v1',
    action: request.action,
    source_root: request.source_root,
    helper_path: request.helper_path,
    install_dir: request.install_dir,
    package_sha256: request.package_sha256,
    mode: request.mode,
    source_tree_sha256: 'b'.repeat(64),
    helper_sha256: 'c'.repeat(64),
    configuration_digest: 'd'.repeat(64),
    options: {
      skip_tests: false, no_path_update: true, no_shell_integration: false,
      preserve_dev_role: false, explorer_context_menu: false
    }
  };
  const responses = [
    { ok: true, authorization: { challenge: { challenge_id: 'challenge-1', target } } },
    { ok: true, authorization: { permit: { token: 'permit-1' } } },
    { ok: true, status: 'completed', effect_id: 'system.install.apply' }
  ];
  const client = createSystemInstallClient({
    apiBase: async () => 'http://127.0.0.1:43210/',
    confirm: async details => {
      calls.push({ kind: 'confirm', details });
      return true;
    },
    fetchImpl: async (url, options) => {
      calls.push({ kind: 'request', url, options, body: JSON.parse(options.body) });
      return { ok: true, status: 200, json: async () => responses.shift() };
    }
  });

  const execute = await client.prepare({ ...request, tag: 'v9.2.0' });
  assert.equal(typeof execute, 'function');
  assert.deepEqual(calls.map(call => call.kind), ['request', 'confirm', 'request']);
  assert.equal(calls[1].details.tag, 'v9.2.0');
  assert.equal(calls[1].details.packageSha256, request.package_sha256);
  assert.equal(calls[2].options.headers['X-Bago-Channel'], 'desktop');
  assert.equal(calls[0].body.configuration.providers.codex.api_key, '');
  assert.equal(calls[0].body.interaction_id, calls[2].body.interaction_id);
  const result = await execute();
  assert.equal(result.status, 'completed');
  assert.equal(calls[3].body.authorization_permit, 'permit-1');
  assert.equal(calls[2].body.operation_fingerprint, undefined);

  const repairCalls = [];
  const repairTarget = {
    ...target,
    action: 'repair',
    package_sha256: '',
    options: {
      skip_tests: false, no_path_update: false, no_shell_integration: false,
      preserve_dev_role: false, explorer_context_menu: false
    }
  };
  const repairResponses = [
    { ok: true, authorization: { challenge: { challenge_id: 'repair-challenge', target: repairTarget } } },
    { ok: true, authorization: { permit: { token: 'repair-permit' } } },
    { ok: true, status: 'completed', effect_id: 'system.install.apply' }
  ];
  const repairClient = createSystemInstallClient({
    apiBase: async () => 'http://127.0.0.1:43210/',
    confirm: async details => { repairCalls.push({ kind: 'confirm', details }); return true; },
    fetchImpl: async (url, options) => {
      repairCalls.push({ kind: 'request', url, body: JSON.parse(options.body) });
      return { ok: true, status: 200, json: async () => repairResponses.shift() };
    }
  });
  const executeRepair = await repairClient.prepare({
    action: 'repair', source_root: request.source_root,
    helper_path: request.helper_path, install_dir: request.install_dir,
    package_sha256: '', mode: 'Express'
  });
  assert.equal(repairCalls[0].body.action, 'repair');
  assert.equal(repairCalls[0].body.options.no_path_update, false);
  assert.equal(repairCalls[1].details.action, 'repair');
  assert.equal((await executeRepair()).effect_id, 'system.install.apply');

  let approved = false;
  const cancelClient = createSystemInstallClient({
    apiBase: async () => 'http://127.0.0.1:43210',
    confirm: async () => false,
    fetchImpl: async (_url, options) => {
      const body = JSON.parse(options.body);
      if (body.authorization_action === 'approve') approved = true;
      return {
        ok: true,
        status: 200,
        json: async () => ({ ok: true, authorization: { challenge: { challenge_id: 'challenge-2', target } } })
      };
    }
  });
  assert.equal(await cancelClient.prepare(request), null);
  assert.equal(approved, false);

  const rollbackCalls = [];
  const rollbackResponses = [
    { ok: true, authorization: { challenge: {
      challenge_id: 'rollback-challenge', effect_id: 'system.install.rollback',
      target: {
        install_dir: 'C:/Program Files/BAGO',
        backup_path: 'C:/Program Files/BAGO.bago-rollback-permit-123',
        displaced_path: 'C:/Program Files/BAGO.bago-replaced-job-1'
      }
    } } },
    { ok: true, authorization: { permit: { token: 'rollback-permit' } } },
    { ok: true, status: 'completed', effect_id: 'system.install.rollback' }
  ];
  const rollbackClient = createSystemInstallClient({
    apiBase: async () => 'http://127.0.0.1:43210',
    confirm: async details => {
      rollbackCalls.push({ kind: 'confirm', details });
      return true;
    },
    fetchImpl: async (url, options) => {
      rollbackCalls.push({ kind: 'request', url, body: JSON.parse(options.body), headers: options.headers });
      return { ok: true, status: 200, json: async () => rollbackResponses.shift() };
    }
  });
  const rollbackResult = await rollbackClient.rollback({
    install_dir: 'C:/Program Files/BAGO',
    backup_path: 'C:/Program Files/BAGO.bago-rollback-permit-123',
    displaced_path: 'C:/Program Files/BAGO.bago-replaced-job-1',
    tag: 'v9.2.0'
  });
  assert.equal(rollbackResult.effect_id, 'system.install.rollback');
  assert.deepEqual(rollbackCalls.map(call => call.kind), ['request', 'confirm', 'request', 'request']);
  assert.ok(rollbackCalls.every(call => call.kind !== 'request' || call.url.endsWith('/install/rollback')));
  assert.equal(rollbackCalls[1].details.type, 'rollback');
  assert.equal(rollbackCalls[2].headers['X-Bago-Channel'], 'desktop');
  assert.equal(rollbackCalls[3].body.authorization_permit, 'rollback-permit');

  const sourceCalls = [];
  const sourceTarget = {
    source_root: 'C:/work/BAGO', branch: 'main', expected_head: 'e'.repeat(40),
    origin_url: 'https://github.com/example/BAGO.git', origin_sha256: 'f'.repeat(64)
  };
  const sourceResponses = [
    { ok: true, authorization: { challenge: {
      challenge_id: 'source-challenge', effect_id: 'system.source.update', target: sourceTarget
    } } },
    { ok: true, authorization: { permit: { token: 'source-permit' } } },
    { ok: true, effect_id: 'system.source.update', head: 'e'.repeat(40) }
  ];
  const sourceClient = createSystemInstallClient({
    apiBase: async () => 'http://127.0.0.1:43210',
    confirm: async details => { sourceCalls.push({ kind: 'confirm', details }); return true; },
    fetchImpl: async (url, options) => {
      sourceCalls.push({ kind: 'request', url, body: JSON.parse(options.body), headers: options.headers });
      return { ok: true, status: 200, json: async () => sourceResponses.shift() };
    }
  });
  const sourceResult = await sourceClient.prepareSourceUpdate({ source_root: sourceTarget.source_root, branch: 'main' });
  assert.equal(sourceResult.effect_id, 'system.source.update');
  assert.deepEqual(sourceCalls.map(call => call.kind), ['request', 'confirm', 'request', 'request']);
  assert.equal(sourceCalls[0].url, 'http://127.0.0.1:43210/install/source-update');
  assert.equal(sourceCalls[1].details.expectedHead, sourceTarget.expected_head);
  assert.equal(sourceCalls[2].headers['X-Bago-Channel'], 'desktop');
  assert.equal(sourceCalls[3].body.authorization_permit, 'source-permit');

  const uninstallCalls = [];
  const uninstallTarget = {
    install_dir: 'C:/Program Files/BAGO',
    backup_root: 'C:/ProgramData/BAGO/backups',
    user_state_dir: 'C:/ProgramData/BAGO/user',
    purge_state: true,
    tree_sha256: '1'.repeat(64),
    cli_sha256: '3'.repeat(64)
  };
  const uninstallResponses = [
    { ok: true, authorization: { challenge: {
      challenge_id: 'uninstall-challenge', effect_id: 'system.install.uninstall', target: uninstallTarget
    } } },
    { ok: true, authorization: { permit: { token: 'uninstall-permit' } } },
    { ok: true, effect_id: 'system.install.uninstall', receipt_id: 'uninstall-receipt' }
  ];
  const uninstallClient = createSystemInstallClient({
    apiBase: async () => 'http://127.0.0.1:43210',
    confirm: async details => { uninstallCalls.push({ kind: 'confirm', details }); return true; },
    fetchImpl: async (url, options) => {
      uninstallCalls.push({ kind: 'request', url, body: JSON.parse(options.body), headers: options.headers });
      return { ok: true, status: 200, json: async () => uninstallResponses.shift() };
    }
  });
  const uninstallResult = await uninstallClient.prepareUninstall({
    install_dir: uninstallTarget.install_dir, purge_state: true
  });
  assert.equal(uninstallResult.receipt_id, 'uninstall-receipt');
  assert.deepEqual(uninstallCalls.map(call => call.kind), ['request', 'confirm', 'request', 'request']);
  assert.equal(uninstallCalls[0].url, 'http://127.0.0.1:43210/install/uninstall');
  assert.equal(uninstallCalls[1].details.purgeState, true);
  assert.equal(uninstallCalls[2].headers['X-Bago-Channel'], 'desktop');
  assert.equal(uninstallCalls[3].body.authorization_permit, 'uninstall-permit');

  const credentialCalls = [];
  const credentialResponses = [
    { ok: true, authorization: { challenge: { challenge_id: 'credential-challenge', target: {
      resource: 'provider_credential', operation: 'set', provider: 'codex', key: 'api_key', configuration_digest: 'a'.repeat(64)
    } } } },
    { ok: true, authorization: { permit: { token: 'credential-permit' } } },
    { ok: true, credential_receipt: { effect_id: 'credential.write' }, authorization: { state: 'consumed' } }
  ];
  const credentialClient = createSystemInstallClient({
    apiBase: async () => 'http://127.0.0.1:43210',
    confirm: async details => { credentialCalls.push({ kind: 'confirm', details }); return true; },
    fetchImpl: async (url, options) => {
      credentialCalls.push({ kind: 'request', url, body: JSON.parse(options.body), headers: options.headers });
      return { ok: true, status: 200, json: async () => credentialResponses.shift() };
    }
  });
  const credentialResult = await credentialClient.prepareProviderCredential({ provider: 'codex', value: 'secret' });
  assert.equal(credentialResult.effect_id, 'credential.write');
  assert.equal(credentialCalls[0].url, 'http://127.0.0.1:43210/providers/configure');
  assert.equal(credentialCalls[1].details.type, 'credential');
  assert.equal(credentialCalls[2].headers['X-Bago-Channel'], 'desktop');
  assert.equal(credentialCalls[3].body.authorization_permit, 'credential-permit');
  process.stdout.write(JSON.stringify({ ok: true, phases: calls.length, cancel_blocks_approval: true, source_update_requires_desktop_approval: true, uninstall_requires_desktop_approval: true, credential_write_requires_desktop_approval: true }) + '\n');
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
