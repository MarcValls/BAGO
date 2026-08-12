import { describe, expect, it, vi } from 'vitest';
import { PANEL_WIDTHS } from '../src/components/ui/PanelHost';

describe('PANEL_WIDTHS', () => {
  it('exports correct widths for each panel', () => {
    expect(PANEL_WIDTHS.agents).toBe(480);
    expect(PANEL_WIDTHS.interpreter).toBe(440);
    expect(PANEL_WIDTHS['github-auth']).toBe(400);
    expect(PANEL_WIDTHS.capabilities).toBe(320);
    expect(PANEL_WIDTHS.system).toBe(360);
    expect(PANEL_WIDTHS.pipeline).toBe(360);
    expect(PANEL_WIDTHS.tools).toBe(280);
  });

  it('has all PanelId keys', () => {
    const panelIds = ['agents', 'interpreter', 'github-auth', 'capabilities', 'system', 'pipeline', 'tools'] as const;
    for (const id of panelIds) {
      expect(PANEL_WIDTHS[id]).toBeDefined();
      expect(typeof PANEL_WIDTHS[id]).toBe('number');
    }
  });
});
