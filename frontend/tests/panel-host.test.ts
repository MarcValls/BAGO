import { describe, expect, it, vi } from 'vitest';
import { PANEL_WIDTHS } from '../src/components/ui/PanelHost';
import { NAVIGATION_GROUPS } from '../src/navigation/actionRegistry';

// Los anchos se derivan del registro de navegación: declarar un ancho para un
// panel inalcanzable dejaría código implementado sin ninguna ruta de UI.
const NAVIGABLE_PANELS = NAVIGATION_GROUPS
  .flatMap((group) => group.items)
  .filter((item) => item.isPanel)
  .map((item) => item.id);

describe('PANEL_WIDTHS', () => {
  it('exports correct widths for each panel', () => {
    expect(PANEL_WIDTHS.agents).toBe(640);
    expect(PANEL_WIDTHS.interpreter).toBe(620);
    expect(PANEL_WIDTHS['github-auth']).toBe(560);
    expect(PANEL_WIDTHS.capabilities).toBe(560);
    expect(PANEL_WIDTHS.tools).toBe(520);
  });

  it('has all PanelId keys', () => {
    for (const id of NAVIGABLE_PANELS) {
      expect(PANEL_WIDTHS[id as keyof typeof PANEL_WIDTHS]).toBeDefined();
      expect(typeof PANEL_WIDTHS[id as keyof typeof PANEL_WIDTHS]).toBe('number');
    }
  });

  it('does not declare widths for panels that cannot be reached', () => {
    expect(Object.keys(PANEL_WIDTHS).sort()).toEqual([...NAVIGABLE_PANELS].sort());
  });
});
