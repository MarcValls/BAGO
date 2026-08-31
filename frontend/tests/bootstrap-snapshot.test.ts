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

  it('uses the modern workspace binding project root for conversation scope', () => {
    const snapshot = buildSnapshot({
      status: { provider: 'ollama-local', model: 'llama3.2:3b' },
      session: { session_id: 'session-1' },
      workspace: {
        root: 'C:/Work/project',
        state_root: 'C:/Work/project/.gabo',
        scope_root: 'C:/Work/project',
        binding: {
          project_root: 'C:/Work/project',
          workspace_state_root: 'C:/Work/project/.gabo',
          workspace_scope_root: 'C:/Work/project',
          binding_confirmed: true,
          binding_reason: 'ok'
        },
        permissions: { canChat: true }
      }
    });

    expect(snapshot?.project.root).toBe('C:/Work/project');
    expect(snapshot?.workspace.root).toBe('C:/Work/project');
    expect(snapshot?.workspace.root).not.toContain('.gabo');
  });
});
