import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
import type { BagoClient } from '@/api/client';
import type { ActiveSection, BackendCommandResult, BackendHistory, BackendMenu, BackendProviders, BackendRouterList, BackendRouterPolicy, BackendRoutes, ChatTurn, InspectorLevel, SelectionRecord, UiAction, UiBootstrapSnapshot } from '@/contracts/backend';
import { createBagoClient, persistApiConfig, readStoredApiBase, resolveDefaultApiBase, safeJson } from '@/api/client';
import { GlobalHeader } from '@/layout/GlobalHeader';
import { MainSidebar } from '@/layout/MainSidebar';
import { WorkspaceShell } from '@/layout/WorkspaceShell';
import { ContextMenu } from '@/layout/ContextMenu';
import { InspectorDrawer } from '@/layout/InspectorDrawer';
import { createContextActions } from '@/features/context-menu/contextActions';
import { ControlSections } from '@/features/sections';
import { resolveOpeningState } from '@/features/opening/opening';
import { createDefaultUiState, loadUiState, patchUiState, persistUiState, type UiState } from '@/state/uiStore';
import { Icon } from '@/shared/Icon';
import { useContextTree, type UseContextTreeState } from '@/features/context-tree/useContextTree';
import { parseContextPatchRequests } from '@/features/context-tree/parseContextPatchRequests';
import type { ContextPatchRequest } from '@/features/context-tree/contextTreeTypes';

function nowStamp(): string {
  return new Date().toISOString();
}

// CANON[CTX-004]: Hash determinista y muy corto para identificar un
// patch emitido por el chat. Usado para deduplicar el mismo bloque a
// lo largo de renders y para etiquetar receipts de manera estable.
function hashString(input: string): string {
  let hash = 5381;
  for (let i = 0; i < input.length; i += 1) {
    hash = ((hash << 5) + hash) + input.charCodeAt(i);
    hash = hash & 0x7fffffff;
  }
  return hash.toString(36);
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((entry) => String(entry)).filter(Boolean);
}

function toNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function toBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined;
}

function readText(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((entry) => entry && typeof entry === 'object' && !Array.isArray(entry)) as Array<Record<string, unknown>> : [];
}

function extractRecordArray(value: unknown, keys: string[]): Array<Record<string, unknown>> {
  if (Array.isArray(value)) {
    return asRecordArray(value);
  }
  if (!value || typeof value !== 'object') {
    return [];
  }
  const data = value as Record<string, unknown>;
  for (const key of keys) {
    const candidate = data[key];
    if (Array.isArray(candidate)) {
      return asRecordArray(candidate);
    }
  }
  return [];
}

function readReceiptId(receipt: unknown): string | undefined {
  if (!receipt || typeof receipt !== 'object') return undefined;
  const data = receipt as Record<string, unknown>;
  return readText(data.envelope_id || data.id || data.receipt_id);
}

function readCertificationStatus(value: unknown): string | undefined {
  if (!value || typeof value !== 'object') return undefined;
  const data = value as Record<string, unknown>;
  return readText(data.status || data.state);
}

function readRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function readStringRecord(value: unknown): Record<string, string> {
  return Object.fromEntries(
    Object.entries(readRecord(value)).map(([key, entry]) => [key, String(entry || '')])
  );
}

function readMenuStateValue(raw: any): Record<string, unknown> {
  return readRecord(raw?.menu_state || raw?.session?.menu_state || raw?.status?.menu_state);
}

function readMenuStateText(value: unknown): string {
  return String(value || '').trim();
}

function shouldOfferSeed(snapshot: UiBootstrapSnapshot | null, selectedRoot: string): boolean {
  const cleanRoot = selectedRoot.trim();
  if (!cleanRoot || !snapshot) return false;
  const currentRoot = String(snapshot.project.root || snapshot.workspace.repoRoot || snapshot.workspace.root || '').trim();
  if (currentRoot && currentRoot === cleanRoot && snapshot.workspace.linkedToSession && snapshot.workspace.manifestState === 'valid') {
    return false;
  }
  return Boolean(
    snapshot.workspace.seedSuggested
    || snapshot.workspace.manifestState !== 'valid'
    || !snapshot.workspace.linkedToSession
    || currentRoot !== cleanRoot
  );
}

type WorkspaceSelectionResult = {
  ok?: boolean;
  canceled?: boolean;
  path?: string;
  filePath?: string;
  filePaths?: string[];
  message?: string;
};

function getElectronBridge() {
  return typeof window === 'undefined' ? undefined : window.bagoElectron;
}

function readSelectedWorkspace(result: WorkspaceSelectionResult | null | undefined): string {
  if (!result || result.canceled === true) return '';
  return String(result.path || result.filePath || (Array.isArray(result.filePaths) ? result.filePaths[0] : '') || '').trim();
}

function normalizeWorkspaceHint(value: string): string {
  const clean = String(value || '').trim().replace(/[\\/]+$/, '');
  if (!clean) return '';
  const normalized = clean.replace(/\//g, '\\');
  const lower = normalized.toLowerCase();
  if (lower.endsWith('\\.gabo') || lower.endsWith('\\.bago')) {
    return normalized.slice(0, normalized.lastIndexOf('\\'));
  }
  if (lower === '.gabo' || lower === '.bago') {
    return '';
  }
  return clean;
}

function normalizeActions(snapshot: UiBootstrapSnapshot | null): UiAction[] {
  const actions: UiAction[] = [];
  if (!snapshot) return actions;
  const enabled = snapshot.permissions.canChat;
  actions.push({
    id: 'open-chat',
    label: 'Open chat',
    kind: 'navigate',
    enabled,
    visible: true,
    reasonDisabled: enabled ? undefined : 'Backend is not ready for chat',
    payload: { section: 'chat' }
  });
  actions.push({
    id: 'inspect-system',
    label: 'Inspect system',
    kind: 'inspect',
    enabled: true,
    visible: true,
    payload: { command: '/status' }
  });
  if (snapshot.permissions.canInspectContext) {
    actions.push({
      id: 'inspect-context',
      label: 'Inspect context',
      kind: 'inspect',
      enabled: true,
      visible: true,
      payload: { command: '/context inspect' }
    });
  }
  if (snapshot.permissions.canViewEvidence) {
    actions.push({
      id: 'view-evidence',
      label: 'Review evidence',
      kind: 'navigate',
      enabled: true,
      visible: true,
      payload: { section: 'evidence' }
    });
  }
  if (snapshot.workspace.manifestState === 'missing') {
    actions.push({
      id: 'workspace-init',
      label: 'Initialize workspace',
      kind: 'mutation',
      enabled: snapshot.permissions.canInitializeWorkspace,
      visible: true,
      reasonDisabled: snapshot.permissions.canInitializeWorkspace ? undefined : 'Not allowed by backend',
      payload: { endpoint: 'project:init' }
    });
  }
  if (snapshot.permissions.canLinkWorkspace && snapshot.workspace.root) {
    actions.push({
      id: 'workspace-link',
      label: 'Link workspace',
      kind: 'mutation',
      enabled: true,
      visible: true,
      payload: { endpoint: 'project:link', root: snapshot.project.root || snapshot.workspace.repoRoot || snapshot.workspace.root }
    });
  }
  if (snapshot.workspace.manifestState === 'invalid') {
    actions.push({
      id: 'workspace-repair',
      label: 'Repair workspace',
      kind: 'danger',
      enabled: snapshot.permissions.canRepairWorkspace,
      visible: true,
      reasonDisabled: snapshot.permissions.canRepairWorkspace ? undefined : 'Repair disabled',
      payload: { endpoint: 'project:init' }
    });
  }
  return actions;
}

function commandKey(command: string): string {
  return command.trim().replace(/^\/+/, '').replace(/[^\w]+/g, '_').replace(/^_+|_+$/g, '') || 'command';
}

function buildSnapshot(raw: any): UiBootstrapSnapshot | null {
  if (!raw) return null;
  const status = raw.status || {};
  const session = raw.session || {};
  const menuStateRaw = readMenuStateValue(raw);
  const workspaceMeta = raw.workspace || {};
  const binding = session.binding || {};
  const projectRoot = String(status.project_root || status.repo_root || binding.project_root || '');
  const workspaceRoot = String(status.workspace_state_root || session.binding?.workspace_state_root || '');
  const scopeRoot = String(status.workspace_scope_root || binding.workspace_scope_root || projectRoot || '');
  const mirrorRoot = String(status.workspace_mirror_root || binding.workspace_mirror_root || '');
  const contextRoot = String(status.workspace_context_root || binding.workspace_context_root || '');
  const authorizedRoot = String(status.authorized_root || binding.authorized_root || scopeRoot || '');
  const repoRoot = String(status.repo_root || binding.repo_root || projectRoot || '');
  const repoBranch = String(status.repo_branch || binding.repo_branch || '');
  const activeBridges = toStringList(status.active_bridges || session.active_bridges);
  const bindingConfirmed = Boolean(
    status.workspace_state?.binding_confirmed
    || session.workspace_state?.binding_confirmed
    || binding.binding_confirmed
    || status.binding_confirmed
  );
  const bindingReason = String(
    status.workspace_state?.binding_reason
    || session.workspace_state?.binding_reason
    || binding.binding_reason
    || status.binding_reason
    || ''
  );
  const workspaceState = String(status.workspace_state || session.workspace_state?.workspace_state || '');
  const seedSuggested = Boolean(workspaceMeta.seed_suggested);
  const seedReason = String(workspaceMeta.seed_reason || '');
  const manifestState: UiBootstrapSnapshot['workspace']['manifestState'] = workspaceState.includes('legacy')
    ? 'legacy'
    : workspaceState.includes('invalid')
      ? 'invalid'
      : workspaceState.includes('missing')
        ? 'missing'
        : bindingConfirmed
          ? 'valid'
          : workspaceRoot
            ? 'unknown'
            : 'missing';
  const health = status.health || {};
  const healthDetail = readText(health.detail);
  const healthLatencyMs = toNumber(health.latency_ms);
  const objective = String(status.objective || binding.objective || '');
  const activeAgent = String(status.active_agent || session.active_agent || '');
  const lastEnvelope = readRecord(raw.last_envelope);
  const lastEnvelopeMeta = readRecord(lastEnvelope.metadata);
  const lastReceipt = readRecord(raw.last_receipt);
  const lastReceiptMeta = readRecord(lastReceipt.metadata);
  const codeTaskClassification = readRecord(status.code_task || lastEnvelopeMeta.code_task || lastReceiptMeta.code_task);
  const codeTaskContract = readRecord(status.code_task_contract || lastEnvelopeMeta.code_task_contract || lastReceiptMeta.code_task_contract);
  const codeTaskContext = readRecord(lastEnvelopeMeta.code_context || lastReceiptMeta.code_context);
  const lastReceiptId = readReceiptId(status.last_receipt);
  const certificationStatus = readCertificationStatus(status.context_certification);
  const menuState = {
    activeCenter: readMenuStateText(menuStateRaw.activeCenter || status.active_center || session.active_center),
    currentScreen: readMenuStateText(menuStateRaw.currentScreen || status.current_screen || session.current_screen),
    operationState: readMenuStateText(menuStateRaw.operationState || status.operation_state || session.operation_state),
    recommendedAction: readMenuStateText(menuStateRaw.recommendedAction || status.recommended_action || session.recommended_action),
    allowedActions: toStringList(menuStateRaw.allowedActions || status.allowed_actions || session.allowed_actions),
    secondaryActions: toStringList(menuStateRaw.secondaryActions || status.secondary_actions || session.secondary_actions),
    blockedActions: toStringList(menuStateRaw.blockedActions || status.blocked_actions || session.blocked_actions),
    blockedReasons: readStringRecord(menuStateRaw.blockedReasons || status.blocked_reasons || session.blocked_reasons),
    pendingWork: readMenuStateText(menuStateRaw.pendingWork || status.pending_work || session.pending_work),
    latestResult: readMenuStateText(menuStateRaw.latestResult || status.latest_result || session.latest_result),
    version: readMenuStateText(menuStateRaw.version || status.contract_version || status.schema_version || raw.version)
  };
  const rawPermissions = readRecord(raw.permissions);
  const systemState: UiBootstrapSnapshot['system']['state'] = health.ok === false
    ? 'error'
    : bindingConfirmed ? 'confirmed'
      : bindingReason ? 'degraded'
        : !raw.status
          ? 'loading'
          : 'unknown';
  const contextRevision = status.context_revision ?? session.status?.context_revision;
  const contextState: UiBootstrapSnapshot['context']['state'] = certificationStatus === 'CERTIFIED'
    ? 'confirmed'
    : contextRevision && lastReceiptId
      ? 'partial'
      : contextRevision
        ? 'stale'
        : bindingConfirmed
          ? 'unknown'
          : 'blocked';
  const explicitModelState = String(status.model_state || '').toLowerCase();
  const modelState: UiBootstrapSnapshot['model']['state'] = explicitModelState === 'error'
    ? 'error'
    : explicitModelState === 'degraded'
      ? 'degraded'
      : (status.provider || session.provider) && (status.model || session.model || status.effective_model)
        ? 'confirmed'
        : 'unknown';
  const effectiveProvider = String(status.provider || session.provider || '');
  const effectiveModel = String(status.model || session.model || status.effective_model || '');
  const permissions = {
    canChat: toBoolean(rawPermissions.canChat) ?? (bindingConfirmed && Boolean(effectiveProvider) && Boolean(effectiveModel)),
    canInitializeWorkspace: toBoolean(rawPermissions.canInitializeWorkspace) ?? !workspaceRoot,
    canLinkWorkspace: toBoolean(rawPermissions.canLinkWorkspace) ?? (Boolean(workspaceRoot) && !bindingConfirmed),
    canRepairWorkspace: toBoolean(rawPermissions.canRepairWorkspace) ?? (Boolean(workspaceRoot) && /manifest|workspace root|scope|legacy|invalid/i.test(bindingReason || workspaceState)),
    canSeedWorkspace: toBoolean(rawPermissions.canSeedWorkspace) ?? Boolean(workspaceRoot),
    canRunTools: toBoolean(rawPermissions.canRunTools) ?? (bindingConfirmed && activeBridges.length > 0),
    canInspectContext: toBoolean(rawPermissions.canInspectContext) ?? (bindingConfirmed && Boolean(contextRevision || lastReceiptId)),
    canViewEvidence: toBoolean(rawPermissions.canViewEvidence) ?? Boolean(lastReceiptId || (Array.isArray(raw.history?.messages) && raw.history.messages.length)),
    canStopPipeline: toBoolean(rawPermissions.canStopPipeline) ?? Boolean(objective || contextRevision),
    canRetryPipeline: toBoolean(rawPermissions.canRetryPipeline) ?? Boolean(objective || lastReceiptId || contextRevision)
  };
  const sessionState: UiBootstrapSnapshot['session']['state'] = session.session_id
    ? (bindingConfirmed
      ? 'valid'
      : /manifest|workspace root|scope|legacy|invalid/i.test(bindingReason) ? 'blocked' : 'recoverable')
    : 'missing';
  const codeTask = Object.keys(codeTaskClassification).length || Object.keys(codeTaskContract).length || Object.keys(codeTaskContext).length
    ? ({
      classification: Object.keys(codeTaskClassification).length ? codeTaskClassification : undefined,
      contract: Object.keys(codeTaskContract).length ? codeTaskContract : undefined,
      context: Object.keys(codeTaskContext).length ? codeTaskContext : undefined
    } as UiBootstrapSnapshot['codeTask'])
    : undefined;

  const snapshot: UiBootstrapSnapshot = {
    system: {
      state: systemState,
      backendAvailable: true,
      version: String(status.framework_version || status.version || ''),
      apiVersion: String(status.api_version || ''),
      contractVersion: String(status.contract_version || ''),
      schemaVersion: String(status.schema_version || ''),
      healthDetail: healthDetail || undefined,
      healthLatencyMs,
      bindingReason: bindingReason || undefined,
      objective: objective || undefined,
      activeAgent: activeAgent || undefined,
      activeBridges: activeBridges.length ? activeBridges : undefined,
      errorCode: readText(status.error_code || status.health?.error_code || '')
    },
    framework: {
      root: String(status.framework_root || ''),
      version: String(status.framework_version || status.version || ''),
      confirmed: Boolean(status.framework_root),
    },
    project: {
      root: projectRoot || undefined,
      state: projectRoot ? 'confirmed' : 'not_detected'
    },
    workspace: {
      id: String(status.workspace_id || session.binding?.workspace_id || ''),
      root: workspaceRoot || undefined,
      scopeRoot: scopeRoot || undefined,
      mirrorRoot: mirrorRoot || undefined,
      contextRoot: contextRoot || undefined,
      authorizedRoot: authorizedRoot || undefined,
      repoRoot: repoRoot || undefined,
      repoBranch: repoBranch || undefined,
      bindingReason: bindingReason || undefined,
      mirrorReady: Boolean(status.workspace_mirror_ready),
      manifestState,
      linkedToSession: bindingConfirmed,
      seedSuggested,
      seedReason: seedReason || undefined
    },
    session: {
      id: String(status.session_id || session.session_id || ''),
      state: sessionState,
      activeAgent: activeAgent || undefined
    },
    model: {
      provider: String(status.provider || session.provider || ''),
      adapter: String(status.adapter || ''),
      runtime: String(status.runtime || status.model_runtime || ''),
      configuredModel: String(status.model || session.model || ''),
      effectiveModel: String(status.effective_model || status.model || session.model || ''),
      state: modelState
    },
    context: {
      state: contextState,
      revision: contextRevision || undefined,
      occupied: typeof status.context_occupied === 'number' ? status.context_occupied : undefined,
      available: typeof status.context_available === 'number' ? status.context_available : undefined,
      limit: typeof status.context_limit === 'number' ? status.context_limit : undefined,
      reserve: typeof status.context_reserve === 'number' ? status.context_reserve : undefined,
      limitingFactor: String(status.context_limiting_factor || ''),
      receiptId: lastReceiptId || undefined,
      certificationStatus: certificationStatus || undefined
    },
    permissions: {
      ...permissions
    },
    capabilities: (status.capabilities as UiBootstrapSnapshot['capabilities']) || undefined,
    error: raw.error && typeof raw.error === 'object' ? raw.error : undefined,
    evidence: extractRecordArray(raw.evidence, ['items', 'receipts', 'claims', 'latest']),
    jobs: extractRecordArray(raw.jobs, ['jobs', 'items']),
    codeTask,
    recommendedActions: [],
    menuState
  };
  snapshot.recommendedActions = normalizeActions(snapshot);
  return snapshot;
}

function historyToTurns(history: BackendHistory | undefined): ChatTurn[] {
  if (!Array.isArray(history?.messages)) return [];
  return history.messages.slice(-30).map((message, index) => {
    const roleValue = String(message.role || 'assistant');
    const role: ChatTurn['role'] = roleValue === 'user' || roleValue === 'system' || roleValue === 'command' ? roleValue : 'assistant';
    return {
      id: String(message.id || `history-${index}`),
      role,
      text: String(message.content || message.text || message.message || ''),
      status: 'done',
      receipt: (message.receipt || message.context_receipt || null) as Record<string, unknown> | null,
      raw: message,
      timestamp: String(message.timestamp || message.created_at || nowStamp())
    };
  });
}

// CANON[WS-005]: Namespace para el useEffect de persistencia de workspace.
// Mantiene estado compartido entre renders sin reasignar el ref.
const persistWorkspace = {
  everPersistedRef: { current: false } as { current: boolean }
};

export function ControlPlane() {
  const [uiState, setUiState] = useState<UiState>(() => {
    const loaded = loadUiState();
    return {
      ...createDefaultUiState(),
      ...loaded,
      apiBase: loaded.apiBase || readStoredApiBase(),
      apiToken: ''
    };
  });
  const [booting, setBooting] = useState(true);
  const [busyCount, setBusyCount] = useState(0);
  const [snapshot, setSnapshot] = useState<UiBootstrapSnapshot | null>(null);
  const [menu, setMenu] = useState<BackendMenu | null>(null);
  const [routes, setRoutes] = useState<BackendRoutes | null>(null);
  const [providers, setProviders] = useState<BackendProviders | null>(null);
  const [routerState, setRouterState] = useState<{ list: BackendRouterList | null; policy: BackendRouterPolicy | null }>({ list: null, policy: null });
  const [history, setHistory] = useState<BackendHistory | null>(null);
  const [files, setFiles] = useState<Record<string, unknown> | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  // CANON[CTX-002]: Patches que ya fueron entregados al módulo de
  // contexto. Mantenemos un Set en memoria para no reingerir el mismo
  // bloque si el usuario entra y sale de la pantalla.
  const [handledContextPatches, setHandledContextPatches] = useState<Set<string>>(new Set());
  // CANON[CTX-018]: nodo que el chat quiere abrir cuando el usuario
  // pulsa "Abrir en árbol". Se sincroniza con `uiState.contextEditPatchId`
  // (campo de un solo uso que el módulo consume).
  const [initialContextSelectedNodeId, setInitialContextSelectedNodeId] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState('iniciando');
  const [commandResults, setCommandResults] = useState<Record<string, BackendCommandResult | null>>({});
  const [opening, setOpening] = useState(() => resolveOpeningState(null));
  const [workspacePickerOpen, setWorkspacePickerOpen] = useState(false);
  const [workspacePickerValue, setWorkspacePickerValue] = useState('');
  // Modelos activos del provider activo (Fase D). Se cruza con el router
  // para filtrar el desplegable del chat.
  const [activeProvider, setActiveProvider] = useState<string | null>(null);
  const [activeModels, setActiveModels] = useState<Set<string>>(new Set());
  const clientRef = useRef(createBagoClient(uiState.apiBase || readStoredApiBase(), uiState.apiToken));

  // CANON[CTX-013]: el árbol de contexto vive aquí, no dentro del
  // módulo, para que tanto el chat (que muestra tarjetas inline de
  // validación) como el módulo de contexto operen sobre el mismo
  // estado. Se monta una vez por sesión.
  const contextTree = useContextTree(clientRef.current);
  const contextTreeRef = useRef(contextTree);
  contextTreeRef.current = contextTree;
  const workspaceBridgeAvailable = Boolean(
    getElectronBridge()?.chooseProjectRoot || getElectronBridge()?.chooseWorkspaceRoot
  );

  const runBusy = async <T,>(task: () => Promise<T>): Promise<T> => {
    setBusyCount((count) => count + 1);
    try {
      return await task();
    } finally {
      setBusyCount((count) => Math.max(0, count - 1));
    }
  };

  const setAndPersistUiState = (patch: Partial<UiState>) => {
    setUiState((current) => {
      const next = patchUiState(current, {
        ...patch,
        workspaceHint: patch.workspaceHint !== undefined ? normalizeWorkspaceHint(patch.workspaceHint) : patch.workspaceHint
      });
      persistUiState(next);
      persistApiConfig(next.apiBase || readStoredApiBase());
      clientRef.current.setConfig(next.apiBase || readStoredApiBase(), next.apiToken || '');
      return next;
    });
  };

  const applyBootData = (data: Awaited<ReturnType<typeof clientRef.current.bootstrap>>) => {
    const nextSnapshot = buildSnapshot(data);
    const nextOpening = resolveOpeningState(nextSnapshot);
    setSnapshot(nextSnapshot);
    setOpening(nextOpening);
    setMenu((data.menu || null) as BackendMenu | null);
    setRoutes((data.routes || null) as BackendRoutes | null);
    setProviders((data.providers || null) as BackendProviders | null);
    setRouterState({
      list: (data.router_list || null) as BackendRouterList | null,
      policy: (data.router_policy || null) as BackendRouterPolicy | null
    });    setHistory((data.history || null) as BackendHistory | null);
    setFiles((data.files || null) as Record<string, unknown> | null);
    setTurns((current) => current.length ? current : historyToTurns(data.history));
    if (nextOpening.id === 'enter_directly') {
      setUiState((current) => current.activeSection === 'chat' ? current : patchUiState(current, { activeSection: 'home' }));
    }
    return nextSnapshot;
  };

  const bootstrap = async () => {
    setBooting(true);
    setLastMessage('consultando backend');
    try {
      const data = await clientRef.current.bootstrapModern().catch(() => clientRef.current.bootstrap());
      const nextSnapshot = applyBootData(data);
      // El snapshot moderno puede llegar antes de que el catálogo del router
      // quede materializado. La lectura dedicada mantiene el selector del chat
      // operativo incluso en ese arranque parcial.
      await refreshRouterState();
      setLastMessage(nextSnapshot?.workspace.linkedToSession ? 'backend confirmado' : 'snapshot recuperado');
    } catch (error) {
      const errorSnapshot: UiBootstrapSnapshot = {
        system: { state: 'error', backendAvailable: false },
        framework: { confirmed: false },
        project: { state: 'unknown' },
        workspace: { manifestState: 'unknown', linkedToSession: false },
        session: { state: 'unknown' },
        model: { state: 'unknown' },
        context: { state: 'blocked' },
        permissions: {
          canChat: false,
          canInitializeWorkspace: false,
          canLinkWorkspace: false,
          canRepairWorkspace: false,
          canSeedWorkspace: false,
          canRunTools: false,
          canInspectContext: false,
          canViewEvidence: false,
          canStopPipeline: false,
          canRetryPipeline: false
        },
        recommendedActions: []
      };
        setSnapshot(errorSnapshot);
        setOpening(resolveOpeningState(errorSnapshot));
        setRouterState({ list: null, policy: null });
        setFiles(null);
        setLastMessage(error instanceof Error ? error.message : 'fallo de conexión');
      } finally {
        setBooting(false);
      }
  };

  const resolveWorkspaceStartPath = (): string => {
    return normalizeWorkspaceHint(uiState.workspaceHint)
      || snapshot?.project.root
      || snapshot?.workspace.repoRoot
      || snapshot?.workspace.authorizedRoot
      || snapshot?.workspace.contextRoot
      || snapshot?.workspace.root
      || '';
  };

  const chooseWorkspaceExplorer = async (defaultPath?: string): Promise<string | null> => {
    const bridge = getElectronBridge();
    const chooseRoot = bridge?.chooseProjectRoot || bridge?.chooseWorkspaceRoot;
    if (chooseRoot) {
      const selection = (await chooseRoot({ defaultPath: defaultPath || resolveWorkspaceStartPath() })) as WorkspaceSelectionResult | null;
      const selectedRoot = readSelectedWorkspace(selection);
      if (!selectedRoot) {
        setLastMessage('selección de workspace cancelada');
        return null;
      }
      const seedAfterLink = shouldOfferSeed(snapshot, selectedRoot)
        ? window.confirm(`La ruta ${selectedRoot} no está validada todavía.\n\n¿Sembrar ahora para dejarla válida?`)
        : false;
      const activated = await activateWorkspaceRoot(selectedRoot, 'workspace activado', { seedAfterLink });
      return activated ? selectedRoot : null;
    }
    setLastMessage('el explorador nativo solo está disponible en Electron');
    return null;
  };

  const openWorkspacePicker = (): void => {
    setWorkspacePickerValue(resolveWorkspaceStartPath());
    setWorkspacePickerOpen(true);
  };

  const chooseWorkspaceFromHeader = (): void => {
    if (workspaceBridgeAvailable) {
      void chooseWorkspaceExplorer(resolveWorkspaceStartPath());
      return;
    }
    openWorkspacePicker();
  };

  const confirmWorkspacePicker = async (seedAfterLink: boolean) => {
    const selectedRoot = workspacePickerValue.trim();
    if (!selectedRoot) {
      setLastMessage('selección de workspace cancelada');
      setWorkspacePickerOpen(false);
      return;
    }
    await activateWorkspaceRoot(selectedRoot, 'workspace activado en navegador', {
      seedAfterLink
    });
  };

  useEffect(() => {
    void bootstrap();
  }, []);

  // CANON[WS-005]: Persiste el workspace activo cada vez que cambia.
  // El backend lo guarda en ~/.bago/last_workspace.json y lo usa al
  // próximo boot. Se ejecuta también al primer snapshot válido.
  useEffect(() => {
    if (!snapshot) return;
    const root = String(
      snapshot.project?.root || snapshot.workspace?.repoRoot || snapshot.workspace?.root || ''
    ).trim();
    if (!root) return;
    // Solo persistir si está vinculado (binding confirmado) o es la primera vez
    const linked = !!snapshot.workspace?.linkedToSession;
    if (!linked && !persistWorkspace.everPersistedRef.current) return;
    persistWorkspace.everPersistedRef.current = true;
    void clientRef.current.persistWorkspace(root).catch(() => {
      // Silenciar: la persistencia es best-effort
    });
  }, [snapshot?.workspace?.linkedToSession, snapshot?.workspace?.root, snapshot?.project?.root]);

  // Live event stream (SSE). Reconnects on disconnect with exponential
  // backoff (1s, 2s, 4s, 8s, capped at 30s). Maps backend events to
  // targeted refreshes so the UI updates without manual F5.
  useEffect(() => {
    let cancelled = false;
    let backoffMs = 1000;
    const backoffMaxMs = 30_000;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const connect = async () => {
      if (cancelled) return;
      try {
        await clientRef.current.streamEvents(async (eventName, payload) => {
          if (cancelled) return;
          switch (eventName) {
            case 'connected':
            case 'heartbeat':
              // Connection liveness. Reset backoff so we don't drop on first idle.
              backoffMs = 1000;
              break;
            case 'chat.completed':
            case 'chat.failed':
            case 'chat.timeout':
              // Chat events: refresh history and snapshot.
              await refreshAfterMutation();
              setLastMessage(eventName === 'chat.completed' ? 'chat completado' : 'chat con error');
              break;
            case 'evidence.created':
              // New receipt available.
              setLastMessage(`evidencia: ${String(payload.receipt_id || payload.envelope_id || 'nueva')}`);
              await refreshAfterMutation();
              break;
            case 'router.toggled':
            case 'router.auto_changed':
            case 'router.session_model_changed':
            case 'router.session_model_cleared':
              // Router changes are cheap to refresh; do it.
              await refreshRouterState();
              await refreshAfterMutation();
              setLastMessage(`router: ${eventName}`);
              break;
            case 'workspace.initialized':
            case 'workspace.linked':
            case 'workspace.seeded':
            case 'workspace.synced':
              // Workspace state changed. This is the authoritative signal
              // that binding flipped or the manifest became valid.
              await refreshAfterMutation();
              setLastMessage(`workspace: ${String(payload.action || eventName)}`);
              break;
            case 'job.cancelled':
            case 'job.retried':
              await refreshAfterMutation();
              setLastMessage(`job: ${eventName}`);
              break;
            default:
              // Unknown event: log once per kind to avoid spam.
              console.debug('[SSE] unhandled event', eventName, payload);
          }
        });
        // Stream finished cleanly (server closed).
        backoffMs = 1000;
      } catch (err) {
        console.warn('[SSE] stream error', err);
      }
      if (cancelled) return;
      // Schedule reconnect with exponential backoff.
      timer = setTimeout(() => { void connect(); }, backoffMs);
      backoffMs = Math.min(backoffMs * 2, backoffMaxMs);
    };

    void connect();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const entered = opening.id === 'enter_directly' || (uiState.activeSection !== 'home' && Boolean(snapshot));

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setUiState((current) => ({ ...current, commandPaletteOpen: !current.commandPaletteOpen }));
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'b') {
        event.preventDefault();
        setUiState((current) => ({ ...current, sidebarCollapsed: !current.sidebarCollapsed }));
        return;
      }
      // Ctrl+1..8: navegar a la vista N (orden de MainSidebar)
      if ((event.ctrlKey || event.metaKey) && /^[1-8]$/.test(event.key)) {
        event.preventDefault();
        const order: ActiveSection[] = ['home', 'chat', 'workspace', 'pipeline', 'context', 'evidence', 'graph', 'system'];
        const idx = parseInt(event.key, 10) - 1;
        const target = order[idx];
        if (target) {
          setAndPersistUiState({ activeSection: target });
        }
        return;
      }
      // F11: focus
      if (event.key === 'F11') {
        event.preventDefault();
        setUiState((current) => ({ ...current, globalMode: current.globalMode === 'focus' ? 'normal' : 'focus' }));
        return;
      }
      // F12: review/lectura
      if (event.key === 'F12') {
        event.preventDefault();
        setUiState((current) => ({ ...current, globalMode: current.globalMode === 'review' ? 'normal' : 'review' }));
        return;
      }
      if (event.key === '?' && !(event.target instanceof HTMLInputElement) && !(event.target instanceof HTMLTextAreaElement)) {
        event.preventDefault();
        setUiState((current) => ({ ...current, helpOpen: !current.helpOpen }));
        return;
      }
      if (event.key === 'Escape' && entered) {
        setUiState((current) => ({ ...current, commandPaletteOpen: false, helpOpen: false }));
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [entered]);

  useEffect(() => {
    const bridge = getElectronBridge();
    if (!bridge?.onInstanceActive) return;
    bridge.onInstanceActive((payload) => {
      setLastMessage(String(payload?.message || 'BAGO ya está abierto'));
    });
  }, []);

  useEffect(() => {
    persistUiState(uiState);
  }, [uiState]);

  // Carga modelos activos del provider activo cuando cambia.
  // Si no hay lista guardada, devuelve set vacío y el chat muestra todos
  // los del router (fallback). Se mantiene aquí para que el GlobalHeader
  // (que también los necesita) siga funcionando.
  useEffect(() => {
    const provider = (snapshot as any)?.model?.provider
      || (snapshot as any)?.provider
      || (snapshot as any)?.session?.provider
      || (snapshot as any)?.system?.provider
      || null;
    if (!provider) {
      setActiveProvider(null);
      setActiveModels(new Set());
      return;
    }
    setActiveProvider(provider);
    const url = `${uiState.apiBase || readStoredApiBase()}/providers/${provider}/active-models`;
    fetch(url)
      .then((r) => r.ok ? r.json() : { active_models: [] })
      .then((data) => {
        if (Array.isArray(data?.active_models)) {
          setActiveModels(new Set(data.active_models));
        } else {
          setActiveModels(new Set());
        }
      })
      .catch(() => setActiveModels(new Set()));
  }, [snapshot, uiState.apiBase]);
  const combinedActions = useMemo(() => snapshot?.recommendedActions || [], [snapshot]);

  // CANON[CTX-003]: cada vez que los turnos cambian, parseamos los
  // bloques <<BAGO:CONTEXT_PATCH_REQUEST>> y los entregamos al
  // módulo de contexto (solo los pendientes y solo los no manejados).
  const incomingContextPatches = useMemo(() => {
    const result: Array<{ patch: ContextPatchRequest; turnId: string }> = [];
    const fallbackTreeId = snapshot?.workspace.id || 'ctree_default';
    for (const turn of turns) {
      if (turn.role !== 'assistant' && turn.role !== 'command') continue;
      if (!turn.text) continue;
      const parsed = parseContextPatchRequests(turn.text, fallbackTreeId);
      for (const entry of parsed) {
        // El parser genera un id aleatorio. Lo estabilizamos con un
        // hash del bloque raw + turno para que el mismo patch no
        // cambie de id cada render.
        const stableId = `${turn.id}:${hashString(entry.raw)}`;
        if (handledContextPatches.has(stableId)) continue;
        result.push({ patch: { ...entry.patch, id: stableId, createdAt: turn.timestamp || entry.patch.createdAt }, turnId: turn.id });
      }
    }
    const assistant = [...turns].reverse().find((turn) => turn.role === 'assistant' && turn.text.trim());
    const assistantIndex = assistant ? turns.findIndex((turn) => turn.id === assistant.id) : -1;
    const user = assistantIndex > 0 ? [...turns.slice(0, assistantIndex)].reverse().find((turn) => turn.role === 'user' && turn.text.trim()) : undefined;
    const opportunityText = `${user?.text || ''}\n${assistant?.text || ''}`.trim();
    const opportunity = /\b(ui|pantalla|interfaz|frontend|vista|componente|tarea|pendiente|decisión|decidir|proyecto|flujo)\b/i.test(opportunityText);
    if (assistant && user && contextTree.tree?.rootId && opportunity && !result.some((entry) => entry.turnId === assistant.id)) {
      const stableId = `proactive:${assistant.id}:${hashString(opportunityText)}`;
      if (!handledContextPatches.has(stableId)) {
        result.push({
          turnId: assistant.id,
          patch: {
            id: stableId,
            treeId: fallbackTreeId,
            validationMode: 'modal',
            proposalType: 'chat_opportunity',
            title: 'Oportunidad de añadir contexto',
            reason: 'El chat contiene una tarea, decisión o elemento de UI que puede quedar como rama abierta.',
            riskLevel: 'low',
            patch: {
              operations: [{
                op: 'create',
                nodeId: `proactive_task_${hashString(opportunityText)}`,
                parentId: contextTree.tree.rootId,
                type: 'pending',
                title: user.text.slice(0, 120),
                summary: opportunityText.slice(0, 500),
                status: 'proposed',
                priority: 'medium'
              }]
            },
            createdAt: assistant.timestamp,
            createdBy: 'chat',
            status: 'pending',
            metadata: {
              source: 'chat_opportunity_detector',
              consent: 'required'
            }
          }
        });
      }
    }
    return result;
  }, [turns, handledContextPatches, snapshot?.workspace.id, contextTree.tree?.rootId]);

  const onContextPatchHandled = useCallback((patchId: string) => {
    setHandledContextPatches((current) => {
      if (current.has(patchId)) return current;
      const next = new Set(current);
      next.add(patchId);
      return next;
    });
  }, []);

  // CANON[CTX-014]: vincula cada patch con su turno original para que
  // el chat muestre la tarjeta inline. Los `proposals` viven en el
  // hook; los `incomingContextPatches` son los que acaban de llegar
  // del último parseo. Cruzamos ambos.
  const contextPatchDisplay = useMemo(() => {
    const map = new Map<string, { patch: ContextPatchRequest; turnId: string }>();
    for (const entry of incomingContextPatches) {
      map.set(entry.patch.id, entry);
    }
    return contextTree.proposals.map((patch) => {
      const source = map.get(patch.id);
      return {
        patch,
        turnId: source?.turnId || '',
        status: patch.status,
        errorMessage: patch.errorMessage,
        appliedAt: patch.appliedAt,
        receiptId: patch.receiptId
      };
    }).filter((entry) => entry.turnId);
  }, [contextTree.proposals, incomingContextPatches]);

  const acceptContextPatch = useCallback(async (patchId: string) => {
    await contextTree.acceptPatch(patchId);
  }, [contextTree]);
  const rejectContextPatch = useCallback(async (patchId: string) => {
    await contextTree.rejectPatch(patchId);
  }, [contextTree]);
  const revertContextPatch = useCallback(async (patchId: string) => {
    await contextTree.revertPatch(patchId);
  }, [contextTree]);
  const reviewContextPatch = useCallback((patchId: string) => {
    void contextTree.rejectPatch(patchId);
  }, [contextTree]);
  const editContextPatch = useCallback((patchId: string) => {
    setAndPersistUiState({ contextEditPatchId: patchId, activeSection: 'context' });
  }, [setAndPersistUiState]);
  const openContextInTree = useCallback((patchId: string) => {
    const patch = contextTree.proposals.find((p) => p.id === patchId);
    if (patch?.targetNodeId) {
      setInitialContextSelectedNodeId(patch.targetNodeId);
    }
    setAndPersistUiState({ activeSection: 'context' });
  }, [contextTree.proposals, setAndPersistUiState]);

  const refreshAfterMutation = async (): Promise<UiBootstrapSnapshot | null> => {
    const next = await clientRef.current.bootstrapModern().catch(() => clientRef.current.bootstrap());
    return applyBootData(next);
  };

  const refreshRouterState = async (): Promise<void> => {
    const [list, policy] = await Promise.all([
      clientRef.current.getRouterList().catch(() => undefined),
      clientRef.current.getRouterPolicy().catch(() => undefined)
    ]);
    setRouterState({
      list: (list || null) as BackendRouterList | null,
      policy: (policy || null) as BackendRouterPolicy | null
    });
  };

  const activateWorkspaceRoot = async (selectedRoot: string, sourceLabel: string, options?: { seedAfterLink?: boolean }): Promise<boolean> => {
    const cleanRoot = selectedRoot.trim();
    if (!cleanRoot) {
      setLastMessage('selección de workspace cancelada');
      return false;
    }

    setAndPersistUiState({ workspaceHint: normalizeWorkspaceHint(cleanRoot) });
    setWorkspacePickerOpen(false);

    try {
      const nextRepairableState = snapshot?.workspace.manifestState;
      if (nextRepairableState === 'missing' || nextRepairableState === 'invalid' || nextRepairableState === 'legacy') {
        await clientRef.current.initProject(cleanRoot);
      }
      const linkResult = await clientRef.current.linkProject(cleanRoot);
      if (linkResult.ok === false) {
        setLastMessage(String(linkResult.message || 'no se pudo activar el workspace'));
        return false;
      }

      let nextSnapshot = await refreshAfterMutation();
      if (options?.seedAfterLink) {
        const seedResult = await clientRef.current.seedProject(cleanRoot);
        if (seedResult.ok === false) {
          setLastMessage(String(seedResult.message || 'no se pudo sembrar el workspace'));
          return false;
        }
        nextSnapshot = await refreshAfterMutation();
      }

      if (nextSnapshot && !nextSnapshot.permissions.canChat && nextSnapshot.workspace.manifestState !== 'valid') {
        await clientRef.current.syncProject(cleanRoot);
        nextSnapshot = await refreshAfterMutation();
      }

      const activated = Boolean(nextSnapshot?.project.root) && Boolean(nextSnapshot?.permissions.canChat);
      if (!activated) {
        setLastMessage(`el backend no pudo autorizar el chat para ${cleanRoot}`);
        return false;
      }

      // CANON[CTX-020]: al cambiar de workspace, el árbol de contexto
      // y el banco deben recargarse desde el nuevo `.bago/context/`.
      // Si no, el usuario seguiría viendo los nodos/packs/receipts
      // del workspace anterior mezclados con el nuevo.
      const treeRef = contextTreeRef.current;
      await Promise.all([
        treeRef.refresh(),
        treeRef.refreshBank()
      ]).catch((e) => {
        setLastMessage(`contexto recargado parcialmente: ${e instanceof Error ? e.message : String(e)}`);
      });

      setLastMessage(`${sourceLabel}: ${cleanRoot}`);
      openShell('workspace');
      return true;
    } catch (error) {
      setLastMessage(error instanceof Error ? error.message : 'no se pudo activar el workspace');
      return false;
    }
  };

  const runCommand = async (command: string): Promise<BackendCommandResult | null> => {
    const clean = command.trim();
    if (!clean) return null;
    // Comandos nativos del frontend (no van al backend como /command).
    // /auto-config start|status|apply|cancel
    // /blacklist show
    if (clean.startsWith('/auto-config') || clean.startsWith('/blacklist')) {
      const [ns, action] = clean.replace(/^\/+/, '').split(/\s+/, 2);
      const base = uiState.apiBase || readStoredApiBase();
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (uiState.apiToken) headers['Authorization'] = `Bearer ${uiState.apiToken}`;
      let endpoint = '';
      let method = 'GET';
      let body: any = undefined;
      if (ns === 'auto-config') {
        if (action === 'start')   { endpoint = '/configure/auto/start';   method = 'POST'; body = {}; }
        else if (action === 'apply')  { endpoint = '/configure/auto/apply';   method = 'POST'; body = {}; }
        else if (action === 'cancel') { endpoint = '/configure/auto/cancel';  method = 'POST'; body = {}; }
        else                          { endpoint = '/configure/auto/status';  method = 'GET';  }
      } else if (ns === 'blacklist') {
        endpoint = '/providers/blacklist';
      }
      if (!endpoint) {
        const result: BackendCommandResult = { ok: false, message: `comando no reconocido: ${clean}` };
        setLastMessage(result.message || clean);
        return result;
      }
      try {
        // FIX v0.2.1 (R2): timeout de 60s para comandos redirigidos
        // (/configure/auto/*, /providers/blacklist). Evita que la UI
        // quede esperando indefinidamente si el backend cuelga.
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 60_000);
        let res: Response;
        try {
          res = await fetch(`${base}${endpoint}`, { method, headers, body: body ? JSON.stringify(body) : undefined, signal: controller.signal });
        } finally {
          clearTimeout(timer);
        }
        const data = await res.json().catch(() => ({}));
        let summary = '';
        if (ns === 'auto-config') {
          if (action === 'start') summary = `Auto-config lanzada (${data.models_to_test ?? 0} modelos a probar)`;
          else if (action === 'apply') summary = data.ok ? `Config aplicada: default=${data.applied?.default_model}` : data.error || 'falló';
          else if (action === 'cancel') summary = 'Auto-config cancelada';
          else summary = `Auto-config status: ${data.status} (${data.tested_models ?? 0}/${data.total_models ?? 0})`;
        } else {
          const models = (data.models || []) as string[];
          summary = models.length ? `Blacklist (${models.length}): ${models.slice(0, 3).join(', ')}${models.length > 3 ? '…' : ''}` : 'Blacklist vacía';
        }
        const result: BackendCommandResult = { ok: true, message: summary, data };
        setLastMessage(summary);
        const turnId = `command-${Date.now()}`;
        setTurns((current) => [...current, {
          id: turnId, role: 'command', text: clean, status: 'done',
          timestamp: nowStamp(), receipt: data as Record<string, unknown>,
        }]);
        return result;
      } catch (exc) {
        const message = exc instanceof Error ? exc.message : `falló ${clean}`;
        setLastMessage(message);
        return { ok: false, message };
      }
    }
    const turnId = `command-${Date.now()}`;
    setTurns((current) => [...current, {
      id: turnId,
      role: 'command',
      text: clean,
      status: 'running',
      timestamp: nowStamp()
    }]);
    setLastMessage(`ejecutando ${clean}`);
    setBusyCount((count) => count + 1);
    try {
      const result = await clientRef.current.runCommand(clean);
      const key = commandKey(clean);
      setCommandResults((current) => ({ ...current, [key]: result }));
      setTurns((current) => current.map((turn) => turn.id === turnId ? {
        ...turn,
        status: result.ok === false ? 'failed' : 'done',
        receipt: (asCommandReceipt(result) || null),
        raw: result
      } : turn));

      if (clean === '/roadmap') setCommandResults((current) => ({ ...current, roadmap: result }));
      if (clean.startsWith('/plan ')) setCommandResults((current) => ({ ...current, plan: result }));
      if (clean === '/context inspect') setCommandResults((current) => ({ ...current, contextInspect: result }));
      if (clean === '/context attach') setCommandResults((current) => ({ ...current, contextAttach: result }));
      if (clean === '/context measure') setCommandResults((current) => ({ ...current, contextMeasure: result }));
      if (clean === '/context certify') setCommandResults((current) => ({ ...current, contextCertify: result }));

      if (clean === '/status' || clean === '/session' || clean.startsWith('/context') || clean.startsWith('/project') || clean.startsWith('/workspace')) {
        await refreshAfterMutation();
      }
      if (clean === '/project status' || clean === '/project analyze') {
        await refreshAfterMutation();
      }
      setLastMessage(result.message || clean);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : `falló ${clean}`;
      setTurns((current) => current.map((turn) => turn.id === turnId ? { ...turn, status: 'failed', text: `${clean}\n${message}` } : turn));
      setLastMessage(message);
      return null;
    } finally {
      setBusyCount((count) => Math.max(0, count - 1));
    }
  };

  const runContextCommand = async (command: string) => {
    const result = await runCommand(command);
    if (result?.data && (command.includes('inspect') || command.includes('attach'))) {
      onInspect({
        id: command.includes('attach') ? 'context-attach' : 'context-inspect',
        kind: 'context',
        title: command.includes('attach') ? 'Contexto adjuntado' : 'Inspección de contexto',
        summary: result.message || (command.includes('attach') ? 'Contexto adjuntado' : 'Contexto inspeccionado'),
        detail: ['source: backend command', `command: ${command}`],
        raw: safeJson(result.data)
      }, 'detail');
    }
  };

  const sendChat = async (message: string) => {
    const text = message.trim();
    if (!text) return;
    if (!snapshot?.permissions.canChat) {
      setLastMessage('chat bloqueado por el estado del backend');
      return;
    }

    const stamp = Date.now();
    const userTurn: ChatTurn = {
      id: `user-${stamp}`,
      role: 'user',
      text,
      status: 'done',
      timestamp: nowStamp()
    };
    const assistantBuffer: ChatTurn = {
      id: `assistant-${stamp}`,
      role: 'assistant',
      text: '',
      status: 'running',
      timestamp: nowStamp()
    };
    setTurns((current) => [...current, userTurn, assistantBuffer]);
    setUiState((current) => patchUiState(current, { drafts: { ...current.drafts, chat: '' } }));
    setBusyCount((count) => count + 1);

    try {
      const payload = uiState.chatMode === 'trace'
        ? await clientRef.current.streamChat(text, (chunk) => {
          setTurns((current) => current.map((turn) => turn.id === assistantBuffer.id ? { ...turn, text: turn.text + chunk } : turn));
        })
        : await clientRef.current.sendChat(text);
      const receipt = (payload.receipt || payload.context_receipt || null) as Record<string, unknown> | null;
      setTurns((current) => current.map((turn) => {
        if (turn.id !== assistantBuffer.id) return turn;
        const responseText = String(payload.response || payload.message || turn.text || '');
        return {
          ...turn,
          text: responseText,
          status: payload.ok === false ? 'failed' : receipt ? 'done' : 'validating',
          receipt,
          raw: payload
        };
      }));
      if (payload.ok !== false) {
        onInspect({
          id: String(payload.session_id || assistantBuffer.id),
          kind: 'chat-response',
          title: 'Respuesta de BAGO',
          summary: String(payload.response || payload.message || 'Respuesta recibida'),
          detail: [
            `provider: ${String(payload.provider || snapshot.model.provider || 'unknown')}`,
            `receipt: ${receipt ? 'available' : 'pending'}`
          ],
          raw: safeJson(payload)
        });
      }
      setLastMessage(String(payload.response || payload.message || 'respuesta recibida'));
      await refreshAfterMutation();
      if (receipt) {
        setTurns((current) => current.map((turn) => turn.id === assistantBuffer.id ? { ...turn, status: 'done' } : turn));
      }
    } catch (error) {
      const messageText = error instanceof Error ? error.message : 'falló el chat';
      setTurns((current) => current.map((turn) => turn.id === assistantBuffer.id ? { ...turn, status: 'failed', text: turn.text || messageText } : turn));
      setLastMessage(messageText);
    } finally {
      setBusyCount((count) => Math.max(0, count - 1));
    }
  };

  const [selectionMenu, setSelectionMenu] = useState<{ selection: SelectionRecord; position: { x: number; y: number } } | null>(null);
  const [inspectorSelection, setInspectorSelection] = useState<{ selection: SelectionRecord; level: InspectorLevel } | null>(null);
  const [workspaceOpenRequest, setWorkspaceOpenRequest] = useState<{ path: string; kind?: 'file' | 'directory'; token: number } | null>(null);

  function openInspector(selection: SelectionRecord, level: InspectorLevel = 'detail') {
    setInspectorSelection({ selection, level });
  }

  function openContextMenu(selection: SelectionRecord, position: { x: number; y: number }) {
    setSelectionMenu({ selection, position });
  }

  function onInspect(eventOrSelection: ReactMouseEvent<HTMLElement> | SelectionRecord, hint?: InspectorLevel | { x: number; y: number }) {
    if (eventOrSelection && typeof eventOrSelection === 'object' && 'clientX' in eventOrSelection) {
      const mouseEvent = eventOrSelection as React.MouseEvent;
      mouseEvent.preventDefault();
      mouseEvent.stopPropagation();
      return;
    }

    if (hint && typeof hint === 'object' && 'x' in hint && 'y' in hint) {
      openContextMenu(eventOrSelection, hint);
      return;
    }

    openInspector(eventOrSelection, typeof hint === 'string' ? hint : 'detail');
  }

  const useSelectionInChat = (nextSelection: SelectionRecord) => {
    const text = [
      `Revisa esto: ${nextSelection.title}`,
      `kind: ${nextSelection.kind}`,
      `id: ${nextSelection.id}`,
      '',
      nextSelection.summary,
      ...nextSelection.detail.map((line) => `- ${line}`)
    ].join('\n');
    setDraft('chat', text);
    setAndPersistUiState({ activeSection: 'chat' });
    setLastMessage(`selección enviada al chat: ${nextSelection.title}`);
  };


  const readSelectionPath = (selection: SelectionRecord): string => {
    const raw = selection.raw && typeof selection.raw === 'object' && !Array.isArray(selection.raw)
      ? selection.raw as Record<string, unknown>
      : {};
    return readText(raw.path || raw.full_path || raw.file || raw.file_path || selection.id || selection.title).trim();
  };

  const writeClipboard = async (label: string, value: string) => {
    const clean = value.trim();
    if (!clean) return;
    await navigator.clipboard?.writeText(clean);
    setLastMessage(`${label} copiado`);
  };

  const openSectionFromSelection = (selection: SelectionRecord) => {
    const targetKind = selection.targetKind || 'unknown';
    if (targetKind.startsWith('workspace.')) return navigate('workspace');
    if (targetKind.startsWith('pipeline.')) return navigate('pipeline');
    if (targetKind.startsWith('evidence.')) return navigate('evidence');
    if (targetKind.startsWith('context.')) return navigate('context');
    if (targetKind.startsWith('system.')) return navigate('system');
    if (targetKind === 'screen.chat') return navigate('chat');
    if (targetKind === 'screen.home') return navigate('home');
    const kind = selection.kind.toLowerCase();
    const id = selection.id.toLowerCase();
    if (kind.includes('workspace') || id.includes('workspace')) return navigate('workspace');
    if (kind.includes('pipeline') || kind.includes('job') || id.includes('pipeline')) return navigate('pipeline');
    if (kind.includes('evidence') || kind.includes('receipt') || id.includes('evidence')) return navigate('evidence');
    if (kind.includes('context') || id.includes('context')) return navigate('context');
    if (kind.includes('router') || kind.includes('system') || kind.includes('provider')) return navigate('system');
    if (kind.includes('graph') || kind.includes('node')) return navigate('graph');
    return navigate('chat');
  };

  const openWorkspaceFileFromMenu = (path: string, kind: 'file' | 'directory' = 'file') => {
    const clean = path.trim();
    if (!clean) {
      navigate('workspace');
      return;
    }
    setWorkspaceOpenRequest({ path: clean, kind, token: Date.now() });
    navigate('workspace');
    setLastMessage(`${kind === 'directory' ? 'carpeta' : 'archivo'} abierto en workspace: ${clean}`);
  };

  // CANON[CTX-008]: encolar un item para que el módulo de Contexto lo
  // recoja al abrirse. kindOverride permite crear como 'claim' o 'rule'
  // en lugar del tipo por defecto.
  const enqueueContextBankItem = (
    path: string,
    kind: 'file' | 'directory' | 'source',
    destination: 'tree' | 'pack',
    kindOverride?: 'claim' | 'rule'
  ) => {
    const clean = path.trim();
    if (!clean) return Promise.resolve();
    const pending = {
      id: `cbp_${Math.random().toString(36).slice(2, 10)}`,
      kind,
      path: clean,
      title: clean.split('/').pop() || clean,
      destination,
      createdAt: new Date().toISOString()
    } as const;
    // Serializamos el kindOverride en el title como prefijo si hace falta
    // para que el módulo sepa qué tipo de nodo crear.
    const enriched = kindOverride
      ? { ...pending, title: `[${kindOverride}] ${pending.title}` }
      : pending;
    setUiState((current) => {
      const next = patchUiState(current, {
        ...current,
        contextBankPending: [...(current.contextBankPending || []), enriched],
        activeSection: 'context'
      });
      persistUiState(next);
      return next;
    });
    setLastMessage(`${enriched.title} → Árbol de Contexto`);
    return Promise.resolve();
  };

  const buildContextActions = (selection: SelectionRecord) => createContextActions(selection, {
    turns,
    snapshot,
    opening,
    booting,
    routerState,
    uiState: { drafts: uiState.drafts, chatMode: uiState.chatMode, globalMode: uiState.globalMode },
    readSelectionPath,
    useSelectionInChat,
    openInspector,
    openShell,
    openWorkspacePicker,
    openWorkspaceFileFromMenu,
    openSectionFromSelection,
    navigate,
    runCommand,
    runContextCommand,
    bootstrap,
    refreshAfterMutation,
    refreshRouterState,
    setRouterAutoSwitch,
    setDraft,
    ensureChatPanel: () => openShell('chat'),
    writeClipboard,
    setAndPersistUiState,
    confirm: (message) => window.confirm(message),
    addWorkspacePathToContextTree: (path, kind) => enqueueContextBankItem(path, kind, 'tree'),
    addWorkspacePathToContextPack: (path) => enqueueContextBankItem(path, 'file', 'pack'),
    createContextClaimFromWorkspacePath: (path) => enqueueContextBankItem(path, 'file', 'tree', 'claim'),
    addSelectionAsContextRule: (text) => enqueueContextBankItem(text, 'file', 'tree', 'rule')
  });

  const setDraft = (key: string, text: string) => {
    setUiState((current) => patchUiState(current, { drafts: { ...current.drafts, [key]: text } }));
  };

  const navigate = (section: ActiveSection) => {
    setAndPersistUiState({ activeSection: section });
  };

  const runAction = async (action: UiAction) => {
    if (!action.enabled) return;
    if (action.confirmation?.required && !window.confirm(action.confirmation.description || action.label)) return;
    if (action.kind === 'navigate' && action.payload?.section) {
      navigate(String(action.payload.section) as ActiveSection);
      return;
    }
    const endpoint = String(action.payload?.endpoint || '');
    if (endpoint === 'project:init') {
      await clientRef.current.initProject();
      await refreshAfterMutation();
      return;
    }
    if (endpoint === 'project:link') {
      const root = String(action.payload?.root || snapshot?.project.root || snapshot?.workspace.repoRoot || snapshot?.workspace.root || '').trim();
      if (!root) {
        setLastMessage('no hay workspace activo para enlazar');
        return;
      }
      const seedAfterLink = shouldOfferSeed(snapshot, root)
        ? window.confirm(`La ruta ${root} no está validada todavía.\n\n¿Sembrar ahora para dejarla válida?`)
        : false;
      await activateWorkspaceRoot(root, 'workspace enlazado', { seedAfterLink });
      return;
    }
    if (endpoint === 'project:status') {
      await clientRef.current.getProjectStatus();
      await refreshAfterMutation();
      return;
    }
    if (action.payload?.command) await runCommand(String(action.payload.command));
  };

  const paletteActions = useMemo(() => {
    type PaletteItem = { id: string; label: string; group: string; icon: string; shortcut?: string; action: () => void };
    const base: PaletteItem[] = [
      // ─── Navegación ───
      { id: 'nav-home',     label: 'Inicio',      group: 'Navegación', icon: 'home',       shortcut: 'Ctrl+1', action: () => navigate('home') },
      { id: 'nav-chat',     label: 'Chat',        group: 'Navegación', icon: 'chat',       shortcut: 'Ctrl+2', action: () => navigate('chat') },
      { id: 'nav-workspace',label: 'Workspace',   group: 'Navegación', icon: 'workspace',  shortcut: 'Ctrl+3', action: () => navigate('workspace') },
      { id: 'nav-pipeline', label: 'Pipeline',    group: 'Navegación', icon: 'pipeline',   shortcut: 'Ctrl+4', action: () => navigate('pipeline') },
      { id: 'nav-context',  label: 'Contexto',    group: 'Navegación', icon: 'context',    shortcut: 'Ctrl+5', action: () => navigate('context') },
      { id: 'nav-evidence', label: 'Evidencia',   group: 'Navegación', icon: 'evidence',   shortcut: 'Ctrl+6', action: () => navigate('evidence') },
      { id: 'nav-graph',    label: 'Grafo',       group: 'Navegación', icon: 'graph',      shortcut: 'Ctrl+7', action: () => navigate('graph') },
      { id: 'nav-system',   label: 'Operación',   group: 'Navegación', icon: 'system',     shortcut: 'Ctrl+8', action: () => navigate('system') },
      // ─── Vistas / paneles ───
      { id: 'toggle-sidebar', label: uiState.sidebarCollapsed ? 'Mostrar navegación' : 'Ocultar navegación', group: 'Paneles', icon: 'menu', shortcut: 'Ctrl+B', action: () => setUiState((c) => ({ ...c, sidebarCollapsed: !c.sidebarCollapsed })) },
      // ─── Modos ───
      { id: 'focus',  label: uiState.globalMode === 'focus'  ? 'Salir de Focus'  : 'Entrar en Focus',  group: 'Modos', icon: 'focus',  shortcut: 'F11', action: () => setAndPersistUiState({ globalMode: uiState.globalMode === 'focus'  ? 'normal' : 'focus' }) },
      { id: 'review', label: uiState.globalMode === 'review' ? 'Salir de Lectura' : 'Entrar en Lectura', group: 'Modos', icon: 'review', shortcut: 'F12', action: () => setAndPersistUiState({ globalMode: uiState.globalMode === 'review' ? 'normal' : 'review' }) },
      // ─── Comandos del sistema ───
      { id: 'cmd-status',    label: 'Ejecutar /status',            group: 'Comandos', icon: 'live',      action: () => void runCommand('/status') },
      { id: 'cmd-session',   label: 'Ejecutar /session',           group: 'Comandos', icon: 'session',   action: () => void runCommand('/session') },
      { id: 'ctx-attach',    label: 'Adjuntar contexto',           group: 'Comandos', icon: 'attach',    action: () => void runContextCommand('/context attach') },
      { id: 'ctx-measure',   label: 'Medir contexto',              group: 'Comandos', icon: 'inspector', action: () => void runContextCommand('/context measure') },
      { id: 'ctx-certify',   label: 'Certificar contexto',         group: 'Comandos', icon: 'check',     action: () => void runContextCommand('/context certify') },
    ];
    for (const action of combinedActions.filter((item) => item.visible && item.enabled)) {
      base.push({ id: `backend-${action.id}`, label: action.label, group: 'Acciones recomendadas', icon: 'plus', action: () => void runAction(action) });
    }
    return base;
  }, [combinedActions, uiState.globalMode, uiState.sidebarCollapsed]);

  const runPlanTask = async (task: string) => {
    const clean = task.trim();
    if (!clean) return;
    setUiState((current) => patchUiState(current, { drafts: { ...current.drafts, pipeline: clean } }));
    await runCommand(`/plan ${clean}`);
  };

  const openShell = (section: ActiveSection, mode: UiState['globalMode'] = 'normal') => {
    setAndPersistUiState({ activeSection: section, globalMode: mode });
  };

  const toggleRouterSelection = async (key: string): Promise<void> => {
    const clean = key.trim();
    if (!clean) return;
    setLastMessage(`cambiando router ${clean}`);
    await clientRef.current.toggleRouter(clean);
    await refreshRouterState();
    await refreshAfterMutation();
  };

  const setRouterAutoSwitch = async (enabled: boolean): Promise<void> => {
    setLastMessage(enabled ? 'activando auto-router' : 'desactivando auto-router');
    await clientRef.current.setRouterAuto(enabled);
    await refreshRouterState();
    await refreshAfterMutation();
  };

  const [sessionModel, setSessionModelState] = useState<string | null>(null);

  const configureProvider = async (provider: string, config: { enabled?: boolean; base_url?: string; api_key?: string; model?: string }): Promise<void> => {
    setLastMessage(`configurando proveedor ${provider}`);
    await clientRef.current.configureProvider(provider, config);
    await refreshAfterMutation();
  };

  const setSessionModelCb = async (modelKey: string | null): Promise<void> => {
    setLastMessage(modelKey ? `modelo sesión: ${modelKey}` : 'modelo sesión: auto');
    const previousModel = sessionModel;
    setSessionModelState(modelKey);
    try {
      await clientRef.current.setSessionModel(modelKey);
      await refreshAfterMutation();
    } catch (error) {
      setSessionModelState(previousModel);
      throw error;
    }
  };

  useEffect(() => {
    clientRef.current.getSessionModel().then((r) => {
      const m = r?.session_model as string | null | undefined;
      setSessionModelState(m ?? null);
    }).catch(() => null);
  }, []);

  return (
    <>
      <div className={`app-root mode-${uiState.globalMode} ${uiState.sidebarCollapsed ? 'sidebar-collapsed' : ''} section-${uiState.activeSection}`}>
        <GlobalHeader
          snapshot={snapshot}
          workspaceHint={uiState.workspaceHint}
          apiBase={uiState.apiBase}
          apiToken={uiState.apiToken}
          activeSection={uiState.activeSection}
          busy={booting || busyCount > 0}
          onApiConfigChange={(patch) => setAndPersistUiState(patch)}
          onOpenPalette={() => setAndPersistUiState({ commandPaletteOpen: true })}
          onToggleSidebar={() => setAndPersistUiState({ sidebarCollapsed: !uiState.sidebarCollapsed })}
          onRefresh={bootstrap}
          onSetMode={(mode) => setAndPersistUiState({ globalMode: mode })}
          onRunCommand={(command) => void runCommand(command)}
          onChooseWorkspace={chooseWorkspaceFromHeader}
          onOpenHelp={() => setAndPersistUiState({ helpOpen: true })}
          globalMode={uiState.globalMode}
          sidebarCollapsed={uiState.sidebarCollapsed}
        />

        <div className="app-body">
          {uiState.globalMode === 'normal' && (
            <MainSidebar
              activeSection={uiState.activeSection}
              snapshot={snapshot}
              opening={opening}
              actions={combinedActions}
              workspaceHint={uiState.workspaceHint}
              collapsed={uiState.sidebarCollapsed}
              onNavigate={navigate}
              onRunAction={runAction}
            />
          )}

          <div className="app-main-area">
            <div className="workspace-area">
              <WorkspaceShell
                activeSection={uiState.activeSection}
                snapshot={snapshot}
                mode={uiState.globalMode}
                showReadiness={uiState.activeSection !== 'workspace'}
                showGlobalChips={uiState.activeSection !== 'workspace'}
              >
                <ControlSections
                  section={uiState.activeSection}
                  snapshot={snapshot}
                  opening={opening}
                  booting={booting}
                  workspaceHint={uiState.workspaceHint}
                  apiBase={uiState.apiBase}
                  apiToken={uiState.apiToken}
                  client={clientRef.current}
                  onApiConfigChange={(patch) => setAndPersistUiState(patch)}
                  onPrimary={() => openShell(opening.targetSection === 'home' && snapshot?.permissions.canChat ? 'chat' : opening.targetSection)}
                  onContinue={() => { void runCommand('/session').then(() => openShell(snapshot?.permissions.canChat ? 'chat' : 'home')); }}
                  onChooseWorkspace={openWorkspacePicker}
                  onOpenPalette={() => setAndPersistUiState({ commandPaletteOpen: true })}
                  onRefresh={bootstrap}
                  menu={menu}
                  routes={routes}
                  providers={providers}
                  router={routerState}
                  history={history}
                  files={files}
                  commandResults={commandResults}
                  turns={turns}
                  drafts={uiState.drafts}
                  chatMode={uiState.chatMode}
                  globalMode={uiState.globalMode}
                  onDraftChange={setDraft}
                  onSendChat={sendChat}
                  onInspect={onInspect}
                  onRunCommand={runCommand}
                  onRunContextCommand={runContextCommand}
                  onRunAction={runAction}
                  onRunPlanTask={runPlanTask}
                  onSetSection={navigate}
                  onSetChatMode={(mode) => setAndPersistUiState({ chatMode: mode })}
                  onSetGlobalMode={(mode) => setAndPersistUiState({ globalMode: mode })}
                  onReadFile={(path) => clientRef.current.readFile(path).catch(() => null)}
                  onManageSource={(action, path, label) => clientRef.current.manageSource(action, path, label).catch(() => null)}
                  onRefreshRouter={refreshRouterState}
                  onToggleRouter={toggleRouterSelection}
                  onSetRouterAuto={setRouterAutoSwitch}
                  onConfigureProvider={configureProvider}
                  onSetSessionModel={setSessionModelCb}
                  sessionModel={sessionModel}
                  workspaceOpenRequest={workspaceOpenRequest}
                  contextClient={clientRef.current}
                  contextTree={contextTree}
                  incomingContextPatches={incomingContextPatches}
                  onContextPatchHandled={onContextPatchHandled}
                  contextBankPending={uiState.contextBankPending || []}
                  onContextBankPendingConsumed={(id) => {
                    setUiState((current) => {
                      const next = patchUiState(current, { contextBankPending: (current.contextBankPending || []).filter((p) => p.id !== id) });
                      persistUiState(next);
                      return next;
                    });
                  }}
                  contextPatchDisplay={contextPatchDisplay}
                  onAcceptContextPatch={acceptContextPatch}
                  onRejectContextPatch={rejectContextPatch}
                  onEditContextPatch={editContextPatch}
                  onRevertContextPatch={revertContextPatch}
                  onReviewContextPatch={reviewContextPatch}
                  onOpenContextInTree={openContextInTree}
                  initialContextSelectedNodeId={initialContextSelectedNodeId}
                  initialContextEditingPatchId={uiState.contextEditPatchId}
                  onInitialContextStateConsumed={() => {
                    setInitialContextSelectedNodeId(null);
                    setAndPersistUiState({ contextEditPatchId: null });
                  }}
                />
              </WorkspaceShell>
            </div>

          </div>
        </div>
        <ActivityToast message={lastMessage} busy={booting || busyCount > 0} state={snapshot?.system.state || 'unknown'} />
      </div>

      {uiState.commandPaletteOpen && (
        <CommandPalette actions={paletteActions} onClose={() => setAndPersistUiState({ commandPaletteOpen: false })} />
      )}
      {uiState.helpOpen && (
        <HelpOverlay onClose={() => setAndPersistUiState({ helpOpen: false })} />
      )}
      {workspacePickerOpen && (
      <WorkspacePickerDialog
          value={workspacePickerValue}
          onChange={setWorkspacePickerValue}
          onClose={() => setWorkspacePickerOpen(false)}
          onChooseExplorer={() => { void chooseWorkspaceExplorer(workspacePickerValue || resolveWorkspaceStartPath()); }}
          seedSuggested={shouldOfferSeed(snapshot, workspacePickerValue || resolveWorkspaceStartPath())}
          onConfirm={(seed) => { void confirmWorkspacePicker(seed); }}
          client={clientRef.current}
        />
      )}

      {selectionMenu && (
        <ContextMenu
          selection={selectionMenu.selection}
          position={selectionMenu.position}
          actions={buildContextActions(selectionMenu.selection)}
          onClose={() => setSelectionMenu(null)}
        />
      )}
      {inspectorSelection && (
        <InspectorDrawer
          selection={inspectorSelection.selection}
          level={inspectorSelection.level}
          onClose={() => setInspectorSelection(null)}
          onOpenContextMenu={(selection, position) => openContextMenu(selection, position)}
        />
      )}
    </>
  );
}

function asCommandReceipt(result: BackendCommandResult): Record<string, unknown> | undefined {
  if (!result || typeof result !== 'object') return undefined;
  const data = result as Record<string, unknown>;
  const receipt = data.receipt || data.context_receipt;
  return receipt && typeof receipt === 'object' && !Array.isArray(receipt) ? receipt as Record<string, unknown> : undefined;
}



interface ActivityToastProps {
  message: string;
  busy: boolean;
  state: string;
}

function ActivityToast({ message, busy, state }: ActivityToastProps) {
  const label = message || (busy ? 'procesando' : 'sin actividad reciente');
  return (
    <div className={`activity-toast state-${busy ? 'loading' : state}`} role="status" aria-live="polite">
      <span className="activity-toast-dot" />
      <span>{label}</span>
    </div>
  );
}

interface HelpOverlayProps {
  onClose: () => void;
}

function HelpOverlay({ onClose }: HelpOverlayProps) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' || event.key === '?') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const shortcuts = [
    ['Ctrl K', 'Abrir comandos y búsqueda'],
    ['Ctrl B', 'Mostrar u ocultar navegación'],
    ['?', 'Abrir esta ayuda'],
    ['Esc', 'Cerrar modales, ayuda o paleta'],
    ['Enter', 'Enviar chat cuando el cursor está en el composer'],
    ['Shift Enter', 'Nueva línea en el composer']
  ];

  return (
    <div className="command-palette-backdrop help-backdrop" role="dialog" aria-modal="true" aria-label="Atajos de teclado">
      <div className="help-panel">
        <header>
          <div>
            <span className="surface-eyebrow">Ayuda rápida</span>
            <h2>Atajos y modelo de navegación</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} title="Cerrar ayuda">
            <Icon name="close" />
          </button>
        </header>
        <section className="help-grid">
          {shortcuts.map(([key, description]) => (
            <div key={key} className="help-shortcut-row">
              <kbd>{key}</kbd>
              <span>{description}</span>
            </div>
          ))}
        </section>
        <p className="help-note">El sidebar contiene destinos. El chat es un panel conmutado, no una pantalla. El inspector aparece como drawer y no reduce el espacio vertical del workspace.</p>
      </div>
    </div>
  );
}

interface PaletteProps {
  actions: Array<{ id: string; label: string; action: () => void }>;
  onClose: () => void;
}

function CommandPalette({ actions, onClose }: PaletteProps) {
  const [query, setQuery] = useState('');
  const filtered = actions.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  return (
    <div className="command-palette-backdrop" role="dialog" aria-modal="true" aria-label="Comandos rápidos">
      <div className="command-palette">
        <div className="command-palette-search">
          <span>/</span>
          <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar módulo, acción o comando" />
          <kbd>Esc</kbd>
        </div>
        <div className="command-palette-list">
          {filtered.length ? filtered.map((item) => (
            <button key={item.id} type="button" onClick={() => { item.action(); onClose(); }}>
              <span>{item.label}</span>
              <span>↵</span>
            </button>
          )) : <div className="palette-empty">No hay acciones que coincidan.</div>}
        </div>
      </div>
    </div>
  );
}

interface WorkspacePickerDialogProps {
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
  onChooseExplorer: () => void;
  seedSuggested: boolean;
  onConfirm: (seed: boolean) => void;
  client: BagoClient;
}

type InspectState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | {
      kind: 'ready';
      configured: boolean;
      linked: boolean;
      bindingConfirmed: boolean;
      bindingReason: string;
      manifestExists: boolean;
    };

function WorkspacePickerDialog({ value, onChange, onClose, onChooseExplorer, seedSuggested, onConfirm, client }: WorkspacePickerDialogProps) {
  const bridge = getElectronBridge();
  const bridgeAvailable = Boolean(bridge?.chooseProjectRoot || bridge?.chooseWorkspaceRoot);
  const [inspect, setInspect] = useState<InspectState>({ kind: 'idle' });

  // Inspecciona el estado REAL del workspace en la ruta actual.
  // Esto consulta directamente el filesystem (vía /project/inspect) y NO
  // el snapshot cacheado del session manager. Es lo que evita ofrecer
  // "Sembrar y activar" cuando el workspace ya está OK.
  useEffect(() => {
    const clean = value.trim();
    if (!clean) {
      setInspect({ kind: 'idle' });
      return;
    }
    let cancelled = false;
    setInspect({ kind: 'loading' });
    const t = setTimeout(async () => {
      try {
        const data = await client.inspectProject(clean);
        if (cancelled) return;
        setInspect({
          kind: 'ready',
          configured: Boolean(data.configured),
          linked: Boolean(data.linked),
          bindingConfirmed: Boolean(data.binding_confirmed),
          bindingReason: String(data.binding_reason || ''),
          manifestExists: Boolean(data.manifest_exists)
        });
      } catch (err) {
        if (cancelled) return;
        setInspect({ kind: 'error', message: err instanceof Error ? err.message : 'Error al inspeccionar' });
      }
    }, 350);  // debounce: no lanzar por cada keystroke
    return () => { cancelled = true; clearTimeout(t); };
  }, [value, client]);

  // El workspace está REALMENTE listo si configured && linked && bindingConfirmed.
  // En ese caso NO se debe ofrecer "Sembrar y activar".
  const isRealReady = inspect.kind === 'ready' && inspect.configured && inspect.linked && inspect.bindingConfirmed;

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) onConfirm(!isRealReady);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [onClose, onConfirm, isRealReady]);

  return (
    <div className="command-palette-backdrop workspace-picker-backdrop" role="dialog" aria-modal="true" aria-label="Elegir workspace">
      <div className="command-palette workspace-picker">
        <div className="command-palette-search workspace-picker-search">
          <span>⌂</span>
          <input autoFocus value={value} onChange={(event) => onChange(event.target.value)} placeholder="Ruta completa del workspace" />
          <kbd>Ctrl+Enter</kbd>
        </div>
        <div className="workspace-picker-body">
          <p>Elige el workspace con el explorador nativo o pega la ruta completa manualmente.</p>
          {inspect.kind === 'loading' && <p className="workspace-picker-status">Inspeccionando…</p>}
          {inspect.kind === 'error' && <p className="workspace-picker-status is-error">⚠ {inspect.message}</p>}
          {inspect.kind === 'ready' && isRealReady && (
            <p className="workspace-picker-status is-ok">
              ✓ Workspace listo (configurado y vinculado{inspect.bindingReason ? `, ${inspect.bindingReason}` : ''}).
              Puedes activarlo directamente.
            </p>
          )}
          {inspect.kind === 'ready' && !isRealReady && (
            <p className="workspace-picker-status is-warn">
              ⚠ Workspace no configurado
              {!inspect.configured && ' · faltan archivos en .bago/'}
              {!inspect.linked && ' · no vinculado'}
              {!inspect.bindingConfirmed && ' · binding no confirmado'}
              {inspect.bindingReason ? ` (${inspect.bindingReason})` : ''}.
              Puedes inicializarlo al activarlo.
            </p>
          )}
          <div className="workspace-picker-example">
            <span>Ejemplo</span>
            <code>C:\Users\AMTEC_Terminal_1º\BAG4.8</code>
          </div>
        </div>
        <div className="workspace-picker-actions">
          <button type="button" className="secondary-button compact" onClick={onChooseExplorer} disabled={!bridgeAvailable}>Abrir Explorer</button>
          <button type="button" className="secondary-button compact" onClick={onClose}>Cancelar</button>
          {isRealReady ? (
            <button type="button" className="primary-button compact" onClick={() => onConfirm(false)}>Activar workspace</button>
          ) : (
            <>
              <button type="button" className="secondary-button compact" onClick={() => onConfirm(false)} disabled={inspect.kind === 'loading'}>Activar sin sembrar</button>
              <button type="button" className="primary-button compact" onClick={() => onConfirm(true)} disabled={inspect.kind === 'loading' || !value.trim()}>Sembrar y activar</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
