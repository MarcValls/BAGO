import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  persistWorkspaceEditorState,
  readPersistedWorkspaceEditorState,
  workspaceEditorStorageKey
} from '../src/features/workspace/useWorkspaceEditor';

describe('workspace editor persistence', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('persists and restores editor state only for the same workspace root', () => {
    const store = new Map<string, string>();
    vi.stubGlobal('window', {
      localStorage: {
        getItem: (key: string) => store.get(key) ?? null,
        setItem: (key: string, value: string) => {
          store.set(key, value);
        },
        removeItem: (key: string) => {
          store.delete(key);
        },
        clear: () => {
          store.clear();
        }
      }
    });

    persistWorkspaceEditorState({
      workspaceRoot: 'C:/work/a',
      tabs: [{ id: '1', path: 'a.txt', language: 'text', label: 'a.txt', baseline: 'x', content: 'y', state: 'dirty', inContext: false, withEvidence: false, diagnostics: [], patterns: [] }],
      activePath: 'a.txt',
      selectedRange: null,
      inspector: { kind: 'file', refId: 'a.txt' },
      bottomPanel: 'changes',
      explorer: [],
      loadingExplorer: false,
      error: null,
      busy: false,
      output: [],
      expandedDirectories: ['dir-1']
    });

    expect(readPersistedWorkspaceEditorState('C:/work/a')?.activePath).toBe('a.txt');
    expect(readPersistedWorkspaceEditorState('C:/work/b')).toBeNull();
    expect(workspaceEditorStorageKey('C:/work/a')).not.toBe(workspaceEditorStorageKey('C:/work/b'));
  });
});
