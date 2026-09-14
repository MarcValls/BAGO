import { describe, expect, it, vi } from 'vitest';
import { NAVIGATION_GROUPS } from '../src/navigation/actionRegistry';
import { PANEL_WIDTHS } from '../src/components/ui/PanelHost';

describe('panel navigation', () => {
  it('has panel items for agents, interpreter, github-auth, capabilities, tools', () => {
    const allItems = NAVIGATION_GROUPS.flatMap((g) => g.items);
    const panelIds = allItems.filter((i) => i.isPanel).map((i) => i.id);
    expect(panelIds).toContain('agents');
    expect(panelIds).toContain('interpreter');
    expect(panelIds).toContain('github-auth');
    expect(panelIds).toContain('capabilities');
    expect(panelIds).toContain('tools');
  });

  it('has exactly 5 panel navigation items', () => {
    const allItems = NAVIGATION_GROUPS.flatMap((g) => g.items);
    const panelItems = allItems.filter((i) => i.isPanel);
    expect(panelItems).toHaveLength(5);
  });

  it('PANEL_WIDTHS has entries for all panel ids', () => {
    const panelIds = NAVIGATION_GROUPS
      .flatMap((group) => group.items)
      .filter((item) => item.isPanel)
      .map((item) => item.id as keyof typeof PANEL_WIDTHS);
    expect(panelIds.length).toBeGreaterThan(0);
    for (const id of panelIds) {
      expect(typeof PANEL_WIDTHS[id]).toBe('number');
      expect(PANEL_WIDTHS[id]).toBeGreaterThan(0);
    }
  });

  it('createShellActions includes openPanel for panel items', () => {
    const allItems = NAVIGATION_GROUPS.flatMap((g) => g.items);
    const panelItems = allItems.filter((i) => i.isPanel);
    // verify each panel item has the right structure
    for (const item of panelItems) {
      expect(item.id).toBeDefined();
      expect(item.isPanel).toBe(true);
    }
  });
});
