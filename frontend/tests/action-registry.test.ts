import { describe, expect, it, vi } from 'vitest';
import { createShellActions, NAVIGATION_GROUPS, NAVIGATION_ORDER, resolveNavigationShortcut } from '../src/navigation/actionRegistry';

describe('canonical shell action registry', () => {
  it('uses the same product order for sidebar, shortcuts and palette', () => {
    expect(NAVIGATION_ORDER).toEqual([
      'home', 'chat', 'workspace', 'context', 'pipeline', 'evidence', 'system', 'agents', 'interpreter', 'capabilities', 'tools', 'github-auth'
    ]);
    expect(NAVIGATION_GROUPS.flatMap((group) => group.items.map((item) => item.shortcut))).toEqual([
      'Ctrl+1', 'Ctrl+2', 'Ctrl+3', 'Ctrl+4', 'Ctrl+5', 'Ctrl+6', 'Ctrl+7', 'Ctrl+8', 'Ctrl+9', 'Ctrl+Shift+C', 'Ctrl+Shift+T', 'Ctrl+0'
    ]);
    expect(NAVIGATION_GROUPS.flatMap((group) => group.items.map((item) => item.label))).toContain('Operaciones');
  });

  it('exposes object and verb labels plus the reusable workspace action', () => {
    const noop = vi.fn();
    const actions = createShellActions({ navigate: noop, openWorkspace: noop, toggleSidebar: noop, toggleFocus: noop, toggleReview: noop, runCommand: noop, runContextCommand: noop, sidebarCollapsed: false, globalMode: 'normal' });
    expect(new Set(actions.map((action) => action.id)).size).toBe(actions.length);
    expect(actions.find((action) => action.id === 'workspace-change')?.label).toBe('Workspace · Cambiar');
    expect(actions.every((action) => Boolean(action.object && action.verb && action.group))).toBe(true);
  });

  it('resolves every advertised shortcut from the same registry', () => {
    const items = NAVIGATION_GROUPS.flatMap((group) => group.items);
    expect(items.map((item) => resolveNavigationShortcut(item.shortcut))).toEqual(NAVIGATION_ORDER);
    expect(resolveNavigationShortcut('x')).toBeNull();
  });
});
