import { describe, expect, it } from 'vitest';
import { buildSnapshot } from '../src/app/bootstrapSnapshot';
import { canPersistWorkspaceAuthority, resolveWorkspaceAuthority } from '../src/shared/workspaceAuthority';

describe('workspace authority presentation', () => {
  it('never presents a mismatched binding as operative', () => {
    const snapshot = buildSnapshot({
      status: {
        project_root: 'C:/BAGO/backend', workspace_state_root: 'C:/BAGO/backend/.gabo',
        workspace_state: { workspace_state: 'invalid', binding_confirmed: false, binding_reason: 'scope mismatch; manifest project mismatch' },
        health: { ok: true }
      },
      session: { session_id: 's1' }
    });
    expect(resolveWorkspaceAuthority(snapshot)).toMatchObject({
      state: 'blocked', requiresAction: true, label: 'Workspace requiere atención'
    });
  });

  it('prefers the authoritative nested binding over a stale legacy flag', () => {
    const snapshot = buildSnapshot({
      status: {
        project_root: 'C:/BAGO/backend', workspace_state_root: 'C:/BAGO/backend/.gabo',
        binding_confirmed: true, binding_reason: 'ok',
        workspace_state: { workspace_state: 'invalid', binding_confirmed: false, binding_reason: 'scope mismatch; manifest project mismatch' },
        health: { ok: true }
      },
      session: { session_id: 's1' }
    });
    expect(snapshot?.workspace).toMatchObject({ linkedToSession: false, manifestState: 'invalid' });
    expect(resolveWorkspaceAuthority(snapshot)).toMatchObject({ state: 'blocked', requiresAction: true });
    expect(canPersistWorkspaceAuthority(snapshot)).toBe(false);
  });

  it('uses the project name only after a valid binding', () => {
    const snapshot = buildSnapshot({
      status: {
        project_root: 'C:/Work/gestor-de-deudas', workspace_state_root: 'C:/Work/gestor-de-deudas/.gabo',
        workspace_state: { binding_confirmed: true }, provider: 'codex', model: 'gpt-5.5', health: { ok: true }
      },
      session: { session_id: 's1' }
    });
    expect(resolveWorkspaceAuthority(snapshot)).toMatchObject({
      state: 'confirmed', requiresAction: false, projectLabel: 'gestor-de-deudas'
    });
    expect(canPersistWorkspaceAuthority(snapshot)).toBe(true);
  });
});
