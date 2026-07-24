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

  constructor(status: number, message: string) {
    super(message);
    this.name = 'BagoHttpError';
    this.status = status;
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
      throw new BagoHttpError(response.status, `HTTP ${response.status} ${response.statusText}`);
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
    const [status, session, providers, menu, routes, history, files, evidence, jobs, schedule, routerList, routerPolicy] = await Promise.all([
      this.getStatus().catch(() => undefined),
      this.getSession().catch(() => undefined),
      this.getProviders().catch(() => undefined),
      this.getMenu().catch(() => undefined),
      this.getRoutes().catch(() => undefined),
      this.getHistory().catch(() => undefined),
      this.listFiles().catch(() => undefined),
      this.getEvidenceLatest().catch(() => undefined),
      this.listJobs().catch(() => undefined),
      this.listSchedule().catch(() => undefined),
      this.getRouterList().catch(() => undefined),
      this.getRouterPolicy().catch(() => undefined)
    ]);
    return { status, session, providers, menu, routes, history, files, evidence, jobs, schedule, router_list: routerList, router_policy: routerPolicy };
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

  verifyProviderContracts(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/providers/contracts', { method: 'GET' });
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

  // --- Memory & Subagents ---
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

  initWorkspace(root?: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/workspace/init', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  linkWorkspace(root: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/workspace/link', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  seedWorkspace(root: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/workspace/seed', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  syncWorkspace(root?: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/workspace/sync', {
      method: 'POST',
      body: this.projectBody(root)
    });
  }

  runCommand(command: string): Promise<BackendCommandResult> {
    const body = JSON.stringify({ command, channel: 'ui-react', surface: 'ui-react' });
    return this.request<BackendCommandResult>('/api/v1/commands', {
      method: 'POST',
      body
    }, 150_000).catch((error) => {
      if (!shouldFallbackToLegacy(error)) {
        throw error;
      }
      return this.request<BackendCommandResult>('/command', {
        method: 'POST',
        body
      }, 150_000);
    });
  }

  runCommandLegacy(command: string): Promise<BackendCommandResult> {
    return this.request<BackendCommandResult>('/command', {
      method: 'POST',
      body: JSON.stringify({ command, channel: 'ui-react' })
    }, 150_000);
  }

  async sendChat(message: string): Promise<Record<string, unknown>> {
    const body = JSON.stringify({ message, channel: 'ui-react', surface: 'ui-react' });
    return this.request<Record<string, unknown>>('/chat', {
      method: 'POST',
      body
    }, 150_000);
  }

  async sendChatModern(message: string): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>('/api/v1/commands', {
      method: 'POST',
      body: JSON.stringify({ command: 'chat', message, channel: 'ui-react', surface: 'ui-react' })
    });
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
          }
          finalPayload = payload;
        } catch {
          // ignore malformed packet
        }
      }
    }
    return finalPayload;
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
