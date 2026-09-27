const assert = require('node:assert/strict');
const { createManagerSettingsClient } = require('../electron/manager-settings-client.cjs');

async function main() {
  const calls = [];
  const responses = [
    { ok: true, authorization: { challenge: { challenge_id: 'settings-challenge', target: {
      resource: 'install_selection', path: 'C:/Users/test/BAGO/install_selection.json', role: 'active',
      install_dir: 'C:/Program Files/BAGO', launcher_sha256: 'a'.repeat(64)
    } } } },
    { ok: true, authorization: { permit: { token: 'settings-permit' } } },
    { ok: true, effect_id: 'manager.settings.write', receipt_id: 'settings-receipt', authorization: { state: 'consumed' } }
  ];
  const client = createManagerSettingsClient({
    apiBase: async () => 'http://127.0.0.1:43210/',
    confirm: async target => { calls.push({ kind: 'confirm', target }); return true; },
    fetchImpl: async (url, options) => {
      calls.push({ kind: 'request', url, body: JSON.parse(options.body), headers: options.headers });
      return { ok: true, status: 200, json: async () => responses.shift() };
    }
  });
  const result = await client.write({ resource: 'install_selection', role: 'active', install_dir: 'C:/Program Files/BAGO' });
  assert.equal(result.receipt_id, 'settings-receipt');
  assert.deepEqual(calls.map(call => call.kind), ['request', 'confirm', 'request', 'request']);
  assert.equal(calls[0].url, 'http://127.0.0.1:43210/manager/settings/write');
  assert.equal(calls[2].headers['X-Bago-Channel'], 'desktop');
  assert.equal(calls[3].body.authorization_permit, 'settings-permit');
  process.stdout.write(JSON.stringify({ ok: true, manager_settings_desktop_permit: true }) + '\n');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
