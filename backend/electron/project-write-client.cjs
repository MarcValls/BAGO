const crypto = require('node:crypto');

function createProjectWriteClient({ apiBase, confirm, fetchImpl = fetch }) {
  if (typeof apiBase !== 'function' || typeof confirm !== 'function' || typeof fetchImpl !== 'function') {
    throw new TypeError('apiBase, confirm y fetchImpl son obligatorios');
  }

  async function link(root) {
    const cleanRoot = String(root || '').trim();
    if (!cleanRoot) throw new Error('Ruta de workspace vacía');
    const base = String(await apiBase() || '').replace(/\/$/, '');
    if (!base) throw new Error('BAGO API local no está activa');
    const interactionId = `project-write:link:${crypto.randomUUID()}`;

    const post = async (fields, desktop = false) => {
      const response = await fetchImpl(`${base}/project/link`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(desktop ? { 'X-Bago-Channel': 'desktop' } : {})
        },
        body: JSON.stringify({ root: cleanRoot, interaction_id: interactionId, ...fields })
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.ok) {
        throw new Error(result.error || `Vinculación de proyecto rechazada (HTTP ${response.status})`);
      }
      return result;
    };

    const challengeResult = await post({ authorization_action: 'challenge' });
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    const target = challenge && challenge.target;
    if (!challenge || !challenge.challenge_id || !target ||
        target.resource !== 'project_operation' || target.operation !== 'link' ||
        !target.path || !target.allowed_root || !target.root_digest) {
      throw new Error('ExecutionGateway no devolvió un challenge válido para vincular el proyecto.');
    }
    if (!await confirm({ ...target, requested_root: cleanRoot })) return null;

    const approvalResult = await post({
      authorization_action: 'approve',
      challenge_id: challenge.challenge_id,
      user_decision: 'approve'
    }, true);
    const permit = approvalResult.authorization && approvalResult.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de proyecto.');

    const result = await post({
      authorization_action: 'execute',
      authorization_permit: permit.token
    });
    if (result.receipt?.effect_id !== 'project.write' ||
        result.receipt?.operation !== 'link' ||
        result.authorization?.state !== 'consumed') {
      throw new Error('ExecutionGateway no confirmó el vínculo del proyecto.');
    }
    return result;
  }

  return { link };
}

module.exports = { createProjectWriteClient };
