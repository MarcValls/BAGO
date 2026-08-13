// src/features/workspace/useWorkspaceEditor.ts
// Estado del editor: tabs, dirty, guardado, selección, etc.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { BagoClient } from '@/api/client';
import type {
  OpenFileTab,
  WorkspaceDiagnostic,
  WorkspacePattern,
  WorkspaceFilter,
  BottomPanel,
  InspectorState,
  SelectedRange,
  OutputEntry,
  ExplorerNode
} from './workspaceTypes';
import type { ContextBankItem, ContextNode } from '@/features/context-tree/contextTreeTypes';
import {
  hashContent,
  readWorkspaceFile,
  writeWorkspaceFile,
  listWorkspaceFiles,
  WorkspaceApiError
} from './workspaceApi';
import { detectLanguage, isBinaryHeuristic } from './detectLanguage';
import { runLocalDiagnostics } from './runLocalDiagnostics';
import { detectPatterns } from './detectCodePatterns';

const MAX_FILE_SIZE = 5_000_000; // 5 MB.
const WORKSPACE_EDITOR_STATE_KEY = 'bago.workspace.editor.state';

let tabCounter = 0;
function nextTabId() {
  tabCounter += 1;
  return `t-${Date.now()}-${tabCounter}`;
}

let outputCounter = 0;
function nextOutputId() {
  outputCounter += 1;
  return `o-${Date.now()}-${outputCounter}`;
}

export interface UseWorkspaceEditorState {
  tabs: OpenFileTab[];
  activePath: string | null;
  activeTab: OpenFileTab | null;
  filter: WorkspaceFilter;
  query: string;
  expandedDirectories: string[];
  inspector: InspectorState;
  bottomPanel: BottomPanel;
  inspectorOpen: boolean;
  selectedRange: SelectedRange | null;
  output: OutputEntry[];
  error: string | null;
  busy: boolean;
  explorer: ExplorerNode[];
  loadingExplorer: boolean;
  openTabs: (paths: string[]) => Promise<void>;
  openFile: (path: string) => Promise<void>;
  closeTab: (path: string) => void;
  setActive: (path: string) => void;
  setContent: (path: string, content: string) => void;
  saveTab: (path: string) => Promise<void>;
  saveAll: () => Promise<void>;
  revertTab: (path: string) => void;
  setFilter: (filter: WorkspaceFilter) => void;
  setQuery: (query: string) => void;
  toggleDirectory: (path: string) => void;
  setInspector: (inspector: InspectorState) => void;
  setInspectorOpen: (open: boolean) => void;
  setBottomPanel: (panel: BottomPanel) => void;
  setSelectedRange: (range: SelectedRange | null) => void;
  refreshExplorer: () => Promise<void>;
  refreshTab: (path: string) => Promise<void>;
  appendOutput: (entry: Omit<OutputEntry, 'id' | 'ts'>) => void;
  clearOutput: () => void;
  runDiagnosticsForTab: (path: string) => Promise<void>;
  markInContext: (path: string, inContext: boolean) => void;
  markWithEvidence: (path: string, withEvidence: boolean) => void;
}

interface HookProps {
  client: BagoClient;
  workspaceRoot: string;
  initialPath?: string | null;
  // Items del Banco contextual (para marcar inContext).
  contextBank?: ContextBankItem[];
  contextTreeNodes?: ContextNode[];
}

export interface WorkspaceEditorResetState {
  tabs: OpenFileTab[];
  activePath: string | null;
  selectedRange: SelectedRange | null;
  inspector: InspectorState;
  bottomPanel: BottomPanel;
  explorer: ExplorerNode[];
  loadingExplorer: boolean;
  error: string | null;
  busy: boolean;
  output: OutputEntry[];
  expandedDirectories: string[];
}

export interface PersistedWorkspaceEditorState {
  workspaceRoot: string;
  tabs: OpenFileTab[];
  activePath: string | null;
  selectedRange: SelectedRange | null;
  inspector: InspectorState;
  bottomPanel: BottomPanel;
  explorer: ExplorerNode[];
  loadingExplorer: boolean;
  error: string | null;
  busy: boolean;
  output: OutputEntry[];
  expandedDirectories: string[];
}

export function readPersistedWorkspaceEditorState(workspaceRoot: string): PersistedWorkspaceEditorState | null {
  if (typeof window === 'undefined' || !workspaceRoot) return null;
  try {
    const raw = window.localStorage.getItem(WORKSPACE_EDITOR_STATE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PersistedWorkspaceEditorState> | null;
    if (!parsed || parsed.workspaceRoot !== workspaceRoot) return null;
    return {
      workspaceRoot,
      tabs: Array.isArray(parsed.tabs) ? parsed.tabs : [],
      activePath: typeof parsed.activePath === 'string' ? parsed.activePath : null,
      selectedRange: parsed.selectedRange && typeof parsed.selectedRange === 'object' ? parsed.selectedRange as SelectedRange : null,
      inspector: parsed.inspector && typeof parsed.inspector === 'object' ? parsed.inspector as InspectorState : { kind: null },
      bottomPanel: parsed.bottomPanel === 'problems' || parsed.bottomPanel === 'changes' || parsed.bottomPanel === 'patterns' || parsed.bottomPanel === 'output' ? parsed.bottomPanel : null,
      explorer: Array.isArray(parsed.explorer) ? parsed.explorer as ExplorerNode[] : [],
      loadingExplorer: Boolean(parsed.loadingExplorer),
      error: typeof parsed.error === 'string' ? parsed.error : null,
      busy: Boolean(parsed.busy),
      output: Array.isArray(parsed.output) ? parsed.output as OutputEntry[] : [],
      expandedDirectories: Array.isArray(parsed.expandedDirectories) ? parsed.expandedDirectories.filter((value): value is string => typeof value === 'string') : []
    };
  } catch {
    return null;
  }
}

export function persistWorkspaceEditorState(state: PersistedWorkspaceEditorState): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(WORKSPACE_EDITOR_STATE_KEY, JSON.stringify(state));
  } catch {
    // Persistencia best-effort.
  }
}

export function createWorkspaceEditorResetState(): WorkspaceEditorResetState {
  return {
    tabs: [],
    activePath: null,
    selectedRange: null,
    inspector: { kind: null },
    bottomPanel: null,
    explorer: [],
    loadingExplorer: false,
    error: null,
    busy: false,
    output: [],
    expandedDirectories: []
  };
}

export function useWorkspaceEditor(props: HookProps): UseWorkspaceEditorState {
  const persisted = readPersistedWorkspaceEditorState(props.workspaceRoot);
  const [tabs, setTabs] = useState<OpenFileTab[]>(() => persisted?.tabs || []);
  const [activePath, setActivePath] = useState<string | null>(() => persisted?.activePath || null);
  const [filter, setFilter] = useState<WorkspaceFilter>('all');
  const [query, setQuery] = useState('');
  const [expandedDirectories, setExpandedDirectories] = useState<string[]>(() => persisted?.expandedDirectories || []);
  const [inspector, setInspector] = useState<InspectorState>(() => persisted?.inspector || { kind: null });
  const [bottomPanel, setBottomPanel] = useState<BottomPanel>(() => persisted?.bottomPanel || null);
  const [inspectorOpen, setInspectorOpen] = useState<boolean>(true);
  const [selectedRange, setSelectedRange] = useState<SelectedRange | null>(() => persisted?.selectedRange || null);
  const [output, setOutput] = useState<OutputEntry[]>(() => persisted?.output || []);
  const [error, setError] = useState<string | null>(() => persisted?.error || null);
  const [busy, setBusy] = useState<boolean>(() => persisted?.busy || false);
  const [explorer, setExplorer] = useState<ExplorerNode[]>(() => persisted?.explorer || []);
  const [loadingExplorer, setLoadingExplorer] = useState<boolean>(() => persisted?.loadingExplorer || false);
  const workspaceRootRef = useRef(props.workspaceRoot);
  const previousWorkspaceRootRef = useRef(props.workspaceRoot);
  workspaceRootRef.current = props.workspaceRoot;

  const appendOutput = useCallback((entry: Omit<OutputEntry, 'id' | 'ts'>) => {
    setOutput((current) => [
      ...current.slice(-200),
      { id: nextOutputId(), ts: new Date().toISOString(), ...entry }
    ]);
  }, []);

  const clearOutput = useCallback(() => {
    setOutput([]);
  }, []);

  const refreshExplorer = useCallback(async () => {
    const root = workspaceRootRef.current;
    if (!root) {
      setExplorer([]);
      return;
    }
    setLoadingExplorer(true);
    try {
      const entries = await listWorkspaceFiles(props.client, root);
      const tree = buildExplorerTree(entries, root);
      setExplorer(tree);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setLoadingExplorer(false);
    }
  }, [props.client]);

  useEffect(() => {
    persistWorkspaceEditorState({
      workspaceRoot: props.workspaceRoot,
      tabs,
      activePath,
      selectedRange,
      inspector,
      bottomPanel,
      explorer,
      loadingExplorer,
      error,
      busy,
      output,
      expandedDirectories
    });
  }, [props.workspaceRoot, tabs, activePath, selectedRange, inspector, bottomPanel, explorer, loadingExplorer, error, busy, output, expandedDirectories]);

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (!tabs.some((tab) => tab.state === 'dirty')) return;
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [tabs]);

  useEffect(() => {
    const workspaceChanged = previousWorkspaceRootRef.current !== props.workspaceRoot;
    previousWorkspaceRootRef.current = props.workspaceRoot;
    if (workspaceChanged) {
      const reset = createWorkspaceEditorResetState();
      setTabs(reset.tabs);
      setActivePath(reset.activePath);
      setSelectedRange(reset.selectedRange);
      setInspector(reset.inspector);
      setBottomPanel(reset.bottomPanel);
      setExplorer(reset.explorer);
      setLoadingExplorer(reset.loadingExplorer);
      setError(reset.error);
      setBusy(reset.busy);
      setOutput(reset.output);
      setExpandedDirectories(reset.expandedDirectories);
    }
    void refreshExplorer();
  }, [props.workspaceRoot, refreshExplorer]);

  const runDiagnosticsForTab = useCallback(async (path: string) => {
    setTabs((current) => current.map((tab) => {
      if (tab.path !== path) return tab;
      const language = detectLanguage(path);
      const diagnostics = runLocalDiagnostics(path, tab.content);
      const patterns = detectPatterns(path, tab.content);
      // Filtramos patterns por language (algunos aplican a todo).
      const filtered = patterns.filter((p) => {
        if (p.kind === 'console-log' || p.kind === 'any-usage' || p.kind === 'unused-import') {
          return ['javascript', 'typescript', 'jsx', 'tsx'].includes(language);
        }
        return true;
      });
      return { ...tab, diagnostics, patterns: filtered };
    }));
  }, []);

  const openFile = useCallback(async (path: string) => {
    setError(null);
    if (isBinaryHeuristic(path)) {
      setError(`Archivo binario: ${path}. No editable.`);
      return;
    }
    setBusy(true);
    try {
      const file = await readWorkspaceFile(props.client, path);
      if (file.size && file.size > MAX_FILE_SIZE) {
        setError(`Archivo grande (${Math.round((file.size || 0) / 1024)} KB). Se cargará como solo lectura.`);
        appendOutput({ channel: 'info', level: 'warn', text: `Archivo grande ${path} (${file.size} bytes) — solo lectura` });
      }
      const baseline = file.content;
      const content = baseline;
      const language = file.language;
      const diagnostics = runLocalDiagnostics(path, content);
      const patterns = detectPatterns(path, content);
      setTabs((current) => {
        const existing = current.find((tab) => tab.path === path);
        if (existing) {
          // Si ya está abierto y no está dirty, recargar contenido.
          if (existing.state === 'clean' && existing.content !== content) {
            return current.map((tab) => tab.path === path ? {
              ...tab,
              baseline,
              content,
              language,
              diagnostics,
              patterns,
              loadedAt: file.modified,
              baselineHash: hashContent(baseline)
            } : tab);
          }
          return current;
        }
        const tab: OpenFileTab = {
          id: nextTabId(),
          path,
          language,
          label: path.split(/[\\/]/).pop() || path,
          baseline,
          content,
          state: file.size && file.size > MAX_FILE_SIZE ? 'readonly' : 'clean',
          inContext: false,
          withEvidence: false,
          diagnostics,
          patterns,
          loadedAt: file.modified,
          baselineHash: hashContent(baseline)
        };
        return [...current, tab];
      });
      setActivePath(path);
      setInspector({ kind: 'file', refId: path });
      setInspectorOpen(true);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      const apiError = err instanceof WorkspaceApiError ? err : new Error(message);
      setError(apiError.message);
      appendOutput({ channel: 'info', level: 'error', text: `Error al leer ${path}: ${apiError.message}` });
    } finally {
      setBusy(false);
    }
  }, [props.client, appendOutput]);

  const openTabs = useCallback(async (paths: string[]) => {
    for (const path of paths) {
      // eslint-disable-next-line no-await-in-loop
      await openFile(path);
    }
  }, [openFile]);

  useEffect(() => {
    if (props.initialPath) {
      void openFile(props.initialPath);
    }
    // Sólo al montar o cuando cambia la ruta inicial.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [props.initialPath]);

  const closeTab = useCallback((path: string) => {
    const target = tabs.find((tab) => tab.path === path);
    if (target?.state === 'dirty') {
      setError(`Guarda o revierte ${path} antes de cerrarlo.`);
      appendOutput({ channel: 'info', level: 'warn', text: `Cierre bloqueado para ${path} por cambios sin guardar` });
      return;
    }
    setTabs((current) => {
      const next = current.filter((tab) => tab.path !== path);
      return next;
    });
    setActivePath((current) => {
      if (current !== path) return current;
      const remaining = tabs.filter((tab) => tab.path !== path);
      return remaining.length > 0 ? remaining[remaining.length - 1].path : null;
    });
    if (inspector.kind === 'file' && inspector.refId === path) {
      setInspector({ kind: null });
    }
  }, [tabs, inspector, appendOutput]);

  const setActive = useCallback((path: string) => {
    setActivePath(path);
    setInspector({ kind: 'file', refId: path });
  }, []);

  const setContent = useCallback((path: string, content: string) => {
    setTabs((current) => current.map((tab) => {
      if (tab.path !== path) return tab;
      if (tab.state === 'readonly') return tab;
      const dirty = content !== tab.baseline;
      // Re-analizamos diagnósticos y patrones al editar.
      const diagnostics = runLocalDiagnostics(path, content);
      const patterns = detectPatterns(path, content);
      return {
        ...tab,
        content,
        diagnostics,
        patterns,
        state: dirty ? 'dirty' : 'clean'
      };
    }));
  }, []);

  const saveTab = useCallback(async (path: string) => {
    const tab = tabs.find((t) => t.path === path);
    if (!tab) return;
    if (tab.state === 'readonly') {
      appendOutput({ channel: 'save', level: 'warn', text: `Archivo ${path} está en solo lectura` });
      return;
    }
    setTabs((current) => current.map((t) => t.path === path ? { ...t, state: 'saving' } : t));
    try {
      const result = await writeWorkspaceFile(props.client, path, tab.content);
      setTabs((current) => current.map((t) => t.path === path ? {
        ...t,
        baseline: tab.content,
        baselineHash: hashContent(tab.content),
        state: 'saved',
        loadedAt: result.saved
      } : t));
      appendOutput({ channel: 'save', level: 'ok', text: `Guardado ${path} (${result.size} bytes)` });
      setTimeout(() => {
        setTabs((current) => current.map((t) => t.path === path ? { ...t, state: 'clean' } : t));
      }, 1200);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setTabs((current) => current.map((t) => t.path === path ? { ...t, state: 'save_error' } : t));
      setError(`No se pudo guardar ${path}: ${message}`);
      appendOutput({ channel: 'save', level: 'error', text: `Error guardando ${path}: ${message}` });
    }
  }, [tabs, props.client, appendOutput]);

  const saveAll = useCallback(async () => {
    const dirty = tabs.filter((tab) => tab.state === 'dirty');
    for (const tab of dirty) {
      // eslint-disable-next-line no-await-in-loop
      await saveTab(tab.path);
    }
  }, [tabs, saveTab]);

  const revertTab = useCallback((path: string) => {
    setTabs((current) => current.map((tab) => {
      if (tab.path !== path) return tab;
      return {
        ...tab,
        content: tab.baseline,
        state: 'clean',
        diagnostics: runLocalDiagnostics(path, tab.baseline),
        patterns: detectPatterns(path, tab.baseline)
      };
    }));
  }, []);

  const toggleDirectory = useCallback((path: string) => {
    setExpandedDirectories((current) => current.includes(path)
      ? current.filter((p) => p !== path)
      : [...current, path]);
  }, []);

  const refreshTab = useCallback(async (path: string) => {
    await openFile(path);
  }, [openFile]);

  const markInContext = useCallback((path: string, inContext: boolean) => {
    setTabs((current) => current.map((tab) => tab.path === path ? { ...tab, inContext } : tab));
  }, []);

  const markWithEvidence = useCallback((path: string, withEvidence: boolean) => {
    setTabs((current) => current.map((tab) => tab.path === path ? { ...tab, withEvidence } : tab));
  }, []);

  // Sincronizar con el árbol de contexto: marcar pestañas que ya están
  // en el árbol y desmarcar las que ya no.
  useEffect(() => {
    if (!props.contextTreeNodes) return;
    const inContextPaths = new Set<string>();
    for (const node of Object.values(props.contextTreeNodes)) {
      if (node.type === 'file' || node.type === 'source') {
        for (const ref of node.sourceRefs || []) {
          if (ref.path) inContextPaths.add(ref.path);
        }
      }
    }
    setTabs((current) => current.map((tab) => ({
      ...tab,
      inContext: inContextPaths.has(tab.path)
    })));
  }, [props.contextTreeNodes]);

  const activeTab = useMemo(() => tabs.find((tab) => tab.path === activePath) || null, [tabs, activePath]);

  return {
    tabs,
    activePath,
    activeTab,
    filter,
    query,
    expandedDirectories,
    inspector,
    bottomPanel,
    inspectorOpen,
    selectedRange,
    output,
    error,
    busy,
    explorer,
    loadingExplorer,
    openTabs,
    openFile,
    closeTab,
    setActive,
    setContent,
    saveTab,
    saveAll,
    revertTab,
    setFilter,
    setQuery,
    toggleDirectory,
    setInspector,
    setInspectorOpen,
    setBottomPanel,
    setSelectedRange,
    refreshExplorer,
    refreshTab,
    appendOutput,
    clearOutput,
    runDiagnosticsForTab,
    markInContext,
    markWithEvidence
  };
}

interface FlatFileEntry {
  path: string;
  name: string;
  kind?: 'directory' | 'file';
  type?: 'directory' | 'file';
  size?: number;
  modified?: string;
}

function buildExplorerTree(entries: FlatFileEntry[], root: string): ExplorerNode[] {
  if (!entries || entries.length === 0) return [];
  const byPath = new Map<string, ExplorerNode>();
  const rootPath = root.replace(/[\\/]+$/, '');
  // Crear nodos para cada entrada.
  for (const entry of entries) {
    if (!entry.path) continue;
    const language = detectLanguage(entry.path);
    const entryKind = entry.kind || entry.type || 'file';
    const node: ExplorerNode = {
      path: entry.path,
      name: entry.name,
      kind: entryKind === 'directory' ? 'directory' : (isCodeLanguage(language) ? 'code' : 'file'),
      language,
      children: [],
      size: entry.size,
      modified: entry.modified,
      extension: (entry.name.split('.').pop() || '').toLowerCase()
    };
    byPath.set(entry.path, node);
  }
  // Construir jerarquía: padre = primer prefijo que existe como carpeta.
  const sortedPaths = Array.from(byPath.keys()).sort();
  for (const path of sortedPaths) {
    const node = byPath.get(path);
    if (!node) continue;
    if (path === rootPath) continue;
    const parentPath = findParentPath(path, rootPath, byPath);
    if (parentPath) {
      const parent = byPath.get(parentPath);
      if (parent) {
        parent.children.push(node);
      }
    }
  }
  // Devolver raíces: cualquier nodo cuyo path es hijo directo de rootPath.
  const result: ExplorerNode[] = [];
  for (const path of sortedPaths) {
    const node = byPath.get(path);
    if (!node) continue;
    if (path === rootPath) {
      result.push(node);
    } else {
      const parentPath = findParentPath(path, rootPath, byPath);
      if (!parentPath || parentPath === rootPath) {
        result.push(node);
      }
    }
  }
  // Ordenar: directorios primero, luego alfabético.
  return result.sort(compareExplorerNodes);
}

function compareExplorerNodes(a: ExplorerNode, b: ExplorerNode): number {
  if (a.kind !== b.kind) return a.kind === 'directory' ? -1 : 1;
  return a.name.localeCompare(b.name);
}

function findParentPath(path: string, rootPath: string, byPath: Map<string, ExplorerNode>): string | null {
  // Buscamos el ancestro más cercano que exista en byPath.
  const separator = path.includes('\\') ? '\\' : '/';
  const parts = path.split(/[\\/]/);
  while (parts.length > 1) {
    parts.pop();
    const candidate = parts.join(separator);
    if (candidate === rootPath) return null;
    if (byPath.has(candidate)) return candidate;
  }
  return null;
}

function isCodeLanguage(language: string): boolean {
  return ['typescript', 'tsx', 'javascript', 'jsx', 'python', 'json', 'css', 'html', 'shell', 'yaml', 'toml', 'dotenv', 'markdown'].includes(language);
}
