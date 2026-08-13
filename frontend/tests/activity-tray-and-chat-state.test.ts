import { describe, expect, it } from 'vitest';
import { workspaceSectionStorageKey } from '../src/features/sections';
import { workspaceContextStorageKey } from '../src/features/context-tree/ContextTreeModule';

describe('workspace-linked ui state keys', () => {
  it('keeps workspace context state isolated', () => {
    expect(workspaceContextStorageKey('C:\\demo-a', 'workbench-view')).toBe('bago.context.C:\\demo-a::workbench-view');
    expect(workspaceContextStorageKey('C:\\demo-b', 'workbench-view')).not.toBe(workspaceContextStorageKey('C:\\demo-a', 'workbench-view'));
  });

  it('keeps section state isolated by workspace', () => {
    expect(workspaceSectionStorageKey('C:\\demo-a', 'initial-branch')).toBe('bago.workspace.C:\\demo-a::section.initial-branch');
    expect(workspaceSectionStorageKey('C:\\demo-b', 'initial-branch')).not.toBe(workspaceSectionStorageKey('C:\\demo-a', 'initial-branch'));
  });
});
