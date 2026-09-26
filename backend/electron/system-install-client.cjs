const crypto = require('node:crypto');

function neutralInstallConfiguration() {
  return {
    providers: {
      'ollama-local': { enabled: false, base_url: 'http://127.0.0.1:11434', model: 'llama3.2:3b' },
      codex: { enabled: false, base_url: 'https://api.openai.com/v1', api_key: '', model: 'gpt-5.4-mini' },
      copilot: { enabled: false, base_url: 'https://api.githubcopilot.com', api_key: '', auth_mode: 'device-flow', model: 'gpt-4o-copilot' },
      'ollama-cloud': { enabled: false, base_url: '', api_key: '', auth_mode: 'signin', model: 'llama3.2:3b' }
    },
    knowledge: { mode: 'none', path: '', visibility: 'private', git_init: false },
    credential_store: { mode: 'session', path: '', encrypted: false, scope: 'session' }
  };
}

function createSystemInstallClient({ apiBase, confirm, fetchImpl = fetch }) {
  if (typeof apiBase !== 'function' || typeof confirm !== 'function' || typeof fetchImpl !== 'function') {
    throw new TypeError('apiBase, confirm y fetchImpl son obligatorios');
  }

  async function post(base, payload, desktopApproval = false, route = 'apply') {
    const response = await fetchImpl(`${base}/install/${route}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(desktopApproval ? { 'X-Bago-Channel': 'desktop' } : {})
      },
      body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) {
      throw new Error(result.error || result.message || `Autorización de instalación rechazada (HTTP ${response.status})`);
    }
    return result;
  }

  async function postProviderCredential(base, payload, desktopApproval = false) {
    const response = await fetchImpl(`${base}/providers/configure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(desktopApproval ? { 'X-Bago-Channel': 'desktop' } : {}) },
      body: JSON.stringify(payload)
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.ok) throw new Error(result.error || `Autorización de credencial rechazada (HTTP ${response.status})`);
    return result;
  }

  async function prepareProviderCredential(operation) {
    const base = String(await apiBase() || '').replace(/\/$/, '');
    if (!base) throw new Error('BAGO API local no está activa');
    const provider = String(operation.provider || '').trim();
    const value = String(operation.value || '').trim();
    if (!provider || !value) throw new Error('Provider y credencial son obligatorios.');
    const request = { provider, api_key: value, interaction_id: `credential-write:${provider}:${crypto.randomUUID()}` };
    const challengeResult = await postProviderCredential(base, { ...request, authorization_action: 'challenge' });
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    const target = challenge && challenge.target;
    if (!challenge || !challenge.challenge_id || !target || target.resource !== 'provider_credential' ||
        target.operation !== 'set' || target.provider !== provider || target.key !== 'api_key' || !target.configuration_digest) {
      throw new Error('ExecutionGateway no devolvió un challenge de credencial válido.');
    }
    if (!await confirm({ type: 'credential', provider, configurationDigest: target.configuration_digest })) return null;
    const approval = await postProviderCredential(base, {
      ...request, authorization_action: 'approve', challenge_id: challenge.challenge_id, user_decision: 'approve'
    }, true);
    const permit = approval.authorization && approval.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de credencial.');
    const result = await postProviderCredential(base, {
      ...request, authorization_action: 'execute', authorization_permit: permit.token
    });
    if (!result.credential_receipt || result.credential_receipt.effect_id !== 'credential.write' ||
        result.authorization?.state !== 'consumed') throw new Error('ExecutionGateway no confirmó la escritura autorizada.');
    return result.credential_receipt;
  }

  async function prepare(operation) {
    const base = String(await apiBase() || '').replace(/\/$/, '');
    if (!base) throw new Error('BAGO API local no está activa');
    const action = String(operation.action || 'release-job').trim();
    const configuration = operation.configuration || neutralInstallConfiguration();
    const options = {
      skip_tests: false,
      no_path_update: action === 'release-job',
      no_shell_integration: false,
      preserve_dev_role: false,
      explorer_context_menu: false,
      ...(operation.options || {})
    };
    const interactionId = `system-install:${action}:${crypto.randomUUID()}`;
    const request = {
      action,
      source_root: operation.source_root,
      helper_path: operation.helper_path,
      install_dir: operation.install_dir,
      package_sha256: operation.package_sha256,
      mode: operation.mode || 'Express',
      options,
      configuration,
      interaction_id: interactionId
    };
    const challengeResult = await post(base, { ...request, authorization_action: 'challenge' });
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    if (!challenge || !challenge.challenge_id || !challenge.target) {
      throw new Error('ExecutionGateway no devolvió un challenge de instalación completo.');
    }
    const target = challenge.target;
    if (
      target.action !== request.action || target.source_root !== request.source_root ||
      target.helper_path !== request.helper_path || target.install_dir !== request.install_dir ||
      target.mode !== request.mode || target.package_sha256 !== request.package_sha256 ||
      !target.options || Object.keys(target.options).length !== Object.keys(request.options).length ||
      Object.keys(request.options).some(key => target.options[key] !== request.options[key]) ||
      !target.source_tree_sha256 || !target.helper_sha256 || !target.configuration_digest
    ) {
      throw new Error('El challenge no coincide con el release job preparado.');
    }
    const approved = await confirm({
      tag: String(operation.tag || ''),
      action,
      sourceRoot: target.source_root,
      helperPath: target.helper_path,
      installDir: target.install_dir,
      mode: target.mode,
      packageSha256: target.package_sha256,
      sourceTreeSha256: target.source_tree_sha256,
      helperSha256: target.helper_sha256,
      configurationDigest: target.configuration_digest
    });
    if (!approved) return null;

    const approval = await post(base, {
      ...request,
      authorization_action: 'approve',
      challenge_id: challenge.challenge_id,
      user_decision: 'approve'
    }, true);
    const permit = approval.authorization && approval.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de instalación.');

    return async () => {
      const result = await post(base, {
        ...request,
        authorization_action: 'execute',
        authorization_permit: permit.token
      });
      if (result.status !== 'completed') throw new Error(`El helper no confirmó la instalación: ${result.status || 'sin estado'}`);
      return result;
    };
  }

  async function rollback(operation) {
    const base = String(await apiBase() || '').replace(/\/$/, '');
    if (!base) throw new Error('BAGO API local no está activa');
    const request = {
      install_dir: operation.install_dir,
      backup_path: operation.backup_path || '',
      displaced_path: operation.displaced_path,
      interaction_id: `system-install-rollback:${crypto.randomUUID()}`
    };
    const challengeResult = await post(base, { ...request, authorization_action: 'challenge' }, false, 'rollback');
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    if (!challenge || !challenge.challenge_id || !challenge.target) throw new Error('ExecutionGateway no devolvió un challenge de rollback completo.');
    if (challenge.effect_id !== 'system.install.rollback' ||
        challenge.target.install_dir !== request.install_dir ||
        challenge.target.backup_path !== request.backup_path ||
        challenge.target.displaced_path !== request.displaced_path) {
      throw new Error('El challenge de rollback no coincide con el destino y los datos recuperables.');
    }
    const approved = await confirm({
      type: 'rollback',
      tag: String(operation.tag || ''),
      installDir: request.install_dir,
      backupPath: request.backup_path,
      displacedPath: request.displaced_path,
      automatic: !!operation.automatic
    });
    if (!approved) return null;
    const approval = await post(base, {
      ...request,
      authorization_action: 'approve',
      challenge_id: challenge.challenge_id,
      user_decision: 'approve'
    }, true, 'rollback');
    const permit = approval.authorization && approval.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de rollback.');
    const result = await post(base, {
      ...request,
      authorization_action: 'execute',
      authorization_permit: permit.token
    }, false, 'rollback');
    if (result.status !== 'completed' || result.effect_id !== 'system.install.rollback') {
      throw new Error('ExecutionGateway no confirmó el rollback.');
    }
    return result;
  }

  async function prepareSourceUpdate(operation) {
    const base = String(await apiBase() || '').replace(/\/$/, '');
    if (!base) throw new Error('BAGO API local no está activa');
    const request = {
      source_root: operation.source_root,
      branch: operation.branch || 'main',
      interaction_id: `system-source-update:${crypto.randomUUID()}`
    };
    const postSource = (payload, desktopApproval = false) => post(base, payload, desktopApproval, 'source-update');
    const challengeResult = await postSource({ ...request, authorization_action: 'challenge' });
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    const target = challenge && challenge.target;
    if (!challenge || !challenge.challenge_id || !target || challenge.effect_id !== 'system.source.update' ||
        target.source_root !== request.source_root || target.branch !== request.branch ||
        !target.expected_head || !target.origin_sha256 || !target.origin_url) {
      throw new Error('El challenge de actualización de fuente no coincide con el checkout.');
    }
    const approved = await confirm({
      type: 'source-update', sourceRoot: target.source_root, branch: target.branch,
      expectedHead: target.expected_head, originUrl: target.origin_url,
      originSha256: target.origin_sha256
    });
    if (!approved) return null;
    const approval = await postSource({
      ...request, authorization_action: 'approve', challenge_id: challenge.challenge_id,
      user_decision: 'approve'
    }, true);
    const permit = approval.authorization && approval.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de actualización de fuente.');
    const result = await postSource({
      ...request, authorization_action: 'execute', authorization_permit: permit.token
    });
    if (!result.ok || result.effect_id !== 'system.source.update' || !result.head) {
      throw new Error('ExecutionGateway no confirmó la actualización del checkout.');
    }
    return result;
  }

  async function prepareUninstall(operation) {
    const base = String(await apiBase() || '').replace(/\/$/, '');
    if (!base) throw new Error('BAGO API local no está activa');
    const request = {
      install_dir: operation.install_dir,
      purge_state: !!operation.purge_state,
      interaction_id: `system-install-uninstall:${crypto.randomUUID()}`
    };
    const postUninstall = (payload, desktopApproval = false) => post(base, payload, desktopApproval, 'uninstall');
    const challengeResult = await postUninstall({ ...request, authorization_action: 'challenge' });
    const challenge = challengeResult.authorization && challengeResult.authorization.challenge;
    const target = challenge && challenge.target;
    if (!challenge || !challenge.challenge_id || !target || challenge.effect_id !== 'system.install.uninstall' ||
        target.install_dir !== request.install_dir || target.purge_state !== request.purge_state ||
        !target.tree_sha256 || !target.cli_sha256 ||
        !target.backup_root || !target.user_state_dir) {
      throw new Error('El challenge de desinstalación no coincide con el destino.');
    }
    const approved = await confirm({
      type: 'uninstall', installDir: target.install_dir, backupRoot: target.backup_root,
      userStateDir: target.user_state_dir, purgeState: target.purge_state,
      treeSha256: target.tree_sha256, cliSha256: target.cli_sha256
    });
    if (!approved) return null;
    const approval = await postUninstall({
      ...request, authorization_action: 'approve', challenge_id: challenge.challenge_id,
      user_decision: 'approve'
    }, true);
    const permit = approval.authorization && approval.authorization.permit;
    if (!permit || !permit.token) throw new Error('AuthorizationBoundary no devolvió un Permit de desinstalación.');
    const result = await postUninstall({
      ...request, authorization_action: 'execute', authorization_permit: permit.token
    });
    if (!result.ok || result.effect_id !== 'system.install.uninstall' || !result.receipt_id) {
      throw new Error('ExecutionGateway no confirmó la desinstalación.');
    }
    return result;
  }

  return { prepare, rollback, prepareSourceUpdate, prepareUninstall, prepareProviderCredential };
}

module.exports = { createSystemInstallClient, neutralInstallConfiguration };
