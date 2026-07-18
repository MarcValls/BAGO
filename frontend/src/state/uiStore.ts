import type { ActiveSection, ChatMode, GlobalMode } from '@/contracts/backend';

const KEY = 'bago.ui.state';

export interface ContextBankPending {
  id: string;
  // kind: 'file' | 'directory' | 'source' para que el ContextBankItem
  // sepa qué tipo de item reconstruir.
  kind: 'file' | 'directory' | 'source';
  path: string;
  title: string;
  // 'tree' añade al árbol; 'pack' añade al pack activo.
  destination: 'tree' | 'pack';
  createdAt: string;
}

export interface UiState {
  sidebarCollapsed: boolean;
  activeSection: ActiveSection;
  globalMode: GlobalMode;
  chatMode: ChatMode;
  helpOpen: boolean;
  commandPaletteOpen: boolean;
  apiBase: string;
  apiToken: string;
  workspaceHint: string;
  drafts: Record<string, string>;
  // CANON[CTX-007]: cola de elementos pendientes de añadir al Banco
  // contextual desde otras pantallas (Workspace, Evidence, etc.). Se
  // consume una vez y se elimina.
  contextBankPending: ContextBankPending[];
  // CANON[CTX-015]: id de patch a abrir en modo edición cuando el
  // usuario hace click en "Editar" desde el chat.
  contextEditPatchId: string | null;
}

export interface UiStatePatch {
  sidebarCollapsed?: boolean;
  activeSection?: ActiveSection;
  globalMode?: GlobalMode;
  chatMode?: ChatMode;
  helpOpen?: boolean;
  commandPaletteOpen?: boolean;
  apiBase?: string;
  apiToken?: string;
  workspaceHint?: string;
  drafts?: Record<string, string>;
  contextBankPending?: ContextBankPending[];
  contextEditPatchId?: string | null;
}


function normalizeGlobalMode(value: unknown): GlobalMode {
  if (value === 'normal' || value === 'focus' || value === 'review') return value;
  return 'normal';
}

function normalizeActiveSection(value: unknown): ActiveSection {
  const allowed: ActiveSection[] = ['home', 'chat', 'workspace', 'graph', 'pipeline', 'evidence', 'context', 'system'];
  if (value === 'providers') return 'system';
  return allowed.includes(value as ActiveSection) ? value as ActiveSection : 'home';
}

export function createDefaultUiState(): UiState {
  return {
    sidebarCollapsed: false,
    activeSection: 'home',
    globalMode: 'normal',
    chatMode: 'live',
    helpOpen: false,
    commandPaletteOpen: false,
    apiBase: '',
    apiToken: '',
    workspaceHint: '',
    drafts: {},
    contextBankPending: [],
    contextEditPatchId: null
  };
}

export function loadUiState(): UiState {
  if (typeof window === 'undefined') {
    return createDefaultUiState();
  }
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return createDefaultUiState();
    const parsed = JSON.parse(raw) as Partial<UiState> & { chatPanel?: unknown };
    const { chatPanel: _legacyChatPanel, apiToken: _legacyApiToken, ...rest } = parsed;
    return {
      ...createDefaultUiState(),
      ...rest,
      drafts: rest.drafts || {},
      activeSection: normalizeActiveSection(rest.activeSection),
      globalMode: normalizeGlobalMode(rest.globalMode)
    };
  } catch {
    return createDefaultUiState();
  }
}

export function persistUiState(state: UiState): void {
  if (typeof window === 'undefined') return;
  const persistedState: Omit<UiState, 'apiToken'> = {
    sidebarCollapsed: state.sidebarCollapsed,
    activeSection: state.activeSection,
    globalMode: state.globalMode,
    chatMode: state.chatMode,
    helpOpen: state.helpOpen,
    commandPaletteOpen: state.commandPaletteOpen,
    apiBase: state.apiBase,
    workspaceHint: state.workspaceHint,
    drafts: state.drafts,
    contextBankPending: state.contextBankPending,
    contextEditPatchId: state.contextEditPatchId
  };
  localStorage.setItem(KEY, JSON.stringify(persistedState));
}

export function patchUiState(state: UiState, patch: UiStatePatch): UiState {
  return {
    ...state,
    ...patch,
    drafts: patch.drafts ? { ...state.drafts, ...patch.drafts } : state.drafts,
    contextBankPending: patch.contextBankPending ? patch.contextBankPending : state.contextBankPending
  };
}
