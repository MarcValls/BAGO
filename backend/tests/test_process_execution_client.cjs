const assert = require('node:assert/strict');
const { createProcessExecutionClient } = require('../electron/process-execution-client.cjs');

function reply(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body };
}

async function approvedFlow() {
  const calls = [];
  let confirmed = null;
  const client = createProcessExecutionClient({
    apiBase: async () => 'http://127.0.0.1:8091/',
    confirm: async operation => { confirmed = operation; return true; },
    fetchImpl: async (url, options) => {
      const body = JSON.parse(options.body);
      calls.push({ url, options, body });
      if (body.authorization_action === 'challenge') return reply(200, { ok: true, authorization: { challenge: {
        challenge_id: 'challenge-1', session_id: 'session-1', target: {
          python_module: 'bago_core.launcher', python_root: 'C:/BAGO/backend',
          python_module_sha256: 'a'.repeat(64), cwd: 'C:/workspace', timeout_seconds: 300
        }
      } } });
      if (body.authorization_action === 'approve') return reply(200, { ok: true, authorization: { permit: { token: 'permit-1' } } });
      return reply(200, { ok: true, process_result: { ok: true, executed: true, effect_id: 'process.execute', exit_code: 0, stdout: 'done', stderr: '', cwd: 'C:/workspace', executable: 'python', python_module: 'bago_core.launcher' }, authorization: { state: 'consumed' } });
    }
  });
  const result = await client.execute('launcher', ['node', 'status', '--json']);
  assert.equal(confirmed.python_module, 'bago_core.launcher');
  assert.equal(confirmed.sessionId, 'session-1');
  assert.deepEqual(confirmed.argv, ['node', 'status', '--json']);
  assert.equal(result.stdout, 'done');
  assert.equal(result.authorization.state, 'consumed');
  assert.equal(calls.length, 3);
  assert.equal(calls[0].options.headers['X-Bago-Channel'], undefined);
  assert.equal(calls[1].options.headers['X-Bago-Channel'], 'desktop');
  assert.equal(calls[2].body.authorization_permit, 'permit-1');
}

async function cancellationStopsBeforeApproval() {
  const calls = [];
  const client = createProcessExecutionClient({
    apiBase: async () => 'http://127.0.0.1:8091',
    confirm: async () => false,
    fetchImpl: async (_url, options) => {
      calls.push(JSON.parse(options.body));
      return reply(200, { ok: true, authorization: { challenge: {
        challenge_id: 'challenge-2', session_id: 'session-1', target: {
          python_module: 'bago_core.session_control', cwd: 'C:/workspace', timeout_seconds: 180
        }
      } } });
    }
  });
  const result = await client.execute('session_control', ['status', '--session-id', 'session-1']);
  assert.equal(result.canceled, true);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].authorization_action, 'challenge');
}

async function readonlyInspectionUsesServerPolicyWithoutDesktopModal() {
  let confirmed = false;
  const client = createProcessExecutionClient({
    apiBase: async () => 'http://127.0.0.1:8091',
    confirm: async () => { confirmed = true; return true; },
    fetchImpl: async () => reply(200, {
      ok: true,
      read_only: true,
      authorization: { state: 'server_policy', proof_id: 'proof-1' },
      process_result: { effect_id: 'process.inspect', executed: true, exit_code: 0, stdout: '{}', stderr: '' }
    })
  });
  const result = await client.execute('launcher', ['node', 'status', '--json']);
  assert.equal(result.read_only, true);
  assert.equal(result.effect_id, 'process.inspect');
  assert.equal(confirmed, false);
}

async function supervisorChallengeBindsTrustedScriptBeforeDesktopApproval() {
  const calls = [];
  let confirmed = null;
  const client = createProcessExecutionClient({
    apiBase: async () => 'http://127.0.0.1:8091',
    confirm: async operation => { confirmed = operation; return true; },
    fetchImpl: async (_url, options) => {
      const body = JSON.parse(options.body);
      calls.push(body);
      if (body.authorization_action === 'challenge') return reply(200, { ok: true, authorization: { challenge: {
        challenge_id: 'supervisor-challenge', session_id: 'session-1', target: {
          python_script: 'scripts/bago_supervisor.py', python_root: 'C:/BAGO/backend',
          python_module_sha256: 'b'.repeat(64), cwd: 'C:/workspace', timeout_seconds: 15
        }
      } } });
      if (body.authorization_action === 'approve') return reply(200, { ok: true, authorization: { permit: { token: 'supervisor-permit' } } });
      return reply(200, { ok: true, process_result: { executed: true, effect_id: 'process.execute', exit_code: 0, stdout: '{}', stderr: '' }, authorization: { state: 'consumed' } });
    }
  });
  const result = await client.execute('supervisor', ['status', '--json']);
  assert.equal(confirmed.python_script, 'scripts/bago_supervisor.py');
  assert.equal(confirmed.sessionId, 'session-1');
  assert.equal(result.authorization.state, 'consumed');
  assert.equal(calls.length, 3);
  assert.equal(calls[1].challenge_id, 'supervisor-challenge');
  assert.equal(calls[2].authorization_permit, 'supervisor-permit');
}

async function zombieCleanupRequiresGatewayPermitBoundToTrustedRoots() {
  const calls = [];
  let confirmed = null;
  const roots = ['C:/BAGO/backend', 'C:/Users/user/.bago'];
  const client = createProcessExecutionClient({
    apiBase: async () => 'http://127.0.0.1:8091',
    confirm: async operation => { confirmed = operation; return true; },
    fetchImpl: async (_url, options) => {
      const body = JSON.parse(options.body);
      calls.push(body);
      if (body.authorization_action === 'challenge') return reply(200, { ok: true, authorization: { challenge: {
        challenge_id: 'cleanup-challenge', session_id: 'session-1', target: {
          operation: 'cleanup_zombies', cleanup_roots: roots, cwd: 'C:/workspace', timeout_seconds: 20
        }
      } } });
      if (body.authorization_action === 'approve') return reply(200, { ok: true, authorization: { permit: { token: 'cleanup-permit' } } });
      return reply(200, { ok: true, process_result: { executed: true, effect_id: 'process.terminate', exit_code: 0, cleaned: 1 }, authorization: { state: 'consumed' } });
    }
  });
  const result = await client.execute('cleanup_zombies', []);
  assert.deepEqual(confirmed.cleanup_roots, roots);
  assert.equal(result.effect_id, 'process.terminate');
  assert.equal(result.authorization.state, 'consumed');
  assert.equal(calls.length, 3);
  assert.equal(calls[1].challenge_id, 'cleanup-challenge');
  assert.equal(calls[2].authorization_permit, 'cleanup-permit');
}

async function webchatShutdownRequiresPermitForExactServerPidAndPort() {
  const calls = [];
  let confirmed = null;
  const client = createProcessExecutionClient({
    apiBase: async () => 'http://127.0.0.1:8091',
    confirm: async operation => { confirmed = operation; return true; },
    fetchImpl: async (_url, options) => {
      const body = JSON.parse(options.body);
      calls.push(body);
      if (body.authorization_action === 'challenge') return reply(200, { ok: true, authorization: { challenge: {
        challenge_id: 'stop-challenge', session_id: 'session-1', target: {
          operation: 'stop_webchat', process_id: 1234, port: 8097,
          python_root: 'C:/BAGO/backend', cwd: 'C:/workspace', timeout_seconds: 20
        }
      } } });
      if (body.authorization_action === 'approve') return reply(200, { ok: true, authorization: { permit: { token: 'stop-permit' } } });
      return reply(200, { ok: true, process_result: { executed: true, termination_scheduled: true, effect_id: 'process.terminate' }, authorization: { state: 'consumed' } });
    }
  });
  const result = await client.execute('stop_webchat', []);
  assert.equal(confirmed.process_id, 1234);
  assert.equal(confirmed.port, 8097);
  assert.equal(result.termination_scheduled, true);
  assert.equal(result.authorization.state, 'consumed');
  assert.equal(calls.length, 3);
}

async function githubMutationUsesExactDesktopPermitAndRedactsTokenInPrompt() {
  const calls = [];
  let confirmed = null;
  const client = createProcessExecutionClient({
    apiBase: async () => 'http://127.0.0.1:8091',
    confirm: async operation => { confirmed = operation; return true; },
    fetchImpl: async (_url, options) => {
      const body = JSON.parse(options.body);
      calls.push(body);
      if (body.authorization_action === 'challenge') return reply(200, { ok: true, authorization: { challenge: {
        challenge_id: 'github-challenge', session_id: 'session-1', target: {
          executable: 'gh', operation: 'gh', cwd: 'C:/workspace', timeout_seconds: 120
        }
      } } });
      if (body.authorization_action === 'approve') return reply(200, { ok: true, authorization: { permit: { token: 'github-permit' } } });
      return reply(200, { ok: true, process_result: { executed: true, effect_id: 'process.execute', exit_code: 0, stdout: '', stderr: '' }, authorization: { state: 'consumed' } });
    }
  });
  const secretArgs = ['auth', 'login', '--hostname', 'github.com', '--token', 'ghp-secret-value'];
  const result = await client.execute('github_cli', secretArgs);
  assert.equal(result.authorization.state, 'consumed');
  assert.equal(confirmed.executable, 'gh');
  assert.deepEqual(confirmed.argv, ['auth', 'login', '--hostname', 'github.com', '--token', '[oculto]']);
  assert.deepEqual(calls[0].argv, secretArgs);
  assert.equal(calls[1].authorization_action, 'approve');
  assert.equal(calls[2].authorization_permit, 'github-permit');
}

Promise.resolve().then(approvedFlow).then(cancellationStopsBeforeApproval).then(readonlyInspectionUsesServerPolicyWithoutDesktopModal).then(supervisorChallengeBindsTrustedScriptBeforeDesktopApproval).then(zombieCleanupRequiresGatewayPermitBoundToTrustedRoots).then(webchatShutdownRequiresPermitForExactServerPidAndPort).then(githubMutationUsesExactDesktopPermitAndRedactsTokenInPrompt).then(() => {
  process.stdout.write('PASS process execution client challenge/confirm/permit/execute\n');
}).catch(error => {
  process.stderr.write(`${error.stack || error}\n`);
  process.exitCode = 1;
});
