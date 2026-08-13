import { describe, expect, it } from 'vitest';
import { deriveWorkspaceKey, shouldResetWorkspaceState } from '../src/features/context-tree/useContextTree';

describe('workspace key derivation', () => {
  it('prefers the strongest workspace identity available', () => {
    expect(deriveWorkspaceKey(null)).toBeNull();
    expect(deriveWorkspaceKey({})).toBeNull();
    expect(deriveWorkspaceKey({ workspace_id: 'wid-1' })).toBe('wid-1');
    expect(deriveWorkspaceKey({ workspace_state_root: 'C:\\demo\\.gabo' })).toBe('C:\\demo\\.gabo');
    expect(deriveWorkspaceKey({ workspace_scope_root: 'C:\\demo' })).toBe('C:\\demo');
  });

  it('requests a reset when the workspace identity changes', () => {
    expect(shouldResetWorkspaceState(null, 'a')).toBe(false);
    expect(shouldResetWorkspaceState('a', null)).toBe(false);
    expect(shouldResetWorkspaceState('a', 'a')).toBe(false);
    expect(shouldResetWorkspaceState('a', 'b')).toBe(true);
  });
});
