// @vitest-environment happy-dom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';
import { render, waitFor } from '@testing-library/react';
import { ControlPlane } from '../src/app/ControlPlane';

vi.mock('@/api/client', async (importOriginal) => {
  const original = await importOriginal<typeof import('@/api/client')>();
  return {
    ...original,
    createBagoClient: vi.fn((_apiBase: string, _apiToken: string) => ({
      setConfig: vi.fn(),
      bootstrap: vi.fn().mockResolvedValue({
        status: {
          framework_root: 'C:\\\\test\\\\bago',
          framework_version: '4.8.4',
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
  const event = new KeyboardEvent('keydown', {
    key,
    ctrlKey: ctrl,
    shiftKey: shift,
    bubbles: true,
    cancelable: true,
  });
  window.dispatchEvent(event);
}

describe('ControlPlane integration', () => {
  beforeEach(() => {
    window.localStorage.setItem('bago.first-run.v1.completed', 'true');
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('renders the main sidebar after bootstrap on large screens', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      const sidebar = container.querySelector('aside.main-sidebar');
      expect(sidebar).toBeInTheDocument();
    }, { timeout: 3000 });

    const sidebar = container.querySelector('aside.main-sidebar');
    expect(sidebar).toHaveAttribute('aria-label', 'Navegación principal');
    expect(sidebar?.querySelector('nav.sidebar-nav')).toBeInTheDocument();
  });

  it('only renders a docked chat panel when chatDocked is true and the active section is not chat', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    // Initially no docked chat panel.
    expect(container.querySelector('.inline-chat-host')).not.toBeInTheDocument();

    // Dock the chat with the canonical shortcut.
    fireShortcut('c', { ctrl: true, shift: true });

    await waitFor(() => {
      expect(container.querySelector('.inline-chat-host')).toBeInTheDocument();
    }, { timeout: 1000 });

    // The chat panel should be marked as docked and labelled as such.
    const dock = container.querySelector('.inline-chat-host');
    expect(dock).toHaveAttribute('aria-label', 'Chat acoplado');

    // The main area should reflect the two-column layout.
    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).toHaveClass('has-chat-dock');
    expect(mainArea).toHaveClass('has-panel');

    // No other section can be docked; verify only the chat host exists.
    expect(container.querySelectorAll('.inline-panel-host').length).toBe(1);
  });

  it('shows the chat as full screen and hides the dock when navigating to the chat section', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    // Start docked.
    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(container.querySelector('.inline-chat-host')).toBeInTheDocument();
    }, { timeout: 1000 });

    // Navigate to chat with Ctrl+2.
    fireShortcut('2', { ctrl: true });

    await waitFor(() => {
      // The docked panel disappears; chat is the active section (full screen).
      expect(container.querySelector('.inline-chat-host')).not.toBeInTheDocument();
    }, { timeout: 1000 });

    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).not.toHaveClass('has-chat-dock');
  });

  it('restores the docked chat when leaving the chat section while chatDocked remains true', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(container.querySelector('.inline-chat-host')).toBeInTheDocument();
    }, { timeout: 1000 });

    // Go to chat full screen.
    fireShortcut('2', { ctrl: true });
    await waitFor(() => {
      expect(container.querySelector('.inline-chat-host')).not.toBeInTheDocument();
    }, { timeout: 1000 });

    // Go back to home.
    fireShortcut('1', { ctrl: true });
    await waitFor(() => {
      expect(container.querySelector('.inline-chat-host')).toBeInTheDocument();
    }, { timeout: 1000 });
  });

  it('closes the docked chat panel when toggling it off again', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(container.querySelector('.inline-chat-host')).toBeInTheDocument();
    }, { timeout: 1000 });

    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(container.querySelector('.inline-chat-host')).not.toBeInTheDocument();
    }, { timeout: 1000 });

    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).not.toHaveClass('has-chat-dock');
  });
});
