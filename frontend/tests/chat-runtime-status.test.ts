import { describe, expect, it } from 'vitest';
import { runtimeStep } from '../src/layout/ChatPanel';
import type { UiBootstrapSnapshot } from '../src/contracts/backend';

function makeSnapshot(partial: Partial<UiBootstrapSnapshot> = {}): UiBootstrapSnapshot {
  return {
    system: { state: 'confirmed', backendAvailable: true },
    framework: { confirmed: true },
    project: { state: 'confirmed' },
    workspace: { manifestState: 'valid', linkedToSession: true },
    session: { state: 'valid' },
    model: { state: 'confirmed' },
    context: { state: 'confirmed' },
    permissions: {
      canChat: true,
      canInitializeWorkspace: true,
      canLinkWorkspace: true,
      canRepairWorkspace: true,
      canSeedWorkspace: true,
      canRunTools: true,
      canInspectContext: true,
      canViewEvidence: true,
      canStopPipeline: true,
      canRetryPipeline: true,
    },
    recommendedActions: [],
    ...partial,
  } as UiBootstrapSnapshot;
}

describe('runtime status UX helpers', () => {
  it('returns null when everything is healthy', () => {
    expect(runtimeStep(makeSnapshot())).toBeNull();
  });

  it('warns about backend when it is unavailable', () => {
    const snapshot = makeSnapshot({
      system: { state: 'error', backendAvailable: false },
    });
    expect(runtimeStep(snapshot)?.message).toContain('No hay conexión con el backend');
  });

  it('prompts to select a workspace when unlinked', () => {
    const snapshot = makeSnapshot({
      workspace: { manifestState: 'missing', linkedToSession: false },
      model: { state: 'unknown' },
    });
    expect(runtimeStep(snapshot)?.message).toContain('workspace');
  });

  it('prompts to configure a provider/model when workspace is valid but model is not confirmed', () => {
    const snapshot = makeSnapshot({
      model: { state: 'unknown' },
    });
    expect(runtimeStep(snapshot)?.message).toContain('proveedor');
  });

  it('prompts to repair workspace when linked but invalid', () => {
    const snapshot = makeSnapshot({
      workspace: { manifestState: 'invalid', linkedToSession: true },
    });
    expect(runtimeStep(snapshot)?.message).toContain('sembrado');
  });
});
