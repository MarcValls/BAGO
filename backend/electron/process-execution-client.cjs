const crypto = require('node:crypto');

function createProcessExecutionClient({ apiBase, confirm, fetchImpl = fetch }) {
  if (typeof apiBase !== 'function' || typeof confirm !== 'function' || typeof fetchImpl !== 'function') {
    throw new TypeError('apiBase, confirm y fetchImpl son obligatorios');
  }

  async function execute(operation, argv) {
    const cleanOperation = String(operation || '').trim();
    const cleanArgv = Array.isArray(argv) ? argv.map(value => String(value ?? '')) : [];
    if (!['launcher', 'session_control', 'supervisor', 'cleanup_zombies', 'stop_webchat', 'github_cli', 'git_identity'].includes(cleanOperation)) throw new Error('Operación de proceso no permitida');
    const base = String(await apiBase() || '').replace(/\/$/, '');
    if (!base) throw new Error('BAGO API local no está activa');
    const interactionId = `process-execute:${cleanOperation}:${crypto.randomUUID()}`;

    const post = async (fields, desktop = false) => {
      const response = await fetchImpl(`${base}/process/execute`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(desktop ? { 'X-Bago-Channel': 'desktop' } : {})
        },
        body: JSON.stringify({ operation: cleanOperation, argv: cleanArgv, interaction_id: interactionId, ...fields })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || `Ejecución de proceso rechazada (HTTP ${response.status})`);
      return result;
    };

    const challengeResult = await post({ authorization_action: 'challenge' });
    if (challengeResult.read_only === true && challengeResult.authorization?.state === 'server_policy') {
      const processResult = challengeResult.process_result;
      if (processResult?.effect_id !== 'process.inspect' || processResult.executed !== true) {
        throw new Error('ExecutionGateway no confirmó la inspección de proceso.');
      }
      return { ...processResult, authorization: challengeResult.authorization, read_only: true };
    }
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    const target = challenge && challenge.target;
    const expectedModule = cleanOperation === 'launcher' ? 'bago_core.launcher' : 'bago_core.session_control';
    const identityMatches = cleanOperation === 'stop_webchat'
      ? target?.operation === 'stop_webchat' && Number.isInteger(target?.process_id) && target.process_id > 0 && Number.isInteger(target?.port) && target.port > 0 && target?.python_root
      : cleanOperation === 'cleanup_zombies'
      ? target?.operation === 'cleanup_zombies' && Array.isArray(target?.cleanup_roots) && target.cleanup_roots.length > 0
      : cleanOperation === 'supervisor'
      ? target?.python_script === 'scripts/bago_supervisor.py'
      : ['github_cli', 'git_identity'].includes(cleanOperation)
      ? target?.executable === (cleanOperation === 'github_cli' ? 'gh' : 'git')
      : target?.python_module === expectedModule;
    if (!challenge || !challenge.challenge_id || !identityMatches || !target.cwd) {
      throw new Error('ExecutionGateway no devolvió un challenge válido de proceso.');
    }
    const displayArgv = cleanOperation === 'github_cli' && cleanArgv.includes('--token')
      ? cleanArgv.map((value, index) => index > cleanArgv.indexOf('--token') ? '[oculto]' : value)
      : cleanArgv;
    if (!await confirm({ operation: cleanOperation, argv: displayArgv, ...target, sessionId: challenge.session_id })) {
      return { ok: false, canceled: true };
    }

    const approvalResult = await post({
      authorization_action: 'approve', challenge_id: challenge.challenge_id, user_decision: 'approve'
    }, true);
    const permit = approvalResult.authorization && approvalResult.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de proceso.');

    const result = await post({ authorization_action: 'execute', authorization_permit: permit.token });
    const processResult = result.process_result;
    const expectedEffect = ['cleanup_zombies', 'stop_webchat'].includes(cleanOperation) ? 'process.terminate' : 'process.execute';
    if (processResult?.effect_id !== expectedEffect || result.authorization?.state !== 'consumed' || processResult.executed !== true) {
      throw new Error('ExecutionGateway no confirmó la ejecución del proceso.');
    }
    if (cleanOperation === 'stop_webchat' && processResult.termination_scheduled !== true) {
      throw new Error('ExecutionGateway no confirmó la programación de cierre del servidor.');
    }
    return { ...processResult, authorization: result.authorization };
  }

  return { execute };
}

module.exports = { createProcessExecutionClient };
