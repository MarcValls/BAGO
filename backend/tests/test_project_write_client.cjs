const assert = require('node:assert/strict');
const { createProjectWriteClient } = require('../electron/project-write-client.cjs');

const target = {
  path: 'C:/work/project/.bago/link.json',
  allowed_root: 'C:/work/project',
  resource: 'project_operation',
  operation: 'link',
  root_digest: 'a'.repeat(64)
};

async function main() {
  const calls = [];
  let confirmations = 0;
  const replies = [
    { ok: true, authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-1', target } } },
    { ok: true, authorization: { permit: { token: 'permit-1' } } },
    {
      ok: true,
      data: { root: 'C:/work/project' },
      receipt: { effect_id: 'project.write', operation: 'link' },
      authorization: { state: 'consumed' }
    }
  ];
  const client = createProjectWriteClient({
    apiBase: async () => 'http://127.0.0.1:8765/',
    confirm: async approved => {
      confirmations += 1;
      assert.equal(approved.operation, 'link');
      assert.equal(approved.requested_root, 'C:/work/project');
      return true;
    },
    fetchImpl: async (url, options) => {
      calls.push({ url, options, body: JSON.parse(options.body) });
      return { ok: true, status: 200, json: async () => replies.shift() };
    }
  });

  const result = await client.link('C:/work/project');
  assert.equal(result.receipt.effect_id, 'project.write');
  assert.equal(confirmations, 1);
  assert.equal(calls.length, 3);
  assert.ok(calls.every(call => call.url === 'http://127.0.0.1:8765/project/link'));
  assert.equal(calls[0].body.authorization_action, 'challenge');
  assert.equal(calls[1].body.authorization_action, 'approve');
  assert.equal(calls[1].body.user_decision, 'approve');
  assert.equal(calls[1].options.headers['X-Bago-Channel'], 'desktop');
  assert.equal(calls[2].body.authorization_action, 'execute');
  assert.equal(calls[0].body.root, 'C:/work/project');

  let cancelCalls = 0;
  const canceledClient = createProjectWriteClient({
    apiBase: async () => 'http://127.0.0.1:8765',
    confirm: async () => false,
    fetchImpl: async () => {
      cancelCalls += 1;
      return { ok: true, status: 200, json: async () => ({
        ok: true,
        authorization: { state: 'challenge', challenge: { challenge_id: 'challenge-2', target } }
      }) };
    }
  });
  assert.equal(await canceledClient.link('C:/work/project'), null);
  assert.equal(cancelCalls, 1);
}

main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
