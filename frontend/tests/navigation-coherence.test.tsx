// @vitest-environment happy-dom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';
import { fireEvent, render, waitFor } from '@testing-library/react';
import { ControlPlane } from '../src/app/ControlPlane';
import {
  NAVIGATION_GROUPS,
  resolveNavigationShortcut,
  SECTION_LABELS,
} from '../src/navigation/actionRegistry';
import { PANEL_WIDTHS } from '../src/components/ui/PanelHost';
import type { PanelId } from '../src/contracts/backend';

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>();
  return {
    ...original,
    createBagoClient: vi.fn(() => ({
      setConfig: vi.fn(),
      bootstrap: vi.fn().mockResolvedValue({
        status: {
          framework_root: 'C:\\\\test\\\\bago',
          framework_version: '4.10.0',
          backendAvailable: true,
          provider: 'copilot',
          model: 'gpt-4',
          binding_confirmed: true,
          workspace_state: 'valid',
          session_id: 'test-session',
          active_bridges: ['chat'],
        },
        session: { session_id: 'test-session' },
        providers: { providers: [], catalog: [] },
        menu: { sections: [] },
        routes: { ok: true, routes: [] },
        router_list: { entries: [], selected_count: 0 },
        router_policy: { entries: [], selected: [] },
      }),
      getRouterList: vi.fn().mockResolvedValue({ entries: [], selected_count: 0 }),
      getRouterPolicy: vi.fn().mockResolvedValue({ entries: [], selected: [] }),
      persistWorkspace: vi.fn().mockResolvedValue({ ok: true }),
      getSessionModel: vi.fn().mockResolvedValue({ model: null }),
      setSessionModel: vi.fn().mockResolvedValue({ ok: true }),
      getReasoningDepth: vi.fn().mockResolvedValue({ depth: 'standard' }),
      setReasoningDepth: vi.fn().mockResolvedValue({ ok: true }),
      streamEvents: vi.fn().mockReturnValue(new Promise(() => {})),
      listCapabilities: vi.fn().mockResolvedValue({ packages: [] }),
      getCapabilitySnapshot: vi.fn().mockResolvedValue({ ok: true }),
      inspectCapabilityPackage: vi.fn().mockResolvedValue({ ok: true }),
      executeCapability: vi.fn().mockResolvedValue({ ok: true }),
      getInstalledCapabilities: vi.fn().mockResolvedValue({ packages: [] }),
      getProviderStatus: vi.fn().mockResolvedValue({ state: 'confirmed' }),
      getProviderModels: vi.fn().mockResolvedValue({ models: [] }),
      getActiveProvider: vi.fn().mockResolvedValue({ provider: 'copilot' }),
      getActiveProviderModels: vi.fn().mockResolvedValue({ active_models: [], models: [] }),
      configureProvider: vi.fn().mockResolvedValue({ ok: true }),
      setRouterAuto: vi.fn().mockResolvedValue({ ok: true }),
      toggleRouter: vi.fn().mockResolvedValue({ ok: true }),
      manageSource: vi.fn().mockResolvedValue({ ok: true }),
      sendCommand: vi.fn().mockResolvedValue({ ok: true }),
      sendChat: vi.fn().mockResolvedValue({ ok: true, message: { id: '1', role: 'assistant', content: 'ok' } }),
      createConversation: vi.fn().mockResolvedValue({ ok: true }),
      switchConversation: vi.fn().mockResolvedValue({ ok: true }),
      deleteConversation: vi.fn().mockResolvedValue({ ok: true }),
      getConversations: vi.fn().mockResolvedValue({ conversations: [] }),
      getHistory: vi.fn().mockResolvedValue({ messages: [] }),
      getFiles: vi.fn().mockResolvedValue({ files: [] }),
      getEvidence: vi.fn().mockResolvedValue({ evidence: [] }),
      getJobs: vi.fn().mockResolvedValue({ jobs: [] }),
      getSchedule: vi.fn().mockResolvedValue({ items: [] }),
      getSources: vi.fn().mockResolvedValue({ sources: [] }),
      listAgents: vi.fn().mockResolvedValue({ ok: true, agents: [] }),
      createAgent: vi.fn().mockResolvedValue({ ok: true }),
      updateAgent: vi.fn().mockResolvedValue({ ok: true }),
      deleteAgent: vi.fn().mockResolvedValue({ ok: true }),
      duplicateAgent: vi.fn().mockResolvedValue({ ok: true }),
      runInterpretation: vi.fn().mockResolvedValue({ ok: true }),
      getInterpretationStatus: vi.fn().mockResolvedValue({ ok: true }),
      startGitHubAuth: vi.fn().mockResolvedValue({ ok: true }),
      refreshGitHubToken: vi.fn().mockResolvedValue({ ok: true }),
      logoutGitHub: vi.fn().mockResolvedValue({ ok: true }),
      setupGitCli: vi.fn().mockResolvedValue({ ok: true }),
      listGitHubAccounts: vi.fn().mockResolvedValue({ ok: true, accounts: [] }),
    })),
    persistApiConfig: vi.fn(),
    readStoredApiBase: vi.fn().mockReturnValue('http://127.0.0.1:8080'),
    resolveDefaultApiBase: vi.fn().mockReturnValue('http://127.0.0.1:8080'),
  };
});

function fireShortcut(key: string, { ctrl = false, shift = false } = {}) {
  window.dispatchEvent(new KeyboardEvent('keydown', {
    key, ctrlKey: ctrl, shiftKey: shift, bubbles: true, cancelable: true,
  }));
}

const navItems = () => NAVIGATION_GROUPS.flatMap((group) => group.items);
const sidePanel = (container: HTMLElement) => container.querySelector('.inline-panel-host:not(.inline-chat-host)');

async function renderShell() {
  const view = render(<ControlPlane />);
  await waitFor(() => {
    expect(view.container.querySelector('aside.main-sidebar')).toBeInTheDocument();
  }, { timeout: 3000 });
  return view;
}

// El sidebar arranca colapsado y no pinta etiquetas, pero siempre expone el
// destino en `title`, así que ese es el localizador estable.
function sidebarButton(container: HTMLElement, label: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll('.main-sidebar .sidebar-item'))
    .find((node) => {
      const title = node.getAttribute('title') || '';
      return title === label || title.startsWith(`${label} ·`) || node.textContent?.includes(label);
    });
  if (!button) throw new Error(`No existe entrada de navegación "${label}"`);
  return button as HTMLButtonElement;
}

describe('coherencia del registro de navegación', () => {
  it('todo PanelId implementado es alcanzable desde la navegación', () => {
    const declared = Object.keys(PANEL_WIDTHS) as PanelId[];
    const reachable = new Set(navItems().filter((item) => item.isPanel).map((item) => item.id));
    const orphans = declared.filter((panelId) => !reachable.has(panelId));
    expect(orphans, `Paneles implementados pero inalcanzables: ${orphans.join(', ')}`).toEqual([]);
  });

  it('todo destino de navegación tiene etiqueta canónica', () => {
    for (const item of navItems()) {
      expect(SECTION_LABELS[item.id], `Falta etiqueta para ${item.id}`).toBeTruthy();
    }
  });

  it('no hay identificadores de navegación duplicados', () => {
    const ids = navItems().map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('cada atajo anunciado resuelve a su destino declarado', () => {
    for (const item of navItems()) {
      const key = item.shortcut.replace(/^Ctrl\+/i, '');
      expect(
        resolveNavigationShortcut(key),
        `El atajo anunciado ${item.shortcut} para "${item.label}" no resuelve`,
      ).toBe(item.id);
    }
  });
});

describe('acceso a pantallas desde el sidebar', () => {
  beforeEach(() => {
    window.localStorage.setItem('bago.first-run.v1.completed', 'true');
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('pulsar "Agentes" abre la pantalla de gestión de agentes', async () => {
    const { container } = await renderShell();

    fireEvent.click(sidebarButton(container, 'Agentes'));

    await waitFor(() => {
      expect(container.querySelector('[aria-label="Editor de Agentes"]')).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('cada atajo anunciado en el sidebar abre realmente su destino', async () => {
    const { container } = await renderShell();

    for (const item of navItems().filter((entry) => entry.isPanel)) {
      const key = item.shortcut.replace(/^Ctrl\+/i, '');
      fireShortcut(key, { ctrl: true });
      // El sidebar marca `aria-current="page"` sobre el destino realmente
      // abierto, así que identifica el panel concreto y no "algún" panel.
      await waitFor(() => {
        const active = sidebarButton(container, item.label);
        expect(
          active.getAttribute('aria-current'),
          `El atajo ${item.shortcut} no abrió "${item.label}"`,
        ).toBe('page');
      }, { timeout: 1000 });
    }
  });

  it('abrir un panel en modo focus nunca deja el área de trabajo en blanco', async () => {
    const { container } = await renderShell();

    // En modo focus el sidebar se desmonta, pero el panel sigue siendo
    // alcanzable por atajo y desde la paleta de comandos.
    fireShortcut('F11');
    await waitFor(() => {
      expect(container.querySelector('.app-root')).toHaveClass('mode-focus');
    }, { timeout: 1000 });

    fireShortcut('7', { ctrl: true });

    await waitFor(() => {
      const root = container.querySelector('.app-root') as HTMLElement;
      const mainArea = container.querySelector('.app-main-area') as HTMLElement;
      // El CSS oculta el workspace cuando hay panel lateral y oculta el panel
      // en focus/lectura. Si ambas condiciones coinciden, no queda nada visible.
      const panelHiddenByMode = root.classList.contains('mode-focus') || root.classList.contains('mode-review');
      const workspaceHiddenByPanel = mainArea.classList.contains('has-side-panel');
      expect(
        panelHiddenByMode && workspaceHiddenByPanel,
        'Panel y workspace ocultos a la vez: el área de trabajo queda en blanco',
      ).toBe(false);
      expect(sidePanel(container)).toBeInTheDocument();
      expect(container.querySelector('[aria-label="Editor de Agentes"]')).toBeInTheDocument();
    }, { timeout: 1000 });
  });
});
