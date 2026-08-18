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
});
