import { describe, expect, it, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { ActivityToast, filterPaletteActions, HelpOverlay } from '../src/app/ControlPlaneOverlays';
import type { BagoAction } from '../src/navigation/actionRegistry';

const actions: BagoAction[] = [
  { id: 'workspace', object: 'Workspace', verb: 'Abrir', label: 'Abrir workspace', group: 'Navegación', icon: 'workspace', keywords: ['archivos'], action: vi.fn() },
  { id: 'context', object: 'Contexto', verb: 'Medir', label: 'Medir contexto', group: 'Contexto', icon: 'context', keywords: ['tokens'], action: vi.fn() },
];

describe('ControlPlane overlays', () => {
  it('filters palette actions across labels, groups and keywords', () => {
    expect(filterPaletteActions(actions, 'archivos').map((item) => item.id)).toEqual(['workspace']);
    expect(filterPaletteActions(actions, 'medir').map((item) => item.id)).toEqual(['context']);
    expect(filterPaletteActions(actions, '')).toEqual(actions);
    expect(filterPaletteActions(actions, 'missing')).toEqual([]);
  });

  it('renders a live status toast with its computed state', () => {
    const markup = renderToStaticMarkup(<ActivityToast message="" busy state="confirmed" />);
    expect(markup).toContain('role="status"');
    expect(markup).toContain('state-loading');
    expect(markup).toContain('procesando');
  });

  it('documents the chat dock shortcut and the screen-sharing rule in the help panel', () => {
    const markup = renderToStaticMarkup(<HelpOverlay onClose={vi.fn()} onOpenFirstRun={vi.fn()} />);
    expect(markup).toContain('Ctrl Shift C');
    expect(markup).toContain('Acoplar o desacoplar el chat');
    expect(markup).toContain('pantalla completa');
    expect(markup).toContain('solo una columna derecha puede estar visible');
  });
});
