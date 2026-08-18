import type {
  BackendCommandResult,
  BackendHistory,
  BackendMenu,
  BackendRouterList,
  BackendRouterPolicy,
  BackendProviders,
  BackendRoutes,
  BackendSession,
  BackendStatus,
  UiBootData
} from '@/contracts/backend';
import type { CapabilityExecutionResponse, CapabilityPackageResponse, PackageInspection } from '@/modules/capability-anatomy/packageContract';
import type { CapabilityListResponse, CapabilitySnapshot } from '@/modules/capability-anatomy/contract';

const FALLBACK_BASE = '';
const STORAGE_BASE = 'bago.ui.apiBase';

export function resolveDefaultApiBase(): string {
  if (typeof window === 'undefined') {
    return FALLBACK_BASE;
  }
  const envBase = import.meta.env.VITE_BAGO_API_BASE as string | undefined;
  if (envBase && envBase.trim()) {
    return envBase.trim().replace(/\/+$/, '');
  }
  if (window.location.protocol === 'file:') {
    return FALLBACK_BASE;
  }
  if (window.location.origin) {
    return window.location.origin.replace(/\/+$/, '');
  }
  return FALLBACK_BASE;
}

export function readStoredApiBase(): string {
  return typeof window === 'undefined' ? FALLBACK_BASE : localStorage.getItem(STORAGE_BASE) || resolveDefaultApiBase();
}

export function persistApiConfig(apiBase: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_BASE, apiBase.trim().replace(/\/+$/, ''));
  localStorage.removeItem('bago.ui.apiToken');
}

type JsonValue = Record<string, unknown> | Array<unknown> | string | number | boolean | null;

class BagoHttpError extends Error {
  status: number;
  payload: Record<string, unknown>;
  provider: string;
  model: string;

  constructor(status: number, message: string, payload: Record<string, unknown> = {}) {
    super(message);
    this.name = 'BagoHttpError';
    this.status = status;
    this.payload = payload;
    this.provider = String(payload.provider || '');
    this.model = String(payload.model || '');
  }
}

function shouldFallbackToLegacy(error: unknown): boolean {
  if (error instanceof BagoHttpError) {
    return [404, 405, 501].includes(error.status);
  }
  return error instanceof TypeError;
}

export class BagoClient {
  constructor(
    private apiBase: string,
    private apiToken: string
  ) {}

  setConfig(apiBase: string, apiToken: string): void {
    this.apiBase = apiBase.trim().replace(/\/+$/, '');
    this.apiToken = apiToken.trim();
  }

  private headers(extra?: Record<string, string>): HeadersInit {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(extra || {})
    };
    if (this.apiToken) {
      headers['X-Bago-Token'] = this.apiToken;
    }
    headers['X-Bago-Channel'] = 'ui-react';
    return headers;
  }

  private url(path: string): string {
    const clean = path.startsWith('/') ? path : `/${path}`;
    return `${this.apiBase}${clean}`;
  }

  private modernUrl(path: string): string {
    const clean = path.startsWith('/') ? path : `/${path}`;
    return `${this.apiBase}/api/v1${clean}`;
  }

  async request<T = unknown>(path: string, init: RequestInit = {}, timeoutMs?: number): Promise<T> {
    const headers = new Headers(init.headers || {});
    for (const [key, value] of Object.entries(this.headers() as Record<string, string>)) {
      headers.set(key, value);
    }
    const effectiveTimeout = timeoutMs ?? 30_000;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), effectiveTimeout);
    let response: Response;
    try {
      response = await fetch(this.url(path), {
        ...init,
        headers,
        signal: controller.signal
      });
    } finally {
      clearTimeout(timer);
    }
    if (!response.ok) {
      const errorText = await response.text();
      let errorPayload: Record<string, unknown> = {};
      try {
        const parsed = errorText ? JSON.parse(errorText) : {};
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          errorPayload = parsed as Record<string, unknown>;
        }
      } catch {
        // Preserve the stable HTTP fallback when an intermediary returns HTML/text.
      }
      const backendMessage = String(errorPayload.error || errorPayload.message || '').trim();
      throw new BagoHttpError(
        response.status,
        backendMessage || `HTTP ${response.status} ${response.statusText}`,
        errorPayload
      );
    }
    if (response.status === 204) {
      return undefined as T;
    }
    const text = await response.text();
    if (!text) {
      return undefined as T;
    }
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new BagoHttpError(
        response.status,
        'La API de BAGO devolvió una respuesta no JSON. Comprueba la URL del backend.'
      );
    }
  }

  async bootstrap(): Promise<UiBootData> {
    // Canonical path: one atomic UI snapshot. Falls back to legacy parallel
    // reads only when the backend does not expose /api/v1/ui/bootstrap.
    return this.bootstrapModern().catch((error) => {
      if (!shouldFallbackToLegacy(error)) {
        throw error;
      }
      return this.bootstrapLegacy();
    });
  }

  async bootstrapLegacy(): Promise<UiBootData> {
    const [status, session, providers, menu, routes, history, conversations, files, evidence, jobs, schedule, routerList, routerPolicy] = await Promise.all([
      this.getStatus().catch(() => undefined),
      this.getSession().catch(() => undefined),
      this.getProviders().catch(() => undefined),
      this.getMenu().catch(() => undefined),
      this.getRoutes().catch(() => undefined),
      this.getHistory().catch(() => undefined),
      this.listConversations().catch(() => undefined),
      this.listFiles().catch(() => undefined),
      this.getEvidenceLatest().catch(() => undefined),
      this.listJobs().catch(() => undefined),
      this.listSchedule().catch(() => undefined),
      this.getRouterList().catch(() => undefined),
      this.getRouterPolicy().catch(() => undefined)
    ]);
    return { status, session, providers, menu, routes, history, conversations, files, evidence, jobs, schedule, router_list: routerList, router_policy: routerPolicy };
  }

  async bootstrapModern(): Promise<UiBootData> {
    return this.request<UiBootData>('/api/v1/ui/bootstrap', { method: 'GET' });
  }

  getStatus(): Promise<BackendStatus> {
    return this.request<BackendStatus>('/status', { method: 'GET' });
  }

  getSession(): Promise<BackendSession> {
    return this.request<BackendSession>('/session', { method: 'GET' });
  }

  getProviders(): Promise<BackendProviders> {
    return this.request<BackendProviders>('/providers', { method: 'GET' });
  }

  checkReleaseUpdate(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/release/check', { method: 'GET' }, 30_000);
  }

  getReleaseUpdateStatus(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/release/status', { method: 'GET' });
  }

  startReleaseUpdate(tag?: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/release/update', {
      method: 'POST',
      body: JSON.stringify(tag ? { tag } : {})
    }, 30_000);
  }

  applyReleaseUpdate(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/release/apply', {
      method: 'POST',
      body: JSON.stringify({})
    }, 30_000);
  }

  verifyProviderContracts(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/providers/contracts', { method: 'GET' });
  }

  getAutoConfigStatus(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/configure/auto/status', { method: 'GET' });
  }

  startAutoConfig(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/configure/auto/start', {
      method: 'POST',
      body: JSON.stringify({})
    }, 60_000);
  }

  applyAutoConfig(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/configure/auto/apply', {
      method: 'POST',
      body: JSON.stringify({})
    }, 60_000);
  }

  cancelAutoConfig(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/configure/auto/cancel', {
      method: 'POST',
      body: JSON.stringify({})
    }, 60_000);
  }

  getModelBlacklist(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/providers/blacklist', { method: 'GET' });
  }

  modifyModelBlacklist(payload: { action: 'add' | 'remove'; model: string; reason?: string }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/providers/blacklist', {
      method: 'POST',
      body: JSON.stringify(payload)
    }, 60_000);
  }

  getModels(provider: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/models/${encodeURIComponent(provider)}`, { method: 'GET' });
  }

  getActiveProviderModels(provider: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/providers/${encodeURIComponent(provider)}/active-models`, { method: 'GET' });
  }

  setActiveProviderModels(provider: string, models: string[]): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/providers/${encodeURIComponent(provider)}/active-models`, {
      method: 'POST',
      body: JSON.stringify({ models, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  detectProviderCli(tool: 'codex' | 'copilot'): Promise<{ installed: boolean; path: string | null; install_hint: string }> {
    return this.request(`/providers/cli-detect?tool=${encodeURIComponent(tool)}`, { method: 'GET' });
  }

  getMenu(): Promise<BackendMenu> {
    return this.request<BackendMenu>('/menu', { method: 'GET' });
  }

  getRoutes(): Promise<BackendRoutes> {
    return this.request<BackendRoutes>('/routes', { method: 'GET' });
  }

  getRouterList(refresh = false): Promise<BackendRouterList> {
    return this.request<BackendRouterList>(refresh ? '/router/list?refresh=1' : '/router/list', { method: 'GET' });
  }

  getRouterPolicy(): Promise<BackendRouterPolicy> {
    return this.request<BackendRouterPolicy>('/router/policy', { method: 'GET' });
  }

  toggleRouter(key: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/router/toggle/${encodeURIComponent(key)}`, {
      method: 'POST',
      body: JSON.stringify({ channel: 'ui-react', surface: 'ui-react' })
    });
  }

  setRouterAuto(enabled: boolean): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/router/auto', {
      method: 'POST',
      body: JSON.stringify({ enabled, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  getSessionModel(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/router/session-model', { method: 'GET' });
  }

  setSessionModel(modelKey: string | null): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/router/session-model', {
      method: 'POST',
      body: JSON.stringify({ model: modelKey, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  // CANON[WS-004]: Listar y persistir workspaces desde el frontend.
  listWorkspaces(): Promise<{ ok: boolean; workspaces: Array<{ path: string; name: string; is_current: boolean; id: string; binding_confirmed: boolean }>; count: number }> {
    return this.request('/workspace/list', { method: 'GET' });
  }

  getReasoningDepth(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/router/reasoning-depth', { method: 'GET' });
  }

  setReasoningDepth(depth: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/router/reasoning-depth', {
      method: 'POST',
      body: JSON.stringify({ depth, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  getGitHubStatus(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/github/status', { method: 'GET' });
  }

  connectGitHubRepository(repo: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/github/connect', { method: 'POST', body: JSON.stringify({ repo }) });
  }

  getGitHubContents(path = ''): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/github/contents?path=${encodeURIComponent(path)}`, { method: 'GET' });
  }

  createGitHubRepository(name: string, options: { private?: boolean; description?: string } = {}): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/github/create', { method: 'POST', body: JSON.stringify({ name, ...options }) });
  }

  createGitHubRepositoryViaMcp(name: string, options: { private?: boolean; description?: string; confirm: boolean }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/github/mcp-create', { method: 'POST', body: JSON.stringify({ name, ...options }) });
  }

  scopeWorkspaceConversation(root: string, conversationId?: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/workspace/conversation', { method: 'POST', body: JSON.stringify({ root, conversation_id: conversationId }) });
  }

  listConversations(): Promise<import('@/contracts/backend').BackendConversations> {
    return this.request('/conversations', { method: 'GET' });
  }

  createConversation(title?: string): Promise<import('@/contracts/backend').BackendConversations> {
    return this.request('/conversations', { method: 'POST', body: JSON.stringify({ action: 'create', title: title || 'Nuevo chat' }) });
  }

  switchConversation(conversationId: string): Promise<import('@/contracts/backend').BackendConversations> {
    return this.request('/conversations', { method: 'POST', body: JSON.stringify({ action: 'switch', conversation_id: conversationId }) });
  }

  renameConversation(conversationId: string, title: string): Promise<import('@/contracts/backend').BackendConversations> {
    return this.request('/conversations', { method: 'POST', body: JSON.stringify({ action: 'rename', conversation_id: conversationId, title }) });
  }

  archiveConversation(conversationId: string): Promise<import('@/contracts/backend').BackendConversations> {
    return this.request('/conversations', { method: 'POST', body: JSON.stringify({ action: 'archive', conversation_id: conversationId }) });
  }

  browseWorkspace(path?: string): Promise<{
    ok: boolean;
    path: string;
    parent: string;
    roots: Array<{ label: string; path: string }>;
    recent: Array<{ label: string; path: string }>;
    breadcrumbs: Array<{ label: string; path: string }>;
    directories: Array<{ name: string; path: string }>;
    truncated?: boolean;
  }> {
    const query = path?.trim() ? `?path=${encodeURIComponent(path.trim())}` : '';
    return this.request(`/workspace/browse${query}`, { method: 'GET' });
  }

  persistWorkspace(path?: string): Promise<{ ok: boolean; saved: string }> {
    const body: Record<string, unknown> = {};
    if (path) body.path = path;
    return this.request('/workspace/persist', {
      method: 'POST',
      body: JSON.stringify(body)
    });
  }

  configureProvider(provider: string, config: { enabled?: boolean; base_url?: string; api_key?: string; model?: string }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/providers/configure', {
      method: 'POST',
      body: JSON.stringify({ provider, ...config, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  // --- Audit ---
  getAuditProject(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/audit/project', { method: 'GET' });
  }
  getAuditBago(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/audit/bago', { method: 'GET' });
  }
  getAuditLedger(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/audit/ledger', { method: 'GET' });
  }

  // --- Simulation ---
  getSimulationStatus(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/simulation/status', { method: 'GET' });
  }
  getSimulationEvents(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/simulation/events', { method: 'GET' });
  }
  setSimulationConfig(config: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/simulation/config', {
      method: 'POST',
      body: JSON.stringify({ ...config, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  // --- RL (experimental) ---
  getRlStatus(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/rl/status', { method: 'GET' });
  }
  setRlShadow(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/rl/shadow', {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  testProvider(provider: string, config: { base_url?: string; api_key?: string; model?: string }): Promise<{ ok: boolean; provider?: string; model?: string; detail?: string }> {
    return this.request('/providers/test', {
      method: 'POST',
      body: JSON.stringify({ provider, ...config, channel: 'ui-react', surface: 'first-run' })
    });
  }

  listCapabilities(): Promise<CapabilityListResponse> {
    return this.request<CapabilityListResponse>('/api/v1/capabilities', { method: 'GET' });
  }

  getCapability(capabilityId: string): Promise<CapabilitySnapshot> {
    return this.request<CapabilitySnapshot>(`/api/v1/capabilities/${encodeURIComponent(capabilityId)}`, { method: 'GET' });
  }
  trainRlBc(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/rl/train-bc', {
      method: 'POST',
      body: JSON.stringify({ channel: 'ui-react', surface: 'ui-react' })
    });
  }
  evalRlPolicy(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/rl/eval', {
      method: 'POST',
      body: JSON.stringify({ channel: 'ui-react', surface: 'ui-react' })
    });
  }

  // --- Agents ---
  listAgents(): Promise<{ ok: boolean; agents: import('@/contracts/backend').AgentConfig[] }> {
    return this.request('/agents', { method: 'GET' });
  }

  getAgent(id: string): Promise<import('@/contracts/backend').AgentConfig> {
    return this.request(`/agents/${encodeURIComponent(id)}`, { method: 'GET' });
  }

  createAgent(payload: Omit<import('@/contracts/backend').AgentConfig, 'id' | 'revision' | 'createdAt' | 'updatedAt'>): Promise<import('@/contracts/backend').AgentConfig> {
    return this.request('/agents', { method: 'POST', body: JSON.stringify(payload) });
  }

  updateAgent(id: string, payload: import('@/contracts/backend').AgentUpdateRequest): Promise<import('@/contracts/backend').AgentConfig> {
    return this.request(`/agents/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(payload) });
  }

  deleteAgent(id: string): Promise<void> {
    return this.request(`/agents/${encodeURIComponent(id)}`, { method: 'DELETE' });
  }

  duplicateAgent(id: string): Promise<import('@/contracts/backend').AgentConfig> {
    return this.request(`/agents/${encodeURIComponent(id)}/duplicate`, { method: 'POST', body: JSON.stringify({}) });
  }

  testAgent(id: string): Promise<import('@/contracts/backend').AgentTestResult> {
    return this.request(`/agents/${encodeURIComponent(id)}/test`, { method: 'POST', body: JSON.stringify({}) }, 60_000);
  }

  // --- Interpretations ---
  createInterpretation(payload: import('@/contracts/backend').InterpretationRequest): Promise<import('@/contracts/backend').InterpretationResult> {
    return this.request('/interpretations', { method: 'POST', body: JSON.stringify(payload) }, 60_000);
  }

  getInterpretation(id: string): Promise<import('@/contracts/backend').InterpretationResult> {
    return this.request(`/interpretations/${encodeURIComponent(id)}`, { method: 'GET' });
  }

  listInterpretations(): Promise<{ ok: boolean; interpretations: import('@/contracts/backend').InterpretationResult[] }> {
    return this.request('/interpretations', { method: 'GET' });
  }

  cancelInterpretation(id: string): Promise<void> {
    return this.request(`/interpretations/${encodeURIComponent(id)}/cancel`, { method: 'POST', body: JSON.stringify({}) });
  }

  // --- GitHub Auth ---
  getGitHubAuthStatus(): Promise<import('@/contracts/backend').GitHubAuthState> {
    return this.request('/github/status', { method: 'GET' });
  }

  startGitHubAuth(): Promise<{ auth_url: string }> {
    return this.request('/github/auth/start', { method: 'POST', body: JSON.stringify({}) });
  }

  refreshGitHubAuth(): Promise<import('@/contracts/backend').GitHubAuthState> {
    return this.request('/github/auth/refresh', { method: 'POST', body: JSON.stringify({}) });
  }

  logoutGitHub(): Promise<void> {
    return this.request('/github/auth/logout', { method: 'POST', body: JSON.stringify({}) });
  }

  setupGitHub(options: { hostname?: string; token?: string }): Promise<import('@/contracts/backend').GitHubAuthState> {
    return this.request('/github/setup', { method: 'POST', body: JSON.stringify(options) });
  }

  // --- Pipeline ---
  listPlans(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/plans', { method: 'GET' });
  }

  createPlan(task: string, autoExecute = false): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/plans', {
      method: 'POST',
      body: JSON.stringify({ task, auto_execute: autoExecute, channel: 'ui-react', surface: 'ui-react' })
    }, 60_000);
  }

  executePlan(planId: string, payload?: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/plans/${encodeURIComponent(planId)}/execute`, {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    }, 60_000);
  }

  // --- Catalog & Provider Buffer ---
  getCatalogStatus(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/catalog/status', { method: 'GET' });
  }

  getProviderBufferStatus(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/provider/buffer/status', { method: 'GET' });
  }

  prepareProviderBuffer(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/provider/buffer/prepare', {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    }, 60_000);
  }

  unloadProviderBuffer(modelName?: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(modelName ? `/provider/buffer/unload/${encodeURIComponent(modelName)}` : '/provider/buffer/unload', {
      method: 'POST',
      body: JSON.stringify({ channel: 'ui-react', surface: 'ui-react' })
    });
  }

  analyzeVision(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/vision', {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    }, 60_000);
  }

  // --- Capability Packages ---
  listCapabilityPackages(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/api/v1/capability-packages', { method: 'GET' });
  }

  listCapabilityReceipts(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/api/v1/capability-packages/receipts', { method: 'GET' });
  }


  listCapabilityExamples(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/api/v1/capability-packages/examples', { method: 'GET' });
  }

  installCapabilityExample(packageId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/api/v1/capability-packages/${encodeURIComponent(packageId)}/install-example`, {
      method: 'POST',
      body: JSON.stringify({ channel: 'ui-react', surface: 'ui-react' })
    });
  }

  inspectCapabilityPackage(fileName: string, contentBase64: string): Promise<PackageInspection> {
    return this.request<PackageInspection>('/api/v1/capability-packages/inspect', {
      method: 'POST',
      body: JSON.stringify({ file_name: fileName, content_base64: contentBase64, channel: 'ui-react', surface: 'ui-react' })
    }, 60_000);
  }

  importCapabilityPackage(payload: { fileName: string; contentBase64: string; confirmTrust?: boolean }): Promise<CapabilityPackageResponse> {
    return this.request<CapabilityPackageResponse>('/api/v1/capability-packages/import', {
      method: 'POST',
      body: JSON.stringify({
        file_name: payload.fileName,
        content_base64: payload.contentBase64,
        confirm_trust: payload.confirmTrust === true,
        channel: 'ui-react',
        surface: 'ui-react'
      })
    }, 60_000);
  }

  exportCapabilityPackage(packageId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/api/v1/capability-packages/${encodeURIComponent(packageId)}/export`, { method: 'GET' });
  }

  setCapabilityPackageEnabled(packageId: string, enabled: boolean, confirmTrust = false): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/api/v1/capability-packages/${encodeURIComponent(packageId)}/enable`, {
      method: 'POST',
      body: JSON.stringify({ enabled, confirm_trust: confirmTrust, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  configureCapabilityPackage(packageId: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/api/v1/capability-packages/${encodeURIComponent(packageId)}/configure`, {
      method: 'POST',
      body: JSON.stringify({ config: payload, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  executeCapabilityPackage(packageId: string, payload?: Record<string, unknown>): Promise<CapabilityExecutionResponse> {
    return this.request<CapabilityExecutionResponse>(`/api/v1/capability-packages/${encodeURIComponent(packageId)}/execute`, {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    }, 60_000);
  }
  listMemory(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/memory/list', { method: 'GET' });
  }
  getMemoryStatus(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/memory/status', { method: 'GET' });
  }
  searchMemory(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/memory/search', { method: 'POST', body: JSON.stringify(payload) });
  }
  upsertEmbedding(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/memory/embeddings/upsert', { method: 'POST', body: JSON.stringify(payload) });
  }
  getSubagentsCatalogue(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/subagents/catalogue', { method: 'GET' });
  }

  // --- Interpret ---
  getInterpretHistory(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/interpret/history', { method: 'GET' });
  }
  getInterpretRules(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/interpret/rules', { method: 'GET' });
  }
  postInterpret(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/interpret', {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  // --- Switch / Catalog ---
  switchProvider(payload: { provider?: string; model?: string; mode?: string }): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/switch', {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    }, 60_000);
  }
  setCatalogConfig(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/catalog/config', {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  // --- Routes (already in bootstrap but exposed for the System tab) ---
  getRoutesFresh(): Promise<BackendRoutes> {
    return this.request<BackendRoutes>('/routes', { method: 'GET' });
  }

  getHistory(): Promise<BackendHistory> {
    return this.request<BackendHistory>('/history', { method: 'GET' });
  }

  listFiles(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/files/list', { method: 'GET' });
  }

  listSources(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/sources', { method: 'GET' });
  }

  manageSource(action: 'add' | 'remove', path: string, label?: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/sources', {
      method: 'POST',
      body: JSON.stringify({ action, path, label, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  addSource(path: string, label?: string): Promise<Record<string, unknown>> {
    return this.manageSource('add', path, label);
  }

  removeSource(path: string): Promise<Record<string, unknown>> {
    return this.manageSource('remove', path);
  }

  getEvidenceLatest(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/evidence/latest', { method: 'GET' });
  }

  listEvidenceClaims(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/evidence/claims', { method: 'GET' });
  }

  listEvidenceReceipts(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/evidence/receipts', { method: 'GET' });
  }

  getEvidenceReceipt(receiptId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/evidence/receipts/${encodeURIComponent(receiptId)}`, { method: 'GET' });
  }

  getEvidenceClaim(claimId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/evidence/claims/${encodeURIComponent(claimId)}`, { method: 'GET' });
  }

  listJobs(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/jobs/list', { method: 'GET' });
  }

  getJob(executionId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/jobs/${encodeURIComponent(executionId)}`, { method: 'GET' });
  }

  cancelJob(executionId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/jobs/${encodeURIComponent(executionId)}/cancel`, { method: 'POST' });
  }

  retryJob(executionId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/jobs/${encodeURIComponent(executionId)}/retry`, { method: 'POST' });
  }

  listSchedule(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/schedule/list', { method: 'GET' });
  }

  createSchedule(payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/schedule', {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  updateSchedule(scheduleId: string, payload: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/schedule/${encodeURIComponent(scheduleId)}`, {
      method: 'POST',
      body: JSON.stringify({ ...payload, channel: 'ui-react', surface: 'ui-react' })
    });
  }

  runSchedule(scheduleId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/schedule/${encodeURIComponent(scheduleId)}/run`, {
      method: 'POST',
      body: '{}'
    }, 60_000);
  }

  deleteSchedule(scheduleId: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>(`/schedule/${encodeURIComponent(scheduleId)}/delete`, {
      method: 'POST',
      body: '{}'
    });
  }

  readFile(filePath: string, options: { optional?: boolean } = {}): Promise<Record<string, unknown>> {
    const query = options.optional ? '?optional=1' : '';
    return this.request<Record<string, unknown>>(`/files/read/${encodeURIComponent(filePath)}${query}`, { method: 'GET' });
  }

  writeFile(path: string, content: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/files/write', {
      method: 'POST',
      body: JSON.stringify({ path, content }),
    });
  }

  private projectBody(root?: string): string {
    return JSON.stringify(root ? { root, channel: 'ui-react', surface: 'ui-react' } : { channel: 'ui-react', surface: 'ui-react' });
  }

  getProjectStatus(): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/project/status', { method: 'GET' });
  }

  getProjectAnalyze(): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/project/analyze', { method: 'GET' });
  }

  initProject(root?: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/project/init', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  // Lee el estado REAL del filesystem en `root` sin tocar el session manager.
  // La UI lo usa antes de ofrecer "Sembrar y activar" para detectar workspaces
  // ya inicializados.
  async inspectProject(root: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/project/inspect', {
      method: 'POST',
      body: JSON.stringify({ root, channel: 'ui-react' })
    });
  }

  linkProject(root: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/project/link', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  seedProject(root: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/project/seed', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  syncProject(root?: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/project/sync', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  runCommand(command: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/api/v1/commands', {
      method: 'POST',
      body: JSON.stringify({ command, channel: 'ui-react', surface: 'ui-react' })
    }, 150_000);
  }

  async sendChat(message: string): Promise<Record<string, unknown>> {
    const body = JSON.stringify({ message, channel: 'ui-react', surface: 'ui-react' });
    return this.request<Record<string, unknown>>('/chat', {
      method: 'POST',
      body
    }, 150_000);
  }

  createDemoProject(root: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/project/demo', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  async sendInternalChat(message: string): Promise<Record<string, unknown>> {
    const body = JSON.stringify({ message, internal: true, channel: 'ui-react', surface: 'context-internal' });
    return this.request<Record<string, unknown>>('/chat', { method: 'POST', body }, 150_000);
  }

  async streamChat(
    message: string,
    onChunk: (chunk: string) => void
  ): Promise<Record<string, unknown>> {
    const response = await fetch(this.url('/chat/stream'), {
      method: 'POST',
      headers: this.headers(),
      body: JSON.stringify({ message, channel: 'ui-react' })
    });
    if (!response.ok || !response.body) {
      return this.sendChat(message);
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalPayload: Record<string, unknown> = {};
    let fullText = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let index = buffer.indexOf('\n\n');
      while (index >= 0) {
        const packet = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 2);
        index = buffer.indexOf('\n\n');
        if (!packet.startsWith('data:')) {
          continue;
        }
        const payloadText = packet.slice(5).trim();
        if (!payloadText) continue;
        try {
          const payload = JSON.parse(payloadText) as Record<string, unknown>;
          if (typeof payload.chunk === 'string') {
            onChunk(payload.chunk);
            fullText += payload.chunk;
          }
          finalPayload = { ...finalPayload, ...payload };
        } catch {
          // ignore malformed packet
        }
      }
    }
    return { ...finalPayload, response: fullText || finalPayload.response || finalPayload.message || '' };
  }

  async streamEvents(
    onEvent: (eventName: string, payload: Record<string, unknown>) => void
  ): Promise<void> {
    const response = await fetch(this.modernUrl('/events'), {
      method: 'GET',
      headers: this.headers()
    });
    if (!response.ok || !response.body) {
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let index = buffer.indexOf('\n\n');
      while (index >= 0) {
        const packet = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 2);
        index = buffer.indexOf('\n\n');
        if (!packet) continue;
        const lines = packet.split('\n');
        const eventLine = lines.find((line) => line.startsWith('event:'));
        const dataLine = lines.find((line) => line.startsWith('data:'));
        if (!dataLine) continue;
        const eventName = eventLine ? eventLine.slice(6).trim() : 'message';
        const payloadText = dataLine.slice(5).trim();
        if (!payloadText) continue;
        try {
          onEvent(eventName, JSON.parse(payloadText) as Record<string, unknown>);
        } catch {
          onEvent(eventName, { raw: payloadText });
        }
      }
    }
  }
}

export function createBagoClient(apiBase: string, apiToken: string): BagoClient {
  return new BagoClient(apiBase.trim().replace(/\/+$/, ''), apiToken);
}

export function jsonToText(value: unknown): string {
  if (value === undefined) return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function safeJson(value: unknown): JsonValue {
  if (value === null) return null;
  if (Array.isArray(value)) return value.map((entry) => safeJson(entry)) as Array<unknown>;
  if (typeof value === 'object' && value) {
    const out: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
      out[key] = safeJson(entry);
    }
    return out;
  }
  if (['string', 'number', 'boolean'].includes(typeof value)) {
    return value as string | number | boolean;
  }
  return null;
}
