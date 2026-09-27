const crypto = require('node:crypto');

function createManagerSettingsClient({ apiBase, confirm, fetchImpl = fetch }) {
  if (typeof apiBase !== 'function' || typeof confirm !== 'function' || typeof fetchImpl !== 'function') {
    throw new TypeError('apiBase, confirm y fetchImpl son obligatorios');
  }

  async function write(operation) {
    const base = String(await apiBase() || '').replace(/\/$/, '');
    if (!base) throw new Error('BAGO API local no está activa');
    const resource = String(operation.resource || '').trim();
    const request = {
      resource,
      interaction_id: `manager-settings:${resource}:${crypto.randomUUID()}`,
      ...(resource === 'install_selection' ? { role: operation.role, install_dir: operation.install_dir } : {}),
      ...(resource === 'chain_registry' ? { chains: operation.chains } : {})
    };
    const post = async (fields, desktop = false) => {
      const response = await fetchImpl(`${base}/manager/settings/write`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(desktop ? { 'X-Bago-Channel': 'desktop' } : {}) },
        body: JSON.stringify({ ...request, ...fields })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) throw new Error(result.error || `Escritura de configuración rechazada (HTTP ${response.status})`);
      return result;
    };
    const challengeResult = await post({ authorization_action: 'challenge' });
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    const target = challenge && challenge.target;
    if (!challenge || !challenge.challenge_id || !target || target.resource !== resource || !target.path ||
        (resource === 'install_selection' && (target.role !== request.role || target.install_dir !== request.install_dir || !target.launcher_sha256)) ||
        (resource === 'chain_registry' && (!target.chains_sha256 || target.chain_count !== request.chains.length))) {
      throw new Error('ExecutionGateway no devolvió un challenge válido de configuración.');
    }
    if (!await confirm({ ...target })) return null;
    const approval = await post({ authorization_action: 'approve', challenge_id: challenge.challenge_id, user_decision: 'approve' }, true);
    const permit = approval.authorization && approval.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de configuración.');
    const result = await post({ authorization_action: 'execute', authorization_permit: permit.token });
    if (result.effect_id !== 'manager.settings.write' || !result.receipt_id || result.authorization?.state !== 'consumed') {
      throw new Error('ExecutionGateway no confirmó la escritura de configuración.');
    }
    return result;
  }

  return { write };
}

module.exports = { createManagerSettingsClient };
