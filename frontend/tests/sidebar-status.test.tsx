import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MainSidebar, sidebarStatusLabel } from '../src/layout/MainSidebar';

describe('sidebar status legend', () => {
  it('names every status without relying on color alone', () => {
    expect(sidebarStatusLabel('ok')).toBe('Listo');
    expect(sidebarStatusLabel('warn')).toBe('Requiere atención');
    expect(sidebarStatusLabel('error')).toBe('Error');
    expect(sidebarStatusLabel('unknown')).toBe('Estado no confirmado');
  });

  it('exposes each status dot through a native tooltip and accessible name', () => {
    const markup = renderToStaticMarkup(
      <MainSidebar
        activeSection="home"
        collapsed={false}
        openDrawer={null}
        onNavigate={() => undefined}
        onOpenDrawer={() => undefined}
        snapshot={{
          system: { backendAvailable: true, state: 'confirmed' },
          project: { root: 'C:\\test\\workspace' },
          workspace: { linkedToSession: true, manifestState: 'valid' },
          jobs: [],
          permissions: { canViewEvidence: true },
          context: { state: 'confirmed' },
          model: { state: 'confirmed' }
        } as never}
      />
    );

    expect(markup).toContain('role="img"');
    expect(markup).toContain('aria-label="Estado: Listo"');
    expect(markup).toContain('title="Estado: Listo"');
  });
});
