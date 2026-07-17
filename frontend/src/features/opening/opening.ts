import type { OpeningDecision, UiBootstrapSnapshot } from '@/contracts/backend';

export function resolveOpeningState(snapshot: UiBootstrapSnapshot | null): OpeningDecision {
  if (!snapshot) {
    return {
      id: 'show_blocked_state',
      label: 'Loading backend snapshot',
      reason: 'The control plane has not bootstrapped yet.',
      actionLabel: 'Retry bootstrap',
      targetSection: 'home'
    };
  }

  if (!snapshot.system.backendAvailable || snapshot.system.state === 'error') {
    return {
      id: 'show_blocked_state',
      label: 'Backend unavailable',
      reason: 'BAGO API did not return a usable snapshot.',
      actionLabel: 'Check backend',
      targetSection: 'system'
    };
  }

  if (snapshot.workspace.manifestState === 'legacy') {
    return {
      id: 'show_legacy_migration',
      label: 'Legacy workspace detected',
      reason: 'A legacy .bago workspace is present and should be reviewed before proceeding.',
      actionLabel: 'Inspect migration',
      targetSection: 'workspace'
    };
  }

  if (snapshot.workspace.manifestState === 'invalid' || snapshot.session.state === 'blocked') {
    return {
      id: 'show_workspace_repair',
      label: 'Workspace needs repair',
      reason: 'The backend reports an invalid binding or blocked session.',
      actionLabel: 'Open repair',
      targetSection: 'workspace'
    };
  }

  if (!snapshot.workspace.root || snapshot.project.state === 'not_detected') {
    return {
      id: 'show_workspace_init',
      label: 'No workspace detected',
      reason: 'The backend did not report an active project root.',
      actionLabel: 'Initialize workspace',
      targetSection: 'home'
    };
  }

  if (snapshot.workspace.linkedToSession && snapshot.session.state === 'valid' && snapshot.system.state !== 'degraded') {
    return {
      id: 'enter_directly',
      label: 'Workspace linked and session valid',
      reason: 'The backend reports a confirmed workspace binding.',
      actionLabel: 'Open chat',
      targetSection: 'chat'
    };
  }

  if (snapshot.workspace.root && !snapshot.workspace.linkedToSession) {
    return {
      id: 'show_workspace_link',
      label: 'Workspace ready to link',
      reason: 'A workspace exists but the session is not linked yet. You can link it and seed it to make it valid.',
      actionLabel: 'Link and seed',
      targetSection: 'home'
    };
  }

  if (snapshot.system.state === 'degraded' || snapshot.context.state === 'stale') {
    return {
      id: 'show_recovery',
      label: 'Recovery recommended',
      reason: 'The session is valid, but some backend signals are degraded or stale.',
      actionLabel: 'Open recovery',
      targetSection: 'home'
    };
  }

  return {
    id: 'show_recovery',
    label: 'Recovery recommended',
    reason: 'The backend state is ambiguous; opening the shell in recovery mode.',
    actionLabel: 'Open recovery',
    targetSection: 'home'
  };
}
