import { describe, expect, it } from 'vitest';
import { deriveWorkspaceGitHubKey } from '../src/features/workspace/WorkspaceModule';

describe('workspace module workspace identity', () => {
  it('derives a stable key from the active workspace', () => {
    expect(deriveWorkspaceGitHubKey(null)).toBe('');
    expect(deriveWorkspaceGitHubKey({ workspace: {} } as never)).toBe('');
    expect(deriveWorkspaceGitHubKey({ workspace: { root: 'C:\\demo' } } as never)).toBe('C:\\demo');
    expect(deriveWorkspaceGitHubKey({ workspace: { id: 'wid-1' } } as never)).toBe('wid-1');
  });
});
