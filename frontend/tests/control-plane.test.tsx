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

// Helpers that distinguish the chat dock (which carries both classes) from a side panel/inspector.
const sidePanel = (container: HTMLElement) => container.querySelector('.inline-panel-host:not(.inline-chat-host)');
const chatDock = (container: HTMLElement) => container.querySelector('.inline-chat-host');
const rightColumnCount = (container: HTMLElement) => container.querySelectorAll('.inline-panel-host').length;

describe('ControlPlane chat-dock behaviour', () => {
  beforeEach(() => {
    window.localStorage.setItem('bago.first-run.v1.completed', 'true');
  });

  afterEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it('renders the workspace at full width when no chat is docked and no panel is open', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).not.toHaveClass('has-chat-dock');
    expect(mainArea).not.toHaveClass('has-panel');
    expect(chatDock(container)).not.toBeInTheDocument();
    expect(sidePanel(container)).not.toBeInTheDocument();
  });

  it('docks the chat as the only right column and uses a two-column layout', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('c', { ctrl: true, shift: true });

    await waitFor(() => {
      expect(chatDock(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).toHaveClass('has-chat-dock');
    expect(mainArea).toHaveClass('has-panel');
    expect(rightColumnCount(container)).toBe(1);
    expect(chatDock(container)).toHaveAttribute('aria-label', 'Chat acoplado');
    expect(sidePanel(container)).not.toBeInTheDocument();
  });

  it('mutually excludes the docked chat and a side panel: opening a panel undocks the chat', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(chatDock(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    fireShortcut('8', { ctrl: true });

    await waitFor(() => {
      expect(chatDock(container)).not.toBeInTheDocument();
      expect(sidePanel(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).not.toHaveClass('has-chat-dock');
    expect(mainArea).toHaveClass('has-panel');
    expect(rightColumnCount(container)).toBe(1);
  });

  it('undocks the chat and closes any side panel when toggling chat dock on', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('8', { ctrl: true });
    await waitFor(() => {
      expect(sidePanel(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    fireShortcut('c', { ctrl: true, shift: true });

    await waitFor(() => {
      expect(sidePanel(container)).not.toBeInTheDocument();
      expect(chatDock(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    expect(rightColumnCount(container)).toBe(1);
    expect(container.querySelector('.inline-panel-host')).toHaveClass('inline-chat-host');
  });

  it('hides the side panel when navigating to the full-screen chat section', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('8', { ctrl: true });
    await waitFor(() => {
      expect(sidePanel(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    fireShortcut('2', { ctrl: true });

    await waitFor(() => {
      expect(sidePanel(container)).not.toBeInTheDocument();
    }, { timeout: 1000 });

    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).not.toHaveClass('has-panel');
    expect(mainArea).not.toHaveClass('has-chat-dock');
  });

  it('toggles the docked chat off with the same keyboard shortcut', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(chatDock(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(chatDock(container)).not.toBeInTheDocument();
    }, { timeout: 1000 });

    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).not.toHaveClass('has-chat-dock');
    expect(mainArea).not.toHaveClass('has-panel');
  });

  it('shows the chat full screen and hides the dock when navigating to the chat section', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(chatDock(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    fireShortcut('2', { ctrl: true });

    await waitFor(() => {
      expect(chatDock(container)).not.toBeInTheDocument();
    }, { timeout: 1000 });

    const mainArea = container.querySelector('.app-main-area');
    expect(mainArea).not.toHaveClass('has-chat-dock');
  });

  it('restores the docked chat when leaving the full-screen chat section', async () => {
    const { container } = render(<ControlPlane />);

    await waitFor(() => {
      expect(container.querySelector('aside.main-sidebar')).toBeInTheDocument();
    }, { timeout: 3000 });

    fireShortcut('c', { ctrl: true, shift: true });
    await waitFor(() => {
      expect(chatDock(container)).toBeInTheDocument();
    }, { timeout: 1000 });

    fireShortcut('2', { ctrl: true });
    await waitFor(() => {
      expect(chatDock(container)).not.toBeInTheDocument();
    }, { timeout: 1000 });

    fireShortcut('1', { ctrl: true });
    await waitFor(() => {
      expect(chatDock(container)).toBeInTheDocument();
    }, { timeout: 1000 });
  });
});
