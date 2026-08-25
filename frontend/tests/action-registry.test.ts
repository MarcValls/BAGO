import { describe, expect, it, vi } from 'vitest';
import { createShellActions, NAVIGATION_GROUPS, NAVIGATION_ORDER, resolveNavigationShortcut } from '../src/navigation/actionRegistry';

function makeShellActions(chatDocked = false) {
  const noop = vi.fn();
  return createShellActions({
    navigate: noop,
    openWorkspace: noop,
    toggleSidebar: noop,
    toggleFocus: noop,
    toggleReview: noop,
    toggleChatDock: noop,
    chatDocked,
    runCommand: noop,
    runContextCommand: noop,
    sidebarCollapsed: false,
    globalMode: 'normal'
  });
}

describe('canonical shell action registry', () => {
  it('uses the same product order for sidebar, shortcuts and palette', () => {
    expect(NAVIGATION_ORDER).toEqual([
      'home', 'workspace', 'context', 'pipeline', 'evidence', 'system', 'agents', 'interpreter', 'github-auth', 'capabilities', 'tools'
    ]);
    expect(NAVIGATION_GROUPS.flatMap((group) => group.items.map((item) => item.shortcut))).toEqual([
      'Ctrl+1', 'Ctrl+2', 'Ctrl+3', 'Ctrl+4', 'Ctrl+5', 'Ctrl+6', 'Ctrl+7', 'Ctrl+8', 'Ctrl+9', 'Ctrl+-', 'Ctrl+='
    ]);
    expect(NAVIGATION_GROUPS.flatMap((group) => group.items.map((item) => item.label))).toContain('Operaciones');
  });

  it('exposes object and verb labels plus the reusable workspace action', () => {
    const actions = makeShellActions();
    expect(new Set(actions.map((action) => action.id)).size).toBe(actions.length);
    expect(actions.find((action) => action.id === 'workspace-change')?.label).toBe('Workspace · Cambiar');
    expect(actions.every((action) => Boolean(action.object && action.verb && action.group))).toBe(true);
  });

  it('resolves every advertised shortcut from the same registry', () => {
    const items = NAVIGATION_GROUPS.flatMap((group) => group.items);
    expect(items.map((item) => resolveNavigationShortcut(item.shortcut.slice(-1)))).toEqual(NAVIGATION_ORDER);
    expect(resolveNavigationShortcut('x')).toBeNull();
  });

  it('advertises a chat-dock action with the canonical shortcut', () => {
    const actions = makeShellActions(false);
    const dock = actions.find((action) => action.id === 'toggle-chat-dock');
    expect(dock).toBeDefined();
    expect(dock?.shortcut).toBe('Ctrl+Shift+C');
    expect(dock?.label).toBe('Vista · Acoplar chat');
    expect(dock?.icon).toBe('chat');
  });

  it('reflects the current dock state in the chat-dock action label', () => {
    const undocked = makeShellActions(false);
    expect(undocked.find((action) => action.id === 'toggle-chat-dock')?.verb).toBe('Acoplar chat');
    const docked = makeShellActions(true);
    expect(docked.find((action) => action.id === 'toggle-chat-dock')?.verb).toBe('Quitar chat acoplado');
  });
});
