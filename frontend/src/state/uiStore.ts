import type { ActiveSection, ChatMode, GlobalMode, PanelId } from '@/contracts/backend';

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
  appearanceTheme: 'dark' | 'light';
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
  // Panel auxiliar activo (agents | interpreter | github-auth | tools | system | capabilities | null)
  activePanel: PanelId | null;
  // Pila de historial de panels para focus return
  panelHistory: PanelId[];
}

export interface UiStatePatch {
  sidebarCollapsed?: boolean;
  activeSection?: ActiveSection;
  globalMode?: GlobalMode;
  chatMode?: ChatMode;
  appearanceTheme?: 'dark' | 'light';
  helpOpen?: boolean;
  commandPaletteOpen?: boolean;
  apiBase?: string;
  apiToken?: string;
  workspaceHint?: string;
  drafts?: Record<string, string>;
  contextBankPending?: ContextBankPending[];
  contextEditPatchId?: string | null;
  activePanel?: PanelId | null;
  panelHistory?: PanelId[];
}


function normalizeGlobalMode(value: unknown): GlobalMode {
  if (value === 'normal' || value === 'focus' || value === 'review') return value;
  return 'normal';
}

function normalizeAppearanceTheme(value: unknown): 'dark' | 'light' {
  return value === 'light' ? 'light' : 'dark';
}

export function normalizeActiveSection(value: unknown): ActiveSection {
  const allowed: ActiveSection[] = ['home', 'chat', 'workspace', 'pipeline', 'evidence', 'context', 'system'];
  if (value === 'providers') return 'system';
  if (value === 'chat') return 'home';
  if (value === 'graph') return 'pipeline';
  return allowed.includes(value as ActiveSection) ? value as ActiveSection : 'home';
}

export function createDefaultUiState(): UiState {
  return {
    sidebarCollapsed: false,
    activeSection: 'home',
    globalMode: 'normal',
    chatMode: 'live',
    appearanceTheme: 'dark',
    helpOpen: false,
    commandPaletteOpen: false,
    apiBase: '',
    apiToken: '',
    workspaceHint: '',
    drafts: {},
    contextBankPending: [],
    contextEditPatchId: null,
    activePanel: null,
    panelHistory: []
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
      globalMode: normalizeGlobalMode(rest.globalMode),
      appearanceTheme: normalizeAppearanceTheme(rest.appearanceTheme),
      activePanel: rest.activePanel ?? null,
      panelHistory: rest.panelHistory ?? []
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
    appearanceTheme: state.appearanceTheme,
    helpOpen: state.helpOpen,
    commandPaletteOpen: state.commandPaletteOpen,
    apiBase: state.apiBase,
    workspaceHint: state.workspaceHint,
    drafts: state.drafts,
    contextBankPending: state.contextBankPending,
    contextEditPatchId: state.contextEditPatchId,
    activePanel: state.activePanel,
    panelHistory: state.panelHistory
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
