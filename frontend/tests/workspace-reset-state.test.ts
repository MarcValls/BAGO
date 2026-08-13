import { describe, expect, it } from 'vitest';
import { createWorkspaceEditorResetState } from '../src/features/workspace/useWorkspaceEditor';

describe('workspace editor reset state', () => {
  it('returns a clean workspace state for a workspace rebind', () => {
    expect(createWorkspaceEditorResetState()).toEqual({
      tabs: [],
      activePath: null,
      selectedRange: null,
      inspector: { kind: null },
      bottomPanel: null,
      explorer: [],
      loadingExplorer: false,
      error: null,
      busy: false,
      output: [],
      expandedDirectories: []
    });
  });
});
