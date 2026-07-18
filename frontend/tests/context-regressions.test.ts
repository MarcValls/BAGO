import { describe, expect, it, vi } from 'vitest';
import { compileContextPack } from '../src/features/context-tree/compileContextPack';
import { contextNodeTypeForBankItem } from '../src/features/context-tree/contextBankMapping';
import { createContextActions, type ContextActionDeps } from '../src/features/context-menu/contextActions';
import type { SelectionRecord } from '../src/contracts/backend';
import type { ContextNode, ContextPack, ContextTree } from '../src/features/context-tree/contextTreeTypes';

function node(overrides: Partial<ContextNode> = {}): ContextNode {
  return {
    id: 'node-1', treeId: 'tree-1', parentId: 'root', type: 'risk', status: 'conflict',
    title: 'Risk', summary: 'Open conflict', priority: 'high', weightTokens: 12,
    sourceRefs: [], evidenceRefs: [], linkedNodeIds: [], conflictNodeIds: ['node-2'],
    tags: [], metadata: {}, createdBy: 'user', updatedBy: 'user',
    createdAt: '2026-01-01T00:00:00Z', updatedAt: '2026-01-01T00:00:00Z',
    ...overrides
  };
}

describe('canonical context regressions', () => {
  it('preserves computed safety counters when compiling a pack', () => {
    const selected = node();
    const root = node({ id: 'root', parentId: null, type: 'root', status: 'active', conflictNodeIds: [] });
    const tree: ContextTree = {
      id: 'tree-1', name: 'Tree', archived: false, createdAt: root.createdAt,
      updatedAt: root.updatedAt, rootId: root.id, nodes: { root, [selected.id]: selected }
    };
    const pack: ContextPack = {
      id: 'pack-1', treeId: tree.id, name: 'Pack', status: 'draft', nodeIds: [selected.id],
      weightTokens: 0, conflicts: 0, proposals: 0, staleCount: 0
    };

    const compiled = compileContextPack(tree, pack);

    expect(compiled).toMatchObject({ conflicts: 1, proposals: 0, staleCount: 0, weightTokens: 12 });
  });

  it.each([
    ['workspace_file', 'file'],
    ['risk', 'risk'],
    ['pending', 'pending']
  ] as const)('maps %s bank items to %s nodes', (kind, expected) => {
    expect(contextNodeTypeForBankItem(kind)).toBe(expected);
  });

  it('opens Chat after preparing a contextual draft', () => {
    const setDraft = vi.fn();
    const ensureChatPanel = vi.fn();
    const deps = {
      turns: [], snapshot: null, opening: {}, booting: false,
      routerState: { list: null, policy: null },
      uiState: { drafts: { chat: '' }, chatMode: 'live', globalMode: 'normal' },
      readSelectionPath: vi.fn(() => ''), useSelectionInChat: vi.fn(), openInspector: vi.fn(),
      openShell: vi.fn(), openWorkspacePicker: vi.fn(), openWorkspaceFileFromMenu: vi.fn(),
      openSectionFromSelection: vi.fn(), navigate: vi.fn(), runCommand: vi.fn(),
      runContextCommand: vi.fn(), bootstrap: vi.fn(), refreshAfterMutation: vi.fn(),
      refreshRouterState: vi.fn(), setRouterAutoSwitch: vi.fn(), setDraft, ensureChatPanel,
      writeClipboard: vi.fn(), setAndPersistUiState: vi.fn(), confirm: vi.fn(() => true)
    } as unknown as ContextActionDeps;
    const selection = { id: 'chat', kind: 'screen-chat', targetKind: 'screen.chat', title: 'Chat', summary: '', detail: [] } as SelectionRecord;

    createContextActions(selection, deps).find((action) => action.id === 'chat-plan')?.onClick();

    expect(setDraft).toHaveBeenCalledWith('chat', '/plan ');
    expect(ensureChatPanel).toHaveBeenCalledOnce();
  });
});
