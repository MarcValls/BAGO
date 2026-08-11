import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react';
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
import { DrawerOverlay } from '@/components/DrawerOverlay';
import { CapabilityAnatomyModule } from '@/modules/capability-anatomy';
import { ExternalCapabilitiesPanel } from '@/modules/capability-anatomy/ExternalCapabilitiesPanel';
import { ToolsPanel } from '@/features/tools/ToolsPanel';
import { AgentEditorPanel } from '@/features/agents/AgentEditorPanel';
import { InterpreterPanel } from '@/features/interpretation/InterpreterPanel';
import { GitHubAuthPanel } from '@/features/github/GitHubAuthPanel';
import { useContextTree, type UseContextTreeState } from '@/features/context-tree/useContextTree';
import { usePanelManager } from '@/hooks/usePanelManager';
import { parseContextPatchRequests } from '@/features/context-tree/parseContextPatchRequests';
import type { ContextPatchRequest } from '@/features/context-tree/contextTreeTypes';
import { buildSnapshot } from '@/app/bootstrapSnapshot';
import { readRecord, readText, toStringList } from '@/shared/unknownValue';
import { normalizeChatResponse } from '@/shared/chatResponse';
import { FirstRunWizard } from '@/features/first-run/FirstRunWizard';
import { markFirstRunComplete, shouldShowFirstRun, shouldSkipAutomaticFirstRun } from '@/features/first-run/firstRun';
import { createShellActions, NAVIGATION_ORDER, type BagoAction } from '@/navigation/actionRegistry';
import { WorkspacePickerDialog } from '@/features/workspace/WorkspacePickerDialog';
import { canPersistWorkspaceAuthority } from '@/shared/workspaceAuthority';

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

function commandKey(command: string): string {
  return command.trim().replace(/^\/+/, '').replace(/[^\w]+/g, '_').replace(/^_+|_+$/g, '') || 'command';
}

function historyToTurns(history: BackendHistory | undefined): ChatTurn[] {
  if (!Array.isArray(history?.messages)) return [];
  return history.messages.slice(-30).map((message, index) => {
    const roleValue = String(message.role || 'assistant');
    const role: ChatTurn['role'] = roleValue === 'user' || roleValue === 'system' || roleValue === 'command' ? roleValue : 'assistant';
    const metadata = readRecord(message.metadata);
    const normalized = normalizeChatResponse(
      String(message.content || message.text || message.message || ''),
      metadata.response_state
    );
    return {
      id: String(message.id || `history-${index}`),
      role,
      text: normalized.text,
      status: normalized.state,
      receipt: (message.receipt || message.context_receipt || null) as Record<string, unknown> | null,
      provider: String(message.provider || metadata.provider || ''),
      model: String(message.model || metadata.model || ''),
      clarification: normalized.clarification,
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
  const [conversations, setConversations] = useState<import('@/contracts/backend').BackendConversations | null>(null);
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
  const { openDrawer, close: closeDrawer, isOpen } = usePanelManager();
  const [workspacePickerOpen, setWorkspacePickerOpen] = useState(false);
  const [workspacePickerValue, setWorkspacePickerValue] = useState('');
  const [firstRunOpen, setFirstRunOpen] = useState(() => shouldShowFirstRun(typeof window === 'undefined' ? null : window.localStorage));
  const [firstRunRequested, setFirstRunRequested] = useState(false);
  // Modelos activos del provider activo (Fase D). Se cruza con el router
  // para filtrar el desplegable del chat.
  const clientRef = useRef(createBagoClient(uiState.apiBase || readStoredApiBase(), uiState.apiToken));
  const conversationRevisionRef = useRef(0);

  // CANON[CTX-013]: el árbol de contexto vive aquí, no dentro del
  // módulo, para que tanto el chat (que muestra tarjetas inline de
  // validación) como el módulo de contexto operen sobre el mismo
  // estado. Se monta una vez por sesión.
  const contextTree = useContextTree(clientRef.current);
  const contextTreeRef = useRef(contextTree);
  contextTreeRef.current = contextTree;
  useEffect(() => {
    if (!firstRunOpen || firstRunRequested || !shouldSkipAutomaticFirstRun(snapshot)) return;
    markFirstRunComplete(window.localStorage);
    setFirstRunOpen(false);
  }, [firstRunOpen, firstRunRequested, snapshot]);
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

  const applyBootData = (
    data: Awaited<ReturnType<typeof clientRef.current.bootstrap>>,
    requestedConversationRevision = conversationRevisionRef.current
  ) => {
    const nextSnapshot = buildSnapshot(data);
    const nextHistory = (data.history || null) as BackendHistory | null;
    const conversationStateIsCurrent = requestedConversationRevision === conversationRevisionRef.current;
    const nextOpening = resolveOpeningState(nextSnapshot);
    setSnapshot(nextSnapshot);
    setOpening(nextOpening);
    setMenu((data.menu || null) as BackendMenu | null);
    setRoutes((data.routes || null) as BackendRoutes | null);
    setProviders((data.providers || null) as BackendProviders | null);
    setRouterState({
      list: (data.router_list || null) as BackendRouterList | null,
      policy: (data.router_policy || null) as BackendRouterPolicy | null
    });
    if (conversationStateIsCurrent) {
      setHistory(nextHistory);
      setConversations(data.conversations || null);
    }
    setFiles((data.files || null) as Record<string, unknown> | null);
    setTurns((current) => {
      if (!conversationStateIsCurrent) return current;
      return current.length ? current : historyToTurns(nextHistory || undefined);
    });
    if (nextOpening.id === 'enter_directly') {
      setUiState((current) => current.activeSection === 'chat' ? current : patchUiState(current, { activeSection: 'home' }));
    }
    return nextSnapshot;
  };

  const bootstrap = async () => {
    setBooting(true);
    setLastMessage('consultando backend');
    const requestedConversationRevision = conversationRevisionRef.current;
    try {
      const data = await clientRef.current.bootstrap();
      const nextSnapshot = applyBootData(data, requestedConversationRevision);
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

  const chooseWorkspacePath = async (defaultPath?: string): Promise<string | null> => {
    const bridge = getElectronBridge();
    const chooseRoot = bridge?.chooseProjectRoot || bridge?.chooseWorkspaceRoot;
    if (chooseRoot) {
      const selection = (await chooseRoot({ defaultPath: defaultPath || resolveWorkspaceStartPath() })) as WorkspaceSelectionResult | null;
      const selectedRoot = readSelectedWorkspace(selection);
      if (!selectedRoot) {
        setLastMessage('selección de workspace cancelada');
        return null;
      }
      return selectedRoot;
    }
    setLastMessage('el explorador nativo solo está disponible en Electron');
    return null;
  };

  const openWorkspacePicker = (): void => {
    setWorkspacePickerValue(resolveWorkspaceStartPath());
    setWorkspacePickerOpen(true);
  };

  const chooseWorkspaceFromHeader = (): void => {
    openWorkspacePicker();
  };

  // Alias so the two ControlSections calls can use different-looking props for the same function
  const onChooseWorkspaceAlternate = openWorkspacePicker;

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
    // Un snapshot inválido nunca puede reemplazar el último workspace válido.
    if (!canPersistWorkspaceAuthority(snapshot)) return;
    persistWorkspace.everPersistedRef.current = true;
    void clientRef.current.persistWorkspace(root).catch(() => {
      // Silenciar: la persistencia es best-effort
    });
  }, [
    snapshot?.workspace?.linkedToSession,
    snapshot?.workspace?.manifestState,
    snapshot?.workspace?.repoRoot,
    snapshot?.workspace?.root,
    snapshot?.project?.root
  ]);

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
      // Ctrl+1..7: navegar según el registro canónico compartido con el sidebar.
      if ((event.ctrlKey || event.metaKey) && /^[1-8]$/.test(event.key)) {
        event.preventDefault();
        const idx = parseInt(event.key, 10) - 1;
        const target = NAVIGATION_ORDER[idx];
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
        setWorkspacePickerOpen(false);
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
    const requestedConversationRevision = conversationRevisionRef.current;
    const next = await clientRef.current.bootstrapModern().catch(() => clientRef.current.bootstrap());
    return applyBootData(next, requestedConversationRevision);
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

  const activateWorkspaceRoot = async (selectedRoot: string, sourceLabel: string, options?: { seedAfterLink?: boolean; forceInit?: boolean }): Promise<boolean> => {
    const cleanRoot = selectedRoot.trim();
    if (!cleanRoot) {
      setLastMessage('selección de workspace cancelada');
      return false;
    }

    setAndPersistUiState({ workspaceHint: normalizeWorkspaceHint(cleanRoot) });
    setWorkspacePickerOpen(false);

    try {
      const nextRepairableState = snapshot?.workspace.manifestState;
      if (options?.forceInit || nextRepairableState === 'missing' || nextRepairableState === 'invalid' || nextRepairableState === 'legacy') {
        await clientRef.current.initProject(cleanRoot);
      }
      const linkResult = await clientRef.current.linkProject(cleanRoot);
      if (linkResult.ok === false) {
        setLastMessage(String(linkResult.message || 'no se pudo activar el workspace'));
        return false;
      }

      // El historial es parte del alcance del workspace confirmado. Se cambia
      // antes del bootstrap para no reutilizar turnos de la carpeta anterior.
      await clientRef.current.scopeWorkspaceConversation(cleanRoot);
      setTurns([]);
      setHistory(null);
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

      const backendRoot = String(nextSnapshot?.workspace.root || nextSnapshot?.project.root || '').trim();
      const normalizeRoot = (value: string) => value.replace(/[\\/]+$/, '').replace(/\\/g, '/').toLowerCase();
      const activated = Boolean(nextSnapshot?.project.root)
        && Boolean(nextSnapshot?.permissions.canChat)
        && Boolean(nextSnapshot?.workspace.linkedToSession)
        && normalizeRoot(backendRoot) === normalizeRoot(cleanRoot);
      if (!activated) {
        setLastMessage(`el backend no confirmó el workspace seleccionado: ${cleanRoot}`);
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
      try {
        let data: Record<string, unknown>;
        if (ns === 'blacklist') {
          data = await clientRef.current.getModelBlacklist();
        } else if (action === 'start') {
          data = await clientRef.current.startAutoConfig();
        } else if (action === 'apply') {
          data = await clientRef.current.applyAutoConfig();
        } else if (action === 'cancel') {
          data = await clientRef.current.cancelAutoConfig();
        } else if (!action || action === 'status') {
          data = await clientRef.current.getAutoConfigStatus();
        } else {
          const result: BackendCommandResult = { ok: false, message: `comando no reconocido: ${clean}` };
          setLastMessage(result.message || clean);
          return result;
        }
        let summary = '';
        if (ns === 'auto-config') {
          if (action === 'start') summary = `Auto-config lanzada (${data.models_to_test ?? 0} modelos a probar)`;
          else if (action === 'apply') {
            const applied = readRecord(data.applied);
            summary = data.ok ? `Config aplicada: default=${readText(applied.default_model)}` : readText(data.error) || 'falló';
          }
          else if (action === 'cancel') summary = 'Auto-config cancelada';
          else summary = `Auto-config status: ${data.status} (${data.tested_models ?? 0}/${data.total_models ?? 0})`;
        } else {
          const models = toStringList(data.models);
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

    // El composer de Chat también es una superficie de comandos. No envíes
    // slash commands al modelo: deben pasar por la autoridad /command para
    // cambiar el estado real de la sesión (por ejemplo, /mode A).
    if (text.startsWith('/') && !text.startsWith('//')) {
      setUiState((current) => patchUiState(current, { drafts: { ...current.drafts, chat: '' } }));
      await runCommand(text);
      return;
    }

    const stamp = Date.now();
    const attemptedProvider = String(snapshot.model.provider || '');
    const attemptedModel = String(snapshot.model.effectiveModel || snapshot.model.configuredModel || '');
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
      provider: attemptedProvider,
      model: attemptedModel,
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
      const normalized = normalizeChatResponse(
        String(payload.response || payload.message || ''),
        payload.ok === false ? 'failed' : payload.response_state
      );
      const clarification = readRecord(payload.clarification);
      setTurns((current) => current.map((turn) => {
        if (turn.id !== assistantBuffer.id) return turn;
        return {
          ...turn,
          text: normalized.text || turn.text,
          status: payload.ok === false ? 'failed' : normalized.state,
          receipt,
          provider: String(payload.provider || snapshot.model.provider || ''),
          model: String(payload.model || snapshot.model.effectiveModel || snapshot.model.configuredModel || ''),
          clarification: Object.keys(clarification).length ? clarification : normalized.clarification,
          raw: payload
        };
      }));
      setLastMessage(normalized.state === 'needs_confirmation' ? 'BAGO necesita confirmación' : normalized.text || 'respuesta recibida');
      await refreshAfterMutation();
    } catch (error) {
      const messageText = error instanceof Error ? error.message : 'falló el chat';
      const errorRecord = readRecord(error);
      setTurns((current) => current.map((turn) => turn.id === assistantBuffer.id ? {
        ...turn,
        status: 'failed',
        text: turn.text || messageText,
        provider: String(errorRecord.provider || turn.provider || attemptedProvider),
        model: String(errorRecord.model || turn.model || attemptedModel)
      } : turn));
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
    if (kind.includes('graph') || kind.includes('node')) return navigate('pipeline');
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
    confirm: async (options: { title: string; description: string; confirmLabel?: string }) => {
      // TODO: Replace with proper dialog implementation
      return window.confirm(options.description || options.title);
    },
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
    const base = createShellActions({
      navigate,
      openWorkspace: openWorkspacePicker,
      toggleSidebar: () => setUiState((current) => ({ ...current, sidebarCollapsed: !current.sidebarCollapsed })),
      toggleFocus: () => setAndPersistUiState({ globalMode: uiState.globalMode === 'focus' ? 'normal' : 'focus' }),
      toggleReview: () => setAndPersistUiState({ globalMode: uiState.globalMode === 'review' ? 'normal' : 'review' }),
      runCommand: (command) => { void runCommand(command); },
      runContextCommand: (command) => { void runContextCommand(command); },
      sidebarCollapsed: uiState.sidebarCollapsed,
      globalMode: uiState.globalMode
    });
    for (const action of combinedActions.filter((item) => item.visible && item.enabled)) {
      base.push({
        id: `backend-${action.id}`,
        object: 'Recomendación',
        verb: action.label,
        label: `Recomendación · ${action.label}`,
        group: 'Acciones recomendadas',
        icon: 'plus',
        action: () => { void runAction(action); }
      });
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
  const [reasoningDepth, setReasoningDepthState] = useState('normal');

  const configureProvider = async (provider: string, config: { enabled?: boolean; base_url?: string; api_key?: string; model?: string }): Promise<void> => {
    setLastMessage(`configurando proveedor ${provider}`);
    await clientRef.current.configureProvider(provider, config);
    await refreshAfterMutation();
  };

  const testProvider = (provider: string, config: { base_url?: string; api_key?: string; model?: string }) => clientRef.current.testProvider(provider, config);

  const createAndActivateDemo = async (root: string): Promise<boolean> => {
    setLastMessage('creando proyecto demo');
    const result = await clientRef.current.createDemoProject(root);
    if (result.ok === false) throw new Error(String(result.message || 'No se pudo crear el proyecto demo'));
    return activateWorkspaceRoot(root, 'proyecto demo activado', { seedAfterLink: true, forceInit: true });
  };

  const setSessionModelCb = async (modelKey: string | null): Promise<void> => {
    setLastMessage(modelKey ? `modelo sesión: ${modelKey}` : 'modelo sesión: auto');
    const previousModel = sessionModel;
    setSessionModelState(modelKey);
    try {
      const result = await clientRef.current.setSessionModel(modelKey);
      const confirmedModel = (result.session_model as string | null | undefined)
        ?? (result.model as string | null | undefined)
        ?? modelKey;
      setSessionModelState(confirmedModel ?? null);
      await refreshAfterMutation();
    } catch (error) {
      setSessionModelState(previousModel);
      throw error;
    }
  };

  const replaceConversationState = (payload: import('@/contracts/backend').BackendConversations): void => {
    const nextHistory = payload.history || null;
    setConversations(payload);
    setHistory(nextHistory);
    setTurns(historyToTurns(nextHistory || undefined));
  };

  const createNewConversation = async (): Promise<void> => {
    conversationRevisionRef.current += 1;
    const created = await clientRef.current.createConversation();
    const conversationId = String(
      created.conversation?.conversation_id
      || created.active_conversation_id
      || created.history?.conversation_id
      || ''
    ).trim();
    if (!conversationId) throw new Error('El backend no confirmó la nueva conversación.');
    replaceConversationState(created);
    const root = String(snapshot?.workspace.root || snapshot?.project.root || '').trim();
    if (root) await clientRef.current.scopeWorkspaceConversation(root, conversationId);
    await refreshAfterMutation();
    setLastMessage('nuevo chat creado');
    window.setTimeout(() => document.getElementById('bago-chat-composer')?.focus(), 0);
  };

  const switchConversation = async (conversationId: string): Promise<void> => {
    conversationRevisionRef.current += 1;
    const switched = await clientRef.current.switchConversation(conversationId);
    replaceConversationState(switched);
    const root = String(snapshot?.workspace.root || snapshot?.project.root || '').trim();
    if (root) await clientRef.current.scopeWorkspaceConversation(root, conversationId);
    await refreshAfterMutation();
    setLastMessage('conversación activada');
    window.setTimeout(() => document.getElementById('bago-chat-composer')?.focus(), 0);
  };

  const renameConversation = async (conversationId: string, title: string): Promise<void> => {
    const renamed = await clientRef.current.renameConversation(conversationId, title);
    setConversations(renamed);
    setLastMessage('conversación renombrada');
  };

  const archiveConversation = async (conversationId: string): Promise<void> => {
    conversationRevisionRef.current += 1;
    const archived = await clientRef.current.archiveConversation(conversationId);
    replaceConversationState(archived);
    const activeId = String(archived.active_conversation_id || archived.history?.conversation_id || '').trim();
    const root = String(snapshot?.workspace.root || snapshot?.project.root || '').trim();
    if (root && activeId) await clientRef.current.scopeWorkspaceConversation(root, activeId);
    await refreshAfterMutation();
    setLastMessage('conversación archivada');
  };

  const setReasoningDepthCb = async (depth: string): Promise<void> => {
    const previous = reasoningDepth;
    setReasoningDepthState(depth);
    try {
      const result = await clientRef.current.setReasoningDepth(depth);
      setReasoningDepthState(String(result.depth || depth));
      setLastMessage(`profundidad: ${String(result.label || depth)}`);
    } catch (error) {
      setReasoningDepthState(previous);
      throw error;
    }
  };

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('theme-light', uiState.appearanceTheme === 'light');
    root.classList.toggle('theme-dark', uiState.appearanceTheme === 'dark');
    root.style.colorScheme = uiState.appearanceTheme;

    return () => {
      root.classList.remove('theme-light', 'theme-dark');
      root.style.removeProperty('color-scheme');
    };
  }, [uiState.appearanceTheme]);

  useEffect(() => {
    clientRef.current.getSessionModel().then((r) => {
      const m = (r?.session_model as string | null | undefined)
        ?? (r?.model as string | null | undefined);
      setSessionModelState(m ?? null);
    }).catch(() => null);
    clientRef.current.getReasoningDepth().then((r) => {
      setReasoningDepthState(String(r?.depth || 'normal'));
    }).catch(() => null);
  }, []);

  return (
    <>
      <div className={`app-root mode-${uiState.globalMode} theme-${uiState.appearanceTheme} ${uiState.sidebarCollapsed ? 'sidebar-collapsed' : ''} section-${uiState.activeSection}`}>
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
          onSetAppearanceTheme={(theme) => setAndPersistUiState({ appearanceTheme: theme })}
          onRunCommand={(command) => void runCommand(command)}
          onChooseWorkspace={chooseWorkspaceFromHeader}
          onGoHome={() => {
            try { window.sessionStorage.removeItem('bago.start.chat-mode'); } catch { /* storage unavailable */ }
            navigate('home');
          }}
          onOpenHelp={() => setAndPersistUiState({ helpOpen: true })}
          globalMode={uiState.globalMode}
          appearanceTheme={uiState.appearanceTheme}
          sidebarCollapsed={uiState.sidebarCollapsed}
        />

        <div className="app-body">
          {uiState.globalMode === 'normal' && (
            <MainSidebar
              activeSection={uiState.activeSection}
              snapshot={snapshot}
              workspaceHint={uiState.workspaceHint}
              collapsed={uiState.sidebarCollapsed}
              onNavigate={navigate}
              openDrawer={openDrawer}
              onOpenDrawer={(id) => openDrawer ? closeDrawer() : open(id)}
            />
          )}

          <div className="app-main-area">
            <div className="workspace-area">
              <WorkspaceShell
                activeSection={uiState.activeSection}
                snapshot={snapshot}
                mode={uiState.globalMode}
                showReadiness={false}
                showGlobalChips={false}
                onChooseWorkspace={openWorkspacePicker}
                onRefresh={bootstrap}
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
                  conversations={conversations}
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
                  reasoningDepth={reasoningDepth}
                  onSetReasoningDepth={setReasoningDepthCb}
                  onCreateConversation={createNewConversation}
                  onSwitchConversation={switchConversation}
                  onRenameConversation={renameConversation}
                  onArchiveConversation={archiveConversation}
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
        {(booting || busyCount > 0 || snapshot?.system.state === 'error') && (
          <ActivityToast message={lastMessage} busy={booting || busyCount > 0} state={snapshot?.system.state || 'unknown'} />
        )}
      </div>

      {uiState.commandPaletteOpen && (
        <CommandPalette actions={paletteActions} onClose={() => setAndPersistUiState({ commandPaletteOpen: false })} />
      )}
      {uiState.helpOpen && (
        <HelpOverlay
          onClose={() => setAndPersistUiState({ helpOpen: false })}
          onOpenFirstRun={() => {
            setAndPersistUiState({ helpOpen: false });
            setFirstRunRequested(true);
            setFirstRunOpen(true);
          }}
        />
      )}
      {firstRunOpen && !booting && snapshot && (firstRunRequested || !shouldSkipAutomaticFirstRun(snapshot)) && (
        <FirstRunWizard
          snapshot={snapshot}
          providers={providers}
          busy={busyCount > 0}
          onRefresh={bootstrap}
          onConfigureProvider={configureProvider}
          onTestProvider={testProvider}
          onActivateWorkspace={(root) => activateWorkspaceRoot(root, 'workspace activado desde el recorrido', { seedAfterLink: true })}
          onCreateDemo={createAndActivateDemo}
          client={clientRef.current}
          onChooseWorkspace={chooseWorkspacePath}
          onClose={() => {
            setFirstRunRequested(false);
            setFirstRunOpen(false);
          }}
          onFinish={() => {
            markFirstRunComplete(window.localStorage);
            setFirstRunRequested(false);
            setFirstRunOpen(false);
            openShell(snapshot.permissions.canChat ? 'chat' : 'home');
          }}
        />
      )}
      {workspacePickerOpen && (
      <WorkspacePickerDialog
          value={workspacePickerValue}
          onChange={setWorkspacePickerValue}
          onClose={() => setWorkspacePickerOpen(false)}
          onChooseExplorer={chooseWorkspacePath}
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

      <DrawerOverlay isOpen={isOpen('capabilities')} onClose={closeDrawer} position="left" width={320}>
        <CapabilityAnatomyModule client={clientRef.current} onInspect={(selection) => onInspect(selection, 'detail')} />
        <ExternalCapabilitiesPanel client={clientRef.current} />
      </DrawerOverlay>

      <DrawerOverlay isOpen={isOpen('pipeline')} onClose={closeDrawer} position="bottom" height={400}>
        <div className="drawer-pipeline-header">
          <h3>Pipeline</h3>
        <button type="button" onClick={closeDrawer} aria-label="Cerrar"><Icon name="close" size={16} /></button>
        </div>
        <div className="drawer-pipeline-content">
          <ControlSections
            section="pipeline"
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
            onChooseWorkspace={onChooseWorkspaceAlternate}
            onOpenPalette={() => setAndPersistUiState({ commandPaletteOpen: true })}
            onRefresh={bootstrap}
            menu={menu}
            routes={routes}
            providers={providers}
            router={routerState}
            history={history}
            conversations={conversations}
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
            reasoningDepth={reasoningDepth}
            onSetReasoningDepth={setReasoningDepthCb}
            onCreateConversation={createNewConversation}
            onSwitchConversation={switchConversation}
            onRenameConversation={renameConversation}
            onArchiveConversation={archiveConversation}
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
        </div>
      </DrawerOverlay>

      <DrawerOverlay isOpen={isOpen('tools')} onClose={closeDrawer} position="right" width={280}>
        <div className="drawer-tools-header">
          <h3>Herramientas</h3>
          <button type="button" onClick={closeDrawer} aria-label="Cerrar"><Icon name="close" size={16} /></button>
        </div>
        <div className="drawer-tools-content">
          <ToolsPanel client={clientRef.current} />
        </div>
      </DrawerOverlay>

      <DrawerOverlay isOpen={isOpen('agents')} onClose={closeDrawer} position="right" width={480}>
        <AgentEditorPanel client={clientRef.current} onClose={closeDrawer} />
      </DrawerOverlay>

      <DrawerOverlay isOpen={isOpen('interpreter')} onClose={closeDrawer} position="right" width={440}>
        <InterpreterPanel client={clientRef.current} onClose={closeDrawer} />
      </DrawerOverlay>

      <DrawerOverlay isOpen={isOpen('github-auth')} onClose={closeDrawer} position="right" width={400}>
        <GitHubAuthPanel client={clientRef.current} onClose={closeDrawer} />
      </DrawerOverlay>
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
  onOpenFirstRun: () => void;
}

function HelpOverlay({ onClose, onOpenFirstRun }: HelpOverlayProps) {
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
        <button type="button" className="secondary-button" onClick={onOpenFirstRun}>Abrir recorrido inicial</button>
        <p className="help-note">El sidebar contiene destinos. El chat es un panel conmutado, no una pantalla. El inspector aparece como drawer y no reduce el espacio vertical del workspace.</p>
      </div>
    </div>
  );
}

interface PaletteProps {
  actions: BagoAction[];
  onClose: () => void;
}

function CommandPalette({ actions, onClose }: PaletteProps) {
  const [query, setQuery] = useState('');
  const needle = query.trim().toLowerCase();
  const filtered = actions.filter((item) => [item.label, item.object, item.verb, item.group, ...(item.keywords || [])].join(' ').toLowerCase().includes(needle));

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
              <span className="palette-item-main"><Icon name={item.icon} size={14} /><span><strong>{item.label}</strong><small>{item.group}</small></span></span>
              <kbd>{item.shortcut || '↵'}</kbd>
            </button>
          )) : <div className="palette-empty">No hay acciones que coincidan.</div>}
        </div>
      </div>
    </div>
  );
}
