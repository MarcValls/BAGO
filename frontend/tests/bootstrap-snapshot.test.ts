import { describe, expect, it } from 'vitest';
import { buildSnapshot } from '@/app/bootstrapSnapshot';

describe('bootstrap snapshot normalization', () => {
  it('preserves workspace, provider and permission fallbacks', () => {
    const snapshot = buildSnapshot({
      status: {
        framework_version: '4.8.1',
        workspace_state_root: 'C:/workspace/.gabo',
        repo_root: 'C:/workspace',
        workspace_state: { binding_confirmed: true, binding_reason: 'ok' },
        provider: 'copilot',
        model: 'gpt-5.4-mini',
        active_bridges: ['copilot'],
        context_revision: 'ctx-1',
        last_receipt: { envelope_id: 'receipt-1' },
        health: { ok: true, latency_ms: 12 }
      },
      session: { session_id: 'session-1' }
    });

    expect(snapshot?.workspace.linkedToSession).toBe(true);
    expect(snapshot?.workspace.repoRoot).toBe('C:/workspace');
    expect(snapshot?.model).toMatchObject({ provider: 'copilot', effectiveModel: 'gpt-5.4-mini' });
    expect(snapshot?.permissions.canChat).toBe(true);
    expect(snapshot?.recommendedActions.map((action) => action.id)).toContain('open-chat');
  });

  it('returns null for an absent backend payload', () => {
    expect(buildSnapshot(null)).toBeNull();
  });

  it('enforces backend action authority and never maps repair to project init', () => {
    const snapshot = buildSnapshot({
      status: {
        framework_root: 'C:/bago',
        project_root: 'C:/workspace',
        workspace_state_root: 'C:/workspace/.gabo',
        workspace_state: {
          workspace_state: 'invalid',
          binding_confirmed: false,
          binding_reason: 'manifest invalid',
        },
        provider: 'copilot',
        model: 'gpt-5.4-mini',
        health: { ok: true },
      },
      session: {
        session_id: 'session-1',
        menu_state: {
          acciones_recomendadas: ['workspace.inspect', 'workspace.repair'],
          acciones_permitidas: ['workspace.inspect', 'workspace.repair'],
          acciones_bloqueadas: ['chat.send', 'workspace.init'],
        },
      },
      workspace: {
        permissions: { canChat: false, canRepairWorkspace: true },
      },
    });

    expect(snapshot?.workspace.manifestState).toBe('invalid');
    expect(snapshot?.menuState?.allowedActions).toContain('workspace.repair');
    expect(snapshot?.recommendedActions.find((action) => action.id === 'open-chat')).toMatchObject({ enabled: false });
    expect(snapshot?.recommendedActions.find((action) => action.id === 'workspace-repair')).toMatchObject({
      kind: 'navigate',
      enabled: true,
      payload: { section: 'workspace', contractAction: 'workspace.repair' },
    });
    expect(snapshot?.recommendedActions.find((action) => action.id === 'workspace-repair')?.payload?.endpoint).toBeUndefined();
  });
});
