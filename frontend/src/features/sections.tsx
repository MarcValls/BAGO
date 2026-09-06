import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent as ReactMouseEvent } from 'react';
import type {
  BackendCommandResult,
  BackendHistory,
  BackendMenu,
  BackendProviders,
  BackendRouterEntry,
  BackendRouterList,
  BackendRouterPolicy,
  BackendRoutes,
  ChatMode,
  ChatTurn,
  ContextTargetKind,
  GlobalMode,
  InspectorLevel,
  SelectionRecord,
  UiAction,
  OpeningDecision,
  UiBootstrapSnapshot,
  BackendFileSourceRoot
} from '@/contracts/backend';
import type { ModuleAction, ModuleBridge } from '@/contracts/modules';
import { safeJson } from '@/api/client';
import { Icon, type IconName } from '@/shared/Icon';
import { quietStatus } from '@/shared/quiet-status';
import { ProviderCenterModule, type ProviderCenterProvider, type ProviderCenterRouterEntry } from '@/modules/provider-center';
import { SystemTabs } from '@/layout/SystemTabs';
import { CapabilityAnatomyModule } from '@/modules/capability-anatomy';
import { ExternalCapabilitiesPanel } from '@/modules/capability-anatomy/ExternalCapabilitiesPanel';
import { ChatPanel } from '@/layout/ChatPanel';
import { PipelineControlPanel } from '@/features/pipeline/PipelineControlPanel';
import { PipelineGuidedBuilder } from '@/features/pipeline/PipelineGuidedBuilder';
import { SimulationLaboratory, RlTrainingLaboratory } from '@/features/pipeline/LaboratoryPanels';
import { createModuleRegistry } from '@/modules/module-registry';
import { ContextTreeModule } from '@/features/context-tree/ContextTreeModule';
import { WorkGraph } from '@/features/graph/WorkGraph';
import { WorkspaceModule } from '@/features/workspace/WorkspaceModule';
import type { BagoClient } from '@/api/client';
import type { UseContextTreeState } from '@/features/context-tree/useContextTree';
import { mergeProviderStates } from '@/shared/providerStates';
import { PIPELINE_TASK_MAX_LENGTH } from '@/shared/inputLimits';
import { ConfirmDialog } from '@/lib/ConfirmDialog';
import { MemoryOperations, ProviderRuntimeTools, VisionOperations } from '@/layout/OperationalTools';
import { workspaceScopedStorageKey } from '@/shared/workspaceStateKeys';

export function workspaceSectionStorageKey(workspaceRoot: string, suffix: string): string {
  return workspaceScopedStorageKey(workspaceRoot, `section.${suffix}`);
}

interface Props {
  section: 'home' | 'chat' | 'workspace' | 'pipeline' | 'evidence' | 'context' | 'system';
  snapshot: UiBootstrapSnapshot | null;
  opening: OpeningDecision;
  booting: boolean;
  workspaceHint?: string;
  apiBase: string;
  apiToken: string;
  client: BagoClient;
  onApiConfigChange: (patch: { apiBase?: string; apiToken?: string }) => void;
  onPrimary: () => void;
  onContinue: () => void;
  onChooseWorkspace: () => void;
  onOpenPalette: () => void;
  onRefresh: () => void;
  menu: BackendMenu | null;
  routes: BackendRoutes | null;
  providers: BackendProviders | null;
  router: { list: BackendRouterList | null; policy: BackendRouterPolicy | null } | null;
  chatModelEntries: BackendRouterEntry[];
  history: BackendHistory | null;
  conversations: import('@/contracts/backend').BackendConversations | null;
  files: Record<string, unknown> | null;
  onManageSource?: (action: 'add' | 'remove', path: string, label?: string) => Promise<Record<string, unknown> | null>;
  commandResults: Record<string, BackendCommandResult | null>;
  turns: ChatTurn[];
  drafts: Record<string, string>;
  chatMode: ChatMode;
  globalMode: GlobalMode;
  onDraftChange: (section: string, text: string) => void;
  onSendChat: (message: string) => Promise<void>;
  onInspect: (eventOrSelection: SelectionRecord | ReactMouseEvent<HTMLElement>, hint?: InspectorLevel | { x: number; y: number }) => void;
  onReadFile: (path: string) => Promise<Record<string, unknown> | null>;
  onRunCommand: (command: string) => Promise<BackendCommandResult | null>;
  onRunContextCommand: (command: string) => Promise<void>;
  onRunAction: (action: UiAction) => void;
  onRunPlanTask: (task: string) => Promise<void>;
  onPreparePlan?: (task: string) => Promise<void>;
  onSetSection: (section: Props['section']) => void;
  onSetChatMode: (mode: ChatMode) => void;
  onSetGlobalMode: (mode: GlobalMode) => void;
  onRefreshRouter: () => Promise<void>;
  onToggleRouter: (key: string) => Promise<void>;
  onSetRouterAuto: (enabled: boolean) => Promise<void>;
  onConfigureProvider?: (provider: string, config: { enabled?: boolean; base_url?: string; api_key?: string; model?: string }) => Promise<void>;
  onSetSessionModel?: (modelKey: string | null) => Promise<void>;
  reasoningDepth?: string;
  onSetReasoningDepth?: (depth: string) => Promise<void>;
  onCreateConversation?: () => Promise<void>;
  onSwitchConversation?: (conversationId: string) => Promise<void>;
  onRenameConversation?: (conversationId: string, title: string) => Promise<void>;
  onArchiveConversation?: (conversationId: string) => Promise<void>;
  sessionModel?: string | null;
  workspaceOpenRequest?: { path: string; kind?: 'file' | 'directory'; token: number } | null;
  // CANON[CTX-001]: el módulo de contexto necesita un cliente HTTP
  // propio para leer/escribir los archivos `.bago/context/...` y para
  // ingerir patches que llegan del chat.
  contextClient: BagoClient;
  contextTree: UseContextTreeState;
  incomingContextPatches?: Array<{ patch: import('@/features/context-tree/contextTreeTypes').ContextPatchRequest; turnId: string }>;
  onContextPatchHandled?: (patchId: string) => void;
  // CANON[CTX-009]: cola de items encolados desde otras pantallas
  // (Workspace → Contexto). El módulo los consume al abrirse.
  contextBankPending?: Array<{
    id: string;
    kind: 'file' | 'directory' | 'source';
    path: string;
    title: string;
    destination: 'tree' | 'pack';
    createdAt: string;
  }>;
  onContextBankPendingConsumed?: (id: string) => void;
  // CANON[CTX-012]: vista de patches del chat con metadatos de display.
  contextPatchDisplay?: Array<{
    patch: import('@/features/context-tree/contextTreeTypes').ContextPatchRequest;
    turnId: string;
    status: 'pending' | 'accepted' | 'rejected' | 'edited' | 'failed' | 'reverted' | 'review_requested';
    errorMessage?: string;
    appliedAt?: string;
    receiptId?: string;
  }>;
  onAcceptContextPatch?: (patchId: string) => void;
  onRejectContextPatch?: (patchId: string) => void;
  onEditContextPatch?: (patchId: string) => void;
  onRevertContextPatch?: (patchId: string) => void;
  onReviewContextPatch?: (patchId: string) => void;
  onOpenContextInTree?: (patchId: string) => void;
  pastedImage?: { dataUrl: string; mimeType: string } | null;
  onRemovePastedImage?: () => void;
  // CANON[CTX-017]: estado inicial de selección / edición que el
  // chat puede pedir (botón "Abrir en árbol" / "Editar"). El módulo
  // lo consume y notifica para que ControlPlane lo limpie.
  initialContextSelectedNodeId?: string | null;
  initialContextEditingPatchId?: string | null;
  onInitialContextStateConsumed?: () => void;
  // CANON[CHAT-DOCK]: proveedor/modelos activos calculados en
  // ControlPlane para compartirse entre el chat acoplado y el chat
  // como pantalla completa.
  activeProvider: string | null;
  activeModels: Set<string>;
}

function resolveRouterEntries(router: Props['router']): BackendRouterEntry[] {
  const policyEntries = router?.policy?.entries || [];
  if (policyEntries.length > 0) return policyEntries;
  return router?.list?.entries || [];
}

export function selectRouterEntries(router: { list: BackendRouterList | null; policy: BackendRouterPolicy | null } | null | undefined): BackendRouterEntry[] {
  if (!router) return [];
  const policyEntries = router.policy?.entries || [];
  if (policyEntries.length > 0) return policyEntries;
  return router.list?.entries || [];
}

type RecordValue = Record<string, unknown>;
type ExplorerKind = 'file' | 'directory';
type WorkspaceFilter = 'all' | 'code' | 'python' | 'text' | 'json' | 'web' | 'shell' | 'other' | 'directory';

const PROGRAMMING_EXTENSIONS = new Set([
  'js', 'jsx', 'ts', 'tsx', 'mjs', 'cjs',
  'py', 'pyw', 'pyi',
  'html', 'htm', 'xhtml', 'xml', 'svg',
  'css', 'scss', 'sass', 'less',
  'json', 'jsonc', 'yaml', 'yml', 'toml', 'ini', 'env',
  'md', 'markdown',
  'sh', 'bash', 'zsh', 'ps1', 'bat', 'cmd',
  'c', 'h', 'hpp', 'cpp', 'cc', 'cxx',
  'java', 'kt', 'kts',
  'go', 'rs', 'rb', 'php',
  'swift', 'scala', 'dart',
  'sql', 'graphql', 'gql',
  'vue', 'svelte', 'astro',
  'lock', 'txt', 'log',
  'cs', 'fs', 'lua', 'r', 'pl', 'pm',
  'makefile', 'mk', 'cmake', 'gradle', 'properties'
]);

const PROGRAMMING_FILENAMES = new Set([
  'dockerfile', 'makefile', 'procfile', 'gemfile', 'rakefile', 'vagrantfile',
  'license', 'licence', 'readme', '.gitignore', '.npmignore', '.editorconfig',
  '.env', '.env.example', '.env.local', '.babelrc', '.eslintrc', '.prettierrc',
  'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock', 'bun.lockb',
  'tsconfig.json', 'jsconfig.json', 'vite.config.js', 'vite.config.ts', 'webpack.config.js',
  'rollup.config.js', 'eslint.config.js', 'prettier.config.js'
]);

const LANGUAGE_LABELS: Record<string, string> = {
  js: 'JavaScript',
  jsx: 'React JSX',
  ts: 'TypeScript',
  tsx: 'React TSX',
  py: 'Python',
  pyw: 'Python',
  pyi: 'Python stub',
  html: 'HTML',
  htm: 'HTML',
  xhtml: 'XHTML',
  css: 'CSS',
  scss: 'SCSS',
  sass: 'Sass',
  less: 'Less',
  json: 'JSON',
  jsonc: 'JSONC',
  yaml: 'YAML',
  yml: 'YAML',
  toml: 'TOML',
  ini: 'INI',
  env: 'Environment',
  md: 'Markdown',
  markdown: 'Markdown',
  sh: 'Shell',
  bash: 'Shell',
  zsh: 'Shell',
  ps1: 'PowerShell',
  bat: 'Batch',
  cmd: 'Batch',
  c: 'C',
  h: 'Header',
  hpp: 'C++ header',
  cpp: 'C++',
  cc: 'C++',
  cxx: 'C++',
  java: 'Java',
  kt: 'Kotlin',
  kts: 'Kotlin',
  go: 'Go',
  rs: 'Rust',
  rb: 'Ruby',
  php: 'PHP',
  swift: 'Swift',
  scala: 'Scala',
  dart: 'Dart',
  sql: 'SQL',
  graphql: 'GraphQL',
  gql: 'GraphQL',
  vue: 'Vue',
  svelte: 'Svelte',
  astro: 'Astro',
  txt: 'Text',
  log: 'Log',
  cs: 'C#',
  fs: 'F#',
  lua: 'Lua',
  r: 'R',
  pl: 'Perl',
  pm: 'Perl',
  makefile: 'Makefile',
  mk: 'Makefile',
  cmake: 'CMake',
  gradle: 'Gradle',
  properties: 'Properties',
  lock: 'Lockfile'
};

const TYPE_LABELS: Record<Exclude<WorkspaceFilter, 'all' | 'code'>, string> = {
  python: 'Python',
  text: 'Text',
  json: 'JSON',
  web: 'Web',
  shell: 'Shell',
  other: 'Otros',
  directory: 'Carpetas',
};

interface ExplorerNode {
  name: string;
  path: string;
  kind: ExplorerKind;
  children: ExplorerNode[];
}

function asRecord(value: unknown): RecordValue | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : null;
}

function flattenFiles(payload: Record<string, unknown> | null): RecordValue[] {
  const entries = Array.isArray(payload?.entries) ? payload.entries as RecordValue[] : [];
  return entries.slice(0, 200);
}

function flattenSourceRoots(payload: Record<string, unknown> | null): BackendFileSourceRoot[] {
  const entries = Array.isArray(payload?.source_roots)
    ? payload.source_roots as BackendFileSourceRoot[]
    : Array.isArray(payload?.sources)
      ? payload.sources as BackendFileSourceRoot[]
      : [];
  return entries.filter((entry): entry is BackendFileSourceRoot => Boolean(entry && typeof entry === 'object' && !Array.isArray(entry)));
}

function buildExplorerTree(entries: RecordValue[]): ExplorerNode[] {
  const roots: ExplorerNode[] = [];

  const getOrCreate = (children: ExplorerNode[], name: string, path: string, kind: ExplorerKind): ExplorerNode => {
    const existing = children.find((node) => node.path === path);
    if (existing) {
      if (kind === 'directory') existing.kind = 'directory';
      return existing;
    }
    const node: ExplorerNode = { name, path, kind, children: [] };
    children.push(node);
    return node;
  };

  const normalize = (value: string) => value.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');

  for (const entry of entries) {
    const rawPath = normalize(String(entry.path || entry.name || ''));
    if (!rawPath) continue;
    const parts = rawPath.split('/').filter(Boolean);
    const isDirectory = ['directory', 'dir', 'folder'].includes(String(entry.type || '').toLowerCase());
    let children = roots;
    let currentPath = '';

    if (isDirectory) {
      parts.forEach((part, index) => {
        currentPath = currentPath ? `${currentPath}/${part}` : part;
        const node = getOrCreate(children, part, currentPath, 'directory');
        children = node.children;
        if (index === parts.length - 1) {
          node.kind = 'directory';
        }
      });
      continue;
    }

    const dirParts = parts.slice(0, -1);
    const fileName = parts[parts.length - 1];
    for (const part of dirParts) {
      currentPath = currentPath ? `${currentPath}/${part}` : part;
      const node = getOrCreate(children, part, currentPath, 'directory');
      children = node.children;
    }
    const filePath = parts.join('/');
    getOrCreate(children, fileName, filePath, 'file');
  }

  const sortNodes = (nodes: ExplorerNode[]) => {
    nodes.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === 'directory' ? -1 : 1;
      return a.name.localeCompare(b.name, 'es', { numeric: true, sensitivity: 'base' });
    });
    nodes.forEach((node) => sortNodes(node.children));
  };
  sortNodes(roots);
  return roots;
}

function fileExtension(path: string): string {
  const file = path.split('/').pop() || '';
  const match = file.toLowerCase().match(/\.([^.]+)$/);
  return match ? match[1] : file.toLowerCase();
}

function isPlainTextContent(text: string): boolean {
  if (!text) return true;
  if (text.includes('\u0000')) return false;
  const sample = text.slice(0, 2000);
  let suspicious = 0;
  for (const char of sample) {
    const code = char.charCodeAt(0);
    if (code < 32 && !['\n', '\r', '\t'].includes(char)) suspicious += 1;
  }
  return suspicious < Math.max(8, sample.length * 0.02);
}

function languageLabelForPath(path: string): string {
  const name = path.split('/').pop() || '';
  const lower = name.toLowerCase();
  const ext = fileExtension(path);
  if (LANGUAGE_LABELS[lower]) return LANGUAGE_LABELS[lower];
  if (LANGUAGE_LABELS[ext]) return LANGUAGE_LABELS[ext];
  if (PROGRAMMING_FILENAMES.has(lower)) return 'Config';
  return ext ? ext.toUpperCase() : 'Text';
}

function workspaceTypeForPath(entry: RecordValue): Exclude<WorkspaceFilter, 'all'> {
  const type = String(entry.type || '').toLowerCase();
  if (['directory', 'dir', 'folder'].includes(type)) return 'directory';
  const name = String(entry.name || entry.path || '').toLowerCase();
  const ext = fileExtension(String(entry.path || entry.name || ''));
  if (['py', 'pyw', 'pyi'].includes(ext)) return 'python';
  if (['json', 'jsonc'].includes(ext)) return 'json';
  if (['html', 'htm', 'xhtml', 'css', 'scss', 'sass', 'less', 'js', 'jsx', 'ts', 'tsx', 'vue', 'svelte', 'astro', 'xml', 'svg'].includes(ext)) return 'web';
  if (['sh', 'bash', 'zsh', 'ps1', 'bat', 'cmd'].includes(ext)) return 'shell';
  if (['txt', 'md', 'markdown', 'log', 'ini', 'toml', 'yaml', 'yml', 'env', 'properties'].includes(ext)) return 'text';
  if (['dockerfile', 'makefile', 'procfile', 'gemfile', 'rakefile', 'vagrantfile', 'package.json', 'tsconfig.json', 'jsconfig.json', 'vite.config.js', 'vite.config.ts', 'webpack.config.js', 'rollup.config.js', 'eslint.config.js', 'prettier.config.js'].includes(name)) return 'text';
  return isProgrammingFile(entry) ? 'other' : 'other';
}


function screenLabel(section: Props['section']): string {
  const labels: Record<Props['section'], string> = {
    home: 'Inicio',
    chat: 'Inicio', // legacy route; normalized to the single conversation surface
    workspace: 'Workspace',
    pipeline: 'Pipeline',
    evidence: 'Evidencia',
    context: 'Contexto',
    system: 'Sistema'
  };
  return labels[section] || section;
}

function actionMatchesText(action: UiAction, text: string): boolean {
  const needle = text.trim().toLowerCase();
  if (!needle) return false;
  const id = action.id.toLowerCase();
  const label = action.label.toLowerCase();
  return id === needle || label === needle || id.includes(needle) || label.includes(needle) || needle.includes(id) || needle.includes(label);
}

function actionGuidanceSnapshot(action: UiAction): string {
  return String(action.payload?.section || action.payload?.targetSection || action.payload?.command || action.kind || '').trim();
}

function filterLabelForType(filter: WorkspaceFilter): string {
  if (filter === 'all') return 'Todo';
  if (filter === 'code') return 'Código';
  if (filter === 'directory') return 'Carpetas';
  return TYPE_LABELS[filter] || filter;
}

function isProgrammingFile(entry: RecordValue): boolean {
  const type = String(entry.type || '').toLowerCase();
  if (['directory', 'dir', 'folder'].includes(type)) return false;
  const rawName = String(entry.name || entry.path || '').toLowerCase().trim();
  const ext = fileExtension(String(entry.path || entry.name || ''));
  return PROGRAMMING_EXTENSIONS.has(ext) || PROGRAMMING_FILENAMES.has(rawName) || PROGRAMMING_FILENAMES.has(rawName.split('/').pop() || '');
}

function workspaceFileKind(entry: RecordValue): 'directory' | 'code' | 'file' {
  const type = String(entry.type || '').toLowerCase();
  if (['directory', 'dir', 'folder'].includes(type)) return 'directory';
  return isProgrammingFile(entry) ? 'code' : 'file';
}

function joinPath(base: string, part: string): string {
  return base ? `${base}/${part}` : part;
}

function readMessages(history: BackendHistory | null): RecordValue[] {
  return Array.isArray(history?.messages) ? history.messages as RecordValue[] : [];
}

// Acorta una ruta manteniendo los segmentos inicial y final, para evitar
// que cadenas técnicas largas como "C:\\Users\\...\\workspace\\.gabo\\...\\archivo"
// rompan la barra superior de un visor. Si la ruta cabe, se devuelve tal cual.
function shortenPath(value: string, maxLength = 60): string {
  const clean = String(value || '').trim();
  if (!clean || clean.length <= maxLength) return clean;
  const head = clean.slice(0, 18);
  const tail = clean.slice(-(maxLength - 18 - 3));
  return `${head}…${tail}`;
}

function planSteps(plan: unknown): RecordValue[] {
  const data = asRecord(plan);
  return data && Array.isArray(data.steps) ? data.steps as RecordValue[] : [];
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((entry) => String(entry)).filter(Boolean) : [];
}

function readText(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function summarizeMessage(message: RecordValue): string {
  return String(message.content || message.text || message.message || '').trim();
}

function commandAvailable(menu: BackendMenu | null, routes: BackendRoutes | null, pattern: RegExp): boolean {
  try {
    return pattern.test(JSON.stringify({ menu, routes }).toLowerCase());
  } catch {
    return false;
  }
}

function statusTone(status: string): string {
  const value = status.toLowerCase();
  if (['done', 'confirmed', 'valid', 'certified', 'ok'].some((entry) => value.includes(entry))) return 'confirmed';
  if (['running', 'pending', 'loading', 'partial', 'stale'].some((entry) => value.includes(entry))) return 'running';
  if (['failed', 'error', 'invalid', 'rejected'].some((entry) => value.includes(entry))) return 'error';
  if (['blocked', 'missing', 'legacy'].some((entry) => value.includes(entry))) return 'blocked';
  return 'unknown';
}

function StatusBadge({ status, label }: { status: string; label?: string }) {
  const text = label || quietStatus(status);
  if (!text) {
    return <span className={`status-badge state-${statusTone(status)}`}><span className="status-dot" /></span>;
  }
  return (
    <span className={`status-badge state-${statusTone(status)}`}>
      <span className="status-dot" />
      {text}
    </span>
  );
}

function Metric({ label, value, hint, icon }: { label: string; value: string; hint?: string; icon?: IconName }) {
  return (
    <article className="metric-card">
      <div className="metric-label">{icon && <Icon name={icon} size={16} />}{label}</div>
      <strong>{value}</strong>
      {hint && <span>{hint}</span>}
    </article>
  );
}

function ActionButton({ icon, children, primary = false, disabled = false, onClick, title }: {
  icon?: IconName;
  children: React.ReactNode;
  primary?: boolean;
  disabled?: boolean;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      className={primary ? 'primary-button compact' : 'secondary-button compact'}
      type="button"
      disabled={disabled}
      onClick={onClick}
      title={title}
    >
      {icon && <Icon name={icon} size={16} />}
      {children}
    </button>
  );
}

function buildSelection(id: string, kind: string, title: string, summary: string, detail: string[], raw: unknown, targetKind?: ContextTargetKind): SelectionRecord {
  return { id, kind, targetKind, title, summary, detail, raw: safeJson(raw) };
}

function openContextMenuFromElement(event: ReactMouseEvent<HTMLElement>, selection: SelectionRecord, onInspect: Props['onInspect']) {
  event.preventDefault();
  event.stopPropagation();
  onInspect(selection, { x: event.clientX, y: event.clientY });
}


function targetKindForSection(section: Props['section']): ContextTargetKind {
  if (section === 'home') return 'screen.home';
  if (section === 'chat') return 'screen.home';
  if (section === 'pipeline') return 'pipeline.surface';
  if (section === 'evidence') return 'evidence.item';
  if (section === 'context') return 'context.item';
  if (section === 'system') return 'system.surface';
  return 'screen.other';
}

function inspectMenuAttrs(selection: SelectionRecord, onInspect: Props['onInspect']) {
  return {
    onContextMenu: (event: ReactMouseEvent<HTMLElement>) => openContextMenuFromElement(event, selection, onInspect),
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if ((event.shiftKey && event.key === 'F10') || event.key === 'ContextMenu') {
        event.preventDefault();
        event.stopPropagation();
        const rect = event.currentTarget.getBoundingClientRect();
        onInspect(selection, { x: rect.left + 12, y: rect.bottom + 6 });
      }
    },
    'aria-haspopup': 'dialog' as const,
    title: 'Abrir acciones para este elemento'
  };
}



function ContextActionButton({ selection, onInspect, label = 'Acciones' }: { selection: SelectionRecord; onInspect: Props['onInspect']; label?: string }) {
  return (
    <button
      type="button"
      className="icon-button context-action-button"
      title={label}
      aria-label={label}
      aria-haspopup="dialog"
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        const rect = event.currentTarget.getBoundingClientRect();
        onInspect(selection, { x: rect.left, y: rect.bottom + 6 });
      }}
    >
      <Icon name="more" size={14} />
    </button>
  );
}

export function ControlSections(props: Props) {
  const [workspaceQuery, setWorkspaceQuery] = useState('');
  const [workspaceFilter, setWorkspaceFilter] = useState<WorkspaceFilter>('all');
  const [workspaceExpanded, setWorkspaceExpanded] = useState<string[]>([]);
  const [workspaceActivePath, setWorkspaceActivePath] = useState('');
  const [workspaceContent, setWorkspaceContent] = useState('Selecciona un archivo para verlo aquí.');
  const [workspaceContentPath, setWorkspaceContentPath] = useState('');
  const [workspaceContentKind, setWorkspaceContentKind] = useState('Text');
  const [workspaceContentLoading, setWorkspaceContentLoading] = useState(false);
  const [workspaceContentState, setWorkspaceContentState] = useState<'empty' | 'loading' | 'ready' | 'error'>('empty');
  const [sourcePath, setSourcePath] = useState('');
  const [sourceLabel, setSourceLabel] = useState('');
  const [sourceBusy, setSourceBusy] = useState(false);
  const [sourceMessage, setSourceMessage] = useState('');
  const [graphFiltered, setGraphFiltered] = useState(true);
  const [pipelineView, setPipelineView] = useState<'create' | 'execution' | 'flow' | 'control' | 'capabilities' | 'simulation' | 'rl'>('create');
  const [flowNotice, setFlowNotice] = useState<{ tone: 'info' | 'warning' | 'error'; message: string } | null>(null);
  const [operationView, setOperationView] = useState<'providers' | 'runtime' | 'memory' | 'vision' | 'configuration'>('providers');
  const [pendingStep, setPendingStep] = useState<RecordValue | null>(null);
  const [pendingStepBusy, setPendingStepBusy] = useState(false);
  const [pendingStepError, setPendingStepError] = useState('');
  const [evidenceView, setEvidenceView] = useState<'receipts' | 'audit'>('receipts');
  const [contextView, setContextView] = useState<'work' | 'routes'>('work');
  const [evidenceCompare, setEvidenceCompare] = useState(false);
  const [contextExpanded, setContextExpanded] = useState(false);
  const [historyExpanded, setHistoryExpanded] = useState(false);
  const activeProvider = props.activeProvider;
  const activeModels = props.activeModels;
  const [sourcesDrawerOpen, setSourcesDrawerOpen] = useState(false);

  const snapshot = props.snapshot;
  useEffect(() => {
    if (!flowNotice) return;
    const t = setTimeout(() => setFlowNotice(null), 6000);
    return () => clearTimeout(t);
  }, [flowNotice]);
  const allFiles = useMemo(() => flattenFiles(props.files), [props.files]);
  const sourceRoots = useMemo(() => flattenSourceRoots(props.files), [props.files]);
  const visibleFiles = useMemo(() => {
    const query = workspaceQuery.trim().toLowerCase();
    return allFiles.filter((entry) => {
      const kind = workspaceFileKind(entry);
      const type = workspaceTypeForPath(entry);
      const matchesType = workspaceFilter === 'all'
        || (workspaceFilter === 'code' ? kind === 'code'
          : workspaceFilter === 'directory' ? kind === 'directory'
            : workspaceFilter === 'python' ? type === 'python'
              : workspaceFilter === 'text' ? type === 'text'
                : workspaceFilter === 'json' ? type === 'json'
                  : workspaceFilter === 'web' ? type === 'web'
                    : workspaceFilter === 'shell' ? type === 'shell'
                      : workspaceFilter === 'other' ? type === 'other'
                        : true);
      const text = `${String(entry.name || '')} ${String(entry.path || '')}`.toLowerCase();
      return matchesType && (!query || text.includes(query));
    });
  }, [allFiles, workspaceFilter, workspaceQuery]);
  const explorerTree = useMemo(() => buildExplorerTree(visibleFiles), [visibleFiles]);

  const historyMessages = useMemo(() => readMessages(props.history), [props.history]);
  const turns = props.turns;
  const evidenceItems = Array.isArray(snapshot?.evidence) ? snapshot.evidence : [];
  const jobItems = Array.isArray(snapshot?.jobs) ? snapshot.jobs : [];
  const planResult = props.commandResults.plan;
  const pipelineJob = jobItems.find((item) => String(item.kind || '') === 'pipeline') || jobItems[0] || null;
  const plan = planResult?.data || planResult?.plan || planResult || pipelineJob;
  const steps = planSteps(plan);
  const planData = asRecord(plan);
  const pipelineStatus = String(planData?.status || pipelineJob?.status || (planResult?.ok === false ? 'failed' : steps.length ? 'running' : 'pending'));
  const doneCount = steps.filter((step) => statusTone(String(step.status || 'pending')) === 'confirmed').length;
  const blockedCount = steps.filter((step) => statusTone(String(step.status || 'pending')) === 'blocked').length;
  const failedCount = steps.filter((step) => statusTone(String(step.status || 'pending')) === 'error').length;
  const selectedWorkspaceFile = useMemo(() => visibleFiles.find((entry) => String(entry.path || '') === workspaceActivePath) || null, [visibleFiles, workspaceActivePath]);
  const screenSelection = buildSelection(
    `screen-${props.section}`,
    `screen-${props.section}`,
    screenLabel(props.section),
    `${snapshot?.system.state || 'unknown'} · ${snapshot?.workspace.root || props.workspaceHint || 'sin workspace confirmado'}`,
    [
      `section: ${props.section}`,
      `workspace: ${snapshot?.workspace.id || snapshot?.workspace.root || 'unknown'}`,
      `model: ${snapshot?.model.provider || 'unknown'} / ${snapshot?.model.effectiveModel || snapshot?.model.configuredModel || snapshot?.model.runtime || snapshot?.model.adapter || 'unknown'}`
    ],
    { section: props.section, snapshot, workspaceHint: props.workspaceHint },
    targetKindForSection(props.section)
  );
  const providers = useMemo(() => mergeProviderStates(props.providers), [props.providers]);
  const routerEntries = props.chatModelEntries;
  const chatModelEntries = props.chatModelEntries;
  const routerAuto = Boolean(props.router?.policy?.auto_switch ?? props.router?.list?.auto_switch);
  const routerSelectedCount = props.router?.policy?.selected_count ?? props.router?.list?.selected_count ?? routerEntries.filter((entry) => Boolean(entry.selected)).length;
  const routerLastPick = String(props.router?.policy?.last_pick || props.router?.list?.last_pick || '—');

  useEffect(() => {
    const topLevel = explorerTree.filter((node) => node.kind === 'directory').map((node) => node.path);
    setWorkspaceExpanded(topLevel);
    setWorkspaceActivePath('');
    setWorkspaceContent('Selecciona un archivo para verlo aquí.');
    setWorkspaceContentPath('');
    setWorkspaceContentKind('Text');
    setWorkspaceContentState('empty');
    setWorkspaceContentLoading(false);
  }, [snapshot?.workspace.id, snapshot?.workspace.root]);

  useEffect(() => {
    if (props.section !== 'workspace') return;
    const firstFile = visibleFiles.find((entry) => workspaceFileKind(entry) !== 'directory');
    if (firstFile && !workspaceActivePath) {
      void openWorkspaceFile(String(firstFile.path || firstFile.name || ''), { inspect: false });
    }
  }, [props.section, visibleFiles, workspaceActivePath]);

  useEffect(() => {
    const request = props.workspaceOpenRequest;
    if (!request?.path) return;
    const clean = request.path.trim();
    if (!clean) return;
    if (request.kind === 'directory') {
      setWorkspaceActivePath(clean);
      setWorkspaceContentPath(clean);
      setWorkspaceContentKind('Carpeta');
      setWorkspaceContent(`Carpeta seleccionada: ${clean}\nUsa el árbol o el menú contextual para abrir, adjuntar o copiar elementos.`);
      setWorkspaceContentState('empty');
      setWorkspaceContentLoading(false);
      setWorkspaceExpanded((current) => current.includes(clean) ? current : [...current, clean]);
      return;
    }
    void openWorkspaceFile(clean, { inspect: false });
  }, [props.workspaceOpenRequest?.token]);

  async function openWorkspaceFile(path: string, options: { inspect?: boolean } = { inspect: false }) {
    const clean = path.trim();
    if (!clean) return;
    setWorkspaceActivePath(clean);
    setWorkspaceContentPath(clean);
    setWorkspaceContentLoading(true);
    setWorkspaceContentState('loading');
    if (options.inspect !== false) {
      props.onInspect(
        buildSelection(
          clean,
          'workspace-file',
          String(clean.split('/').pop() || clean),
          `Leyendo ${clean}`,
          [`path: ${clean}`, `workspace: ${snapshot?.workspace.id || 'unknown'}`],
          { path: clean },
          'workspace.file'
        )
      );
    }
    try {
      const result = await props.onReadFile(clean);
      const record = result && typeof result === 'object' && !Array.isArray(result) ? result as RecordValue : {};
      const content = readText(record.content) || readText((record.data as RecordValue | undefined)?.content) || readText(record.text);
      if (content && !isPlainTextContent(content)) {
        setWorkspaceContent('Este archivo parece binario o no es texto legible.');
        setWorkspaceContentKind(languageLabelForPath(clean));
        setWorkspaceContentState('error');
      } else {
        setWorkspaceContent(content || 'Archivo vacío.');
        setWorkspaceContentKind(languageLabelForPath(clean));
        setWorkspaceContentState('ready');
      }
    } catch (error) {
      setWorkspaceContent(String(error instanceof Error ? error.message : 'No se pudo leer el archivo.'));
      setWorkspaceContentKind(languageLabelForPath(clean));
      setWorkspaceContentState('error');
    } finally {
      setWorkspaceContentLoading(false);
    }
  }

  async function copyWorkspaceText(text: string) {
    if (!text.trim()) return;
    await navigator.clipboard?.writeText(text);
  }

  function toggleWorkspaceFolder(path: string) {
    setWorkspaceExpanded((current) => (
      current.includes(path)
        ? current.filter((item) => item !== path)
        : [...current, path]
    ));
  }

  function isWorkspaceExpanded(path: string): boolean {
    return workspaceExpanded.includes(path);
  }

  async function submitSource(action: 'add' | 'remove', path: string, label?: string) {
    if (!props.onManageSource) {
      setSourceMessage('La gestión de fuentes no está disponible.');
      return;
    }
    const cleanPath = path.trim();
    if (!cleanPath) {
      setSourceMessage('Introduce una ruta.');
      return;
    }
    setSourceBusy(true);
    try {
      const result = await props.onManageSource(action, cleanPath, label?.trim() || undefined);
      if (result && typeof result === 'object' && !Array.isArray(result)) {
        setSourceMessage(String((result as RecordValue).message || (action === 'add' ? 'Fuente añadida' : 'Fuente eliminada')));
      } else {
        setSourceMessage(action === 'add' ? 'Fuente añadida' : 'Fuente eliminada');
      }
      await props.onRefresh();
      if (action === 'add') {
        setSourcePath('');
        setSourceLabel('');
      }
    } catch (error) {
      setSourceMessage(error instanceof Error ? error.message : 'No se pudo actualizar la fuente.');
    } finally {
      setSourceBusy(false);
    }
  }

  const moduleRegistry = useMemo(() => createModuleRegistry([
    {
      id: 'home',
      label: 'Inicio',
      description: 'Resumen del estado y accesos rápidos',
      state: snapshot?.system.state || 'unknown',
      capabilities: ['read', 'inspect', 'navigate'],
      actions: [
        { id: 'open-chat', label: 'Ir a chat', kind: 'navigate', enabled: true, payload: { section: 'chat' } },
        { id: 'open-workspace', label: 'Ir a workspace', kind: 'navigate', enabled: true, payload: { section: 'workspace' } },
      ],
      read: () => ({
        moduleId: 'home',
        label: 'Inicio',
        state: snapshot?.system.state || 'unknown',
        summary: `${snapshot?.system.state || 'unknown'} · ${snapshot?.workspace.root || props.workspaceHint || 'sin workspace confirmado'}`,
        data: {
          workspace: snapshot?.workspace,
          model: snapshot?.model,
          permissions: snapshot?.permissions
        }
      }),
      inspect: () => {
        const selection = buildSelection(
          'home',
          'module-home',
          'Inicio',
          snapshot?.workspace.root || props.workspaceHint || 'Resumen de entrada',
          [
            `state: ${snapshot?.system.state || 'unknown'}`,
            `workspace: ${snapshot?.workspace.root || 'unknown'}`
          ],
          { snapshot, workspaceHint: props.workspaceHint }
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'home', selection, message: 'Inicio inspeccionado', data: snapshot };
      }
    },
    {
      id: 'chat',
      label: 'Chat',
      description: 'Conversación principal y acciones de lectura/escritura',
      state: snapshot?.permissions.canChat ? 'ready' : 'blocked',
      capabilities: ['read', 'write', 'inspect', 'navigate'],
      actions: [
        { id: 'send-draft', label: 'Enviar borrador', kind: 'write', enabled: Boolean(snapshot?.permissions.canChat && (props.drafts.chat || '').trim()), payload: { text: props.drafts.chat || '' } },
        { id: 'inspect-turns', label: 'Inspeccionar chat', kind: 'inspect', enabled: true, payload: { target: 'turns' } },
        { id: 'open-context', label: 'Adjuntar contexto', kind: 'navigate', enabled: Boolean(snapshot?.permissions.canInspectContext), payload: { command: '/context attach' } }
      ],
      read: () => ({
        moduleId: 'chat',
        label: 'Chat',
        state: snapshot?.permissions.canChat ? 'ready' : 'blocked',
        summary: `${turns.length} turnos · ${snapshot?.permissions.canChat ? 'autorizado' : 'bloqueado'}`,
        data: {
          turns,
          draft: props.drafts.chat || '',
          canChat: snapshot?.permissions.canChat ?? false
        }
      }),
      write: async (payload) => {
        const text = String(payload.text || payload.message || payload.command || '').trim();
        if (!text) {
          return { moduleId: 'chat', ok: false, message: 'Sin texto para enviar' };
        }
        if (!snapshot?.permissions.canChat) {
          return { moduleId: 'chat', ok: false, message: 'Chat bloqueado por backend' };
        }
        if (payload.command || payload.section === 'context') {
          await props.onRunContextCommand(text);
          return { moduleId: 'chat', ok: true, message: text };
        }
        await props.onSendChat(text);
        return { moduleId: 'chat', ok: true, message: text };
      },
      inspect: () => {
        const latest = turns[turns.length - 1];
        const selection = buildSelection(
          latest?.id || 'chat',
          'module-chat',
          'Chat',
          latest?.text || 'Sin mensajes recientes',
          [
            `turns: ${turns.length}`,
            `canChat: ${String(snapshot?.permissions.canChat ?? false)}`,
            `mode: ${props.chatMode}`
          ],
          { turns, draft: props.drafts.chat || '' }
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'chat', selection, message: 'Chat inspeccionado', data: turns };
      }
    },
    {
      id: 'workspace',
      label: 'Workspace',
      description: 'Explorador, filtros y archivo activo',
      state: workspaceContentState,
      capabilities: ['read', 'write', 'inspect', 'navigate', 'select'],
      actions: [
        { id: 'set-all', label: 'Ver todo', kind: 'write', enabled: true, payload: { filter: 'all' } },
        { id: 'open-picker', label: 'Elegir workspace', kind: 'navigate', enabled: true, payload: { command: 'open-picker' } },
        { id: 'inspect-file', label: 'Inspeccionar archivo', kind: 'inspect', enabled: Boolean(workspaceActivePath), payload: { target: workspaceActivePath } }
      ],
      read: () => ({
        moduleId: 'workspace',
        label: 'Workspace',
        state: workspaceContentState,
        summary: `${visibleFiles.length} archivos visibles · ${workspaceActivePath || 'sin archivo activo'}`,
        data: {
          query: workspaceQuery,
          filter: workspaceFilter,
          expanded: workspaceExpanded,
          activePath: workspaceActivePath,
          contentPath: workspaceContentPath,
          contentKind: workspaceContentKind,
          contentState: workspaceContentState
        }
      }),
      write: async (payload) => {
        if (payload.filter) {
          setWorkspaceFilter(String(payload.filter) as WorkspaceFilter);
        }
        if (typeof payload.query === 'string') {
          setWorkspaceQuery(payload.query);
        }
        if (typeof payload.path === 'string' && payload.path.trim()) {
          await openWorkspaceFile(payload.path);
        }
        return { moduleId: 'workspace', ok: true, message: 'Workspace actualizado' };
      },
      inspect: () => {
        const target = selectedWorkspaceFile || { path: workspaceActivePath, name: workspaceContentPath };
        const selection = buildSelection(
          String(target?.path || workspaceActivePath || 'workspace'),
          'module-workspace',
          String(target?.name || workspaceContentPath || 'Workspace'),
          workspaceContent.slice(0, 220) || 'Sin contenido activo',
          [
            `filter: ${workspaceFilter}`,
            `query: ${workspaceQuery || '—'}`,
            `state: ${workspaceContentState}`
          ],
          target
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'workspace', selection, message: 'Workspace inspeccionado', data: target };
      }
    },
    {
      id: 'graph',
      label: 'Mapa de trabajo',
      description: 'Menciones, tareas y ejecución accionables',
      state: graphFiltered ? 'pending' : 'all',
      capabilities: ['read', 'write', 'inspect', 'select'],
      actions: [
        { id: 'show-pending', label: 'Mostrar pendientes', kind: 'write', enabled: true, payload: { filtered: true } },
        { id: 'show-all', label: 'Mostrar todo', kind: 'write', enabled: true, payload: { filtered: false } },
        { id: 'open-context', label: 'Abrir Contexto', kind: 'write', enabled: true, payload: { section: 'context' } },
        { id: 'open-pipeline', label: 'Abrir Pipeline', kind: 'write', enabled: true, payload: { section: 'pipeline' } }
      ],
      read: () => ({
        moduleId: 'graph',
        label: 'Mapa de trabajo',
        state: graphFiltered ? 'pending' : 'all',
        summary: `${props.contextTree.proposals.filter((proposal) => proposal.status === 'pending').length} menciones · ${steps.length} pasos`,
        data: { filtered: graphFiltered, proposals: props.contextTree.proposals.length, steps: steps.length }
      }),
      write: async (payload) => {
        if (typeof payload.filtered === 'boolean') setGraphFiltered(payload.filtered);
        if (payload.section === 'context' || payload.section === 'pipeline') props.onSetSection(payload.section);
        return { moduleId: 'graph', ok: true, message: 'Mapa de trabajo actualizado' };
      },
      inspect: () => {
        const pendingMentions = props.contextTree.proposals.filter((proposal) => proposal.status === 'pending').length;
        const selection = buildSelection(
          'graph',
          'module-graph',
          'Mapa de trabajo',
          `${pendingMentions} menciones · ${steps.length} pasos`,
          [
            `scope: ${graphFiltered ? 'pending' : 'all'}`,
            `steps: ${String(steps.length)}`
          ],
          { filtered: graphFiltered, proposals: props.contextTree.proposals.length, steps: steps.length }
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'graph', selection, message: 'Mapa de trabajo inspeccionado', data: { filtered: graphFiltered } };
      }
    },
    {
      id: 'pipeline',
      label: 'Pipeline',
      description: 'Plan, tareas y estado de ejecución',
      state: pipelineStatus,
      capabilities: ['read', 'write', 'inspect'],
      actions: [
        { id: 'run-plan', label: 'Ejecutar tarea', kind: 'write', enabled: true, payload: { task: props.drafts.pipeline || '' } },
        { id: 'inspect-plan', label: 'Inspeccionar plan', kind: 'inspect', enabled: true, payload: { target: 'plan' } }
      ],
      read: () => ({
        moduleId: 'pipeline',
        label: 'Pipeline',
        state: pipelineStatus,
        summary: `${steps.length} pasos · ${doneCount} hechos · ${blockedCount} bloqueados`,
        data: {
          status: pipelineStatus,
          steps,
          doneCount,
          blockedCount,
          failedCount
        }
      }),
      write: async (payload) => {
        const task = String(payload.task || payload.text || payload.command || '').trim();
        if (!task) return { moduleId: 'pipeline', ok: false, message: 'Sin tarea para ejecutar' };
        await props.onRunPlanTask(task);
        return { moduleId: 'pipeline', ok: true, message: task };
      },
      inspect: () => {
        const selection = buildSelection(
          'pipeline',
          'module-pipeline',
          'Pipeline',
          pipelineStatus,
          [
            `steps: ${steps.length}`,
            `done: ${doneCount}`,
            `blocked: ${blockedCount}`,
            `failed: ${failedCount}`
          ],
          plan
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'pipeline', selection, message: 'Pipeline inspeccionado', data: plan };
      }
    },
    {
      id: 'evidence',
      label: 'Evidencia',
      description: 'Receipts, historial y comparación',
      state: evidenceCompare ? 'compare' : 'ready',
      capabilities: ['read', 'write', 'inspect'],
      actions: [
        { id: 'toggle-compare', label: 'Comparar', kind: 'toggle', enabled: true, payload: { compare: !evidenceCompare } },
        { id: 'inspect-latest', label: 'Última evidencia', kind: 'inspect', enabled: true, payload: { target: 'latest' } }
      ],
      read: () => ({
        moduleId: 'evidence',
        label: 'Evidencia',
        state: evidenceCompare ? 'compare' : 'ready',
        summary: `${evidenceItems.length || historyMessages.length} registros`,
        data: { evidenceCompare, evidenceItems, historyMessages }
      }),
      write: async (payload) => {
        if (typeof payload.compare === 'boolean') setEvidenceCompare(payload.compare);
        return { moduleId: 'evidence', ok: true, message: 'Estado de evidencia actualizado' };
      },
      inspect: () => {
        const latest = evidenceItems.length ? (evidenceItems[0] as RecordValue) : historyMessages.length ? historyMessages[historyMessages.length - 1] : (asRecord(snapshot?.context) || {});
        const receiptId = snapshot?.context.receiptId || String(latest.id || latest.receipt_id || latest.envelope_id || 'Sin identificador');
        const selection = buildSelection(
          receiptId,
          'module-evidence',
          'Última evidencia',
          String(latest.message || latest.text || latest.summary || summarizeMessage(latest) || `Evidencia ${receiptId}`),
          [
            `status: ${snapshot?.context.certificationStatus || snapshot?.context.state || 'unknown'}`,
            `source: ${String(latest.source || latest.origin || 'backend')}`
          ],
          latest
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'evidence', selection, message: 'Evidencia inspeccionada', data: latest };
      }
    },
    {
      id: 'context',
      label: 'Contexto',
      description: 'Presupuesto y certificación del contexto',
      state: snapshot?.context.state || 'unknown',
      capabilities: ['read', 'write', 'inspect'],
      actions: [
        { id: 'measure', label: 'Medir', kind: 'write', enabled: Boolean(snapshot?.permissions.canInspectContext), payload: { command: '/context measure' } },
        { id: 'certify', label: 'Certificar', kind: 'write', enabled: Boolean(snapshot?.permissions.canInspectContext), payload: { command: '/context certify' } }
      ],
      read: () => ({
        moduleId: 'context',
        label: 'Contexto',
        state: snapshot?.context.state || 'unknown',
        summary: `${snapshot?.context.occupied ?? 0}/${snapshot?.context.limit ?? 0} tokens`,
        data: snapshot?.context
      }),
      write: async (payload) => {
        const command = String(payload.command || '').trim();
        if (!command) {
          if (typeof payload.expanded === 'boolean') setContextExpanded(payload.expanded);
          return { moduleId: 'context', ok: true, message: 'Estado de contexto actualizado' };
        }
        await props.onRunContextCommand(command);
        return { moduleId: 'context', ok: true, message: command };
      },
      inspect: () => {
        const occupied = snapshot?.context.occupied ?? 0;
        const limit = snapshot?.context.limit ?? 0;
        const reserve = snapshot?.context.reserve ?? 0;
        const selection = buildSelection(
          snapshot?.context.receiptId || 'context-receipt',
          'module-context',
          'Contexto',
          `Estado ${snapshot?.context.state || 'unknown'} · revisión ${String(snapshot?.context.revision || 'unknown')}`,
          [`occupied: ${occupied}`, `reserve: ${reserve}`, `limit: ${limit}`],
          snapshot?.context
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'context', selection, message: 'Contexto inspeccionado', data: snapshot?.context };
      }
    },
    {
      id: 'system',
      label: 'Sistema',
      description: 'Estado general, router y rutas backend',
      state: routerSelectedCount > 0 ? 'confirmed' : 'blocked',
      capabilities: ['read', 'write', 'inspect', 'refresh', 'toggle'],
      actions: [
        { id: 'refresh-router', label: 'Refrescar router', kind: 'refresh', enabled: true },
        { id: 'router-auto', label: 'Auto-router', kind: 'toggle', enabled: true, payload: { enabled: routerAuto } },
        { id: 'open-system', label: 'Abrir sistema', kind: 'navigate', enabled: true, payload: { section: 'system' } }
      ],
      read: () => ({
        moduleId: 'system',
        label: 'Sistema',
        state: routerSelectedCount > 0 ? 'confirmed' : 'blocked',
        summary: `${routerSelectedCount} seleccionados · ${routerLastPick}`,
        data: {
          snapshot,
          routerEntries,
          routerAuto,
          routerSelectedCount,
          routerLastPick,
          providers
        }
      }),
      write: async (payload) => {
        if (typeof payload.enabled === 'boolean') {
          await props.onSetRouterAuto(payload.enabled);
        }
        if (typeof payload.key === 'string' && payload.key.trim()) {
          await props.onToggleRouter(payload.key);
        }
        if (payload.refresh) {
          await props.onRefreshRouter();
        }
        return { moduleId: 'system', ok: true, message: 'Sistema actualizado' };
      },
      inspect: () => {
        const selection = buildSelection(
          'system',
          'module-system',
          'Sistema',
          `${routerSelectedCount} seleccionados · ${routerLastPick}`,
          [
            `router_auto: ${String(routerAuto)}`,
            `selected: ${String(routerSelectedCount)}`
          ],
          { snapshot, routerEntries, routerAuto, routerSelectedCount, routerLastPick }
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'system', selection, message: 'Sistema inspeccionado', data: snapshot };
      }
    },
    {
      id: 'provider-center',
      label: 'Centro de proveedores',
      description: 'Catálogo reutilizable de proveedores y modelos',
      state: providers.length ? 'ready' : 'empty',
      capabilities: ['read', 'write', 'inspect', 'register', 'toggle'],
      actions: [
        { id: 'register-provider', label: 'Registrar proveedor', kind: 'register', enabled: true },
        { id: 'register-model', label: 'Registrar modelo', kind: 'register', enabled: true },
        { id: 'toggle-router-auto', label: 'Auto-router', kind: 'toggle', enabled: true, payload: { enabled: routerAuto } }
      ],
      read: () => ({
        moduleId: 'provider-center',
        label: 'Centro de proveedores',
        state: providers.length ? 'ready' : 'empty',
        summary: `${providers.length} proveedores · ${routerEntries.length} rutas de router`,
        data: { providers, routerEntries, routerAuto, routerSelectedCount, routerLastPick }
      }),
      write: async (payload) => {
        if (typeof payload.enabled === 'boolean') {
          await props.onSetRouterAuto(payload.enabled);
        }
        if (typeof payload.key === 'string' && payload.key.trim()) {
          await props.onToggleRouter(payload.key);
        }
        return { moduleId: 'provider-center', ok: true, message: 'Centro de proveedores actualizado' };
      },
      inspect: () => {
        const selection = buildSelection(
          'provider-center',
          'module-provider-center',
          'Centro de proveedores',
          `${providers.length} proveedores`,
          [
            `router_entries: ${String(routerEntries.length)}`,
            `auto: ${String(routerAuto)}`
          ],
          { providers, routerEntries, routerAuto, routerSelectedCount, routerLastPick }
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'provider-center', selection, message: 'Centro de proveedores inspeccionado', data: providers };
      }
    },
    {
      id: 'capability-anatomy',
      label: 'Capacidades',
      description: 'Anatomía de capacidades del backend desde Pipeline',
      state: 'ready',
      capabilities: ['read', 'inspect', 'navigate'],
      actions: [
        { id: 'open-pipeline', label: 'Abrir pipeline', kind: 'navigate', enabled: true, payload: { section: 'pipeline' } }
      ],
      read: () => ({
        moduleId: 'capability-anatomy',
        label: 'Capacidades',
        state: 'ready',
        summary: 'Anatomía y rutas del backend',
        data: { source: 'pipeline' }
      }),
      inspect: () => {
        const selection = buildSelection(
          'capability-anatomy',
          'module-capability-anatomy',
          'Capacidades',
          'Anatomía y contrato de capacidades del backend',
          ['surface: pipeline', 'source: backend'],
          { source: 'pipeline' }
        );
        props.onInspect(selection, 'detail');
        return { moduleId: 'capability-anatomy', selection, message: 'Capacidades inspeccionadas', data: { source: 'pipeline' } };
      }
    }
  ]), [
    evidenceCompare,
    evidenceItems,
    failedCount,
    graphFiltered,
    historyMessages,
    plan,
    pipelineStatus,
    providers,
    props,
    props.drafts.chat,
    props.drafts.pipeline,
    routerAuto,
    routerEntries,
    routerLastPick,
    routerSelectedCount,
    selectedWorkspaceFile,
    snapshot,
    steps,
    snapshot?.permissions.canChat,
    snapshot?.permissions.canInspectContext,
    turns,
    visibleFiles,
    workspaceActivePath,
    workspaceContent,
    workspaceContentKind,
    workspaceContentPath,
    workspaceContentState,
    workspaceExpanded,
    workspaceFilter,
    workspaceQuery
  ]);

  if (props.section === 'home' || props.section === 'chat') {
    const recentProjects = props.contextTree.tree
      ? Object.values(props.contextTree.tree.nodes)
        .filter((node) => node.parentId === props.contextTree.tree?.rootId && (node.type === 'pending' || node.metadata?.branch === true))
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
        .slice(0, 5)
        .map((node) => ({ id: node.id, title: node.title, summary: node.summary || '', updatedAt: node.updatedAt, status: node.status }))
      : [];
    return (
      <ChatPanel
        snapshot={snapshot}
        turns={props.turns}
        drafts={props.drafts}
        chatMode={props.chatMode}
        history={props.history}
        conversations={props.conversations}
        routerEntries={chatModelEntries}
        sessionModel={props.sessionModel ?? null}
        activeProvider={activeProvider}
        activeModels={activeModels}
        onSetChatMode={props.onSetChatMode}
        onDraftChange={props.onDraftChange}
        onSendChat={props.onSendChat}
        onInspect={props.onInspect}
        onRunCommand={props.onRunCommand}
        onRunContextCommand={props.onRunContextCommand}
        onNavigate={props.onSetSection}
        onSetSessionModel={(key) => props.onSetSessionModel ? props.onSetSessionModel(key) : Promise.resolve()}
        reasoningDepth={props.reasoningDepth || 'normal'}
        onSetReasoningDepth={(depth) => props.onSetReasoningDepth ? props.onSetReasoningDepth(depth) : Promise.resolve()}
        onCreateConversation={props.onCreateConversation}
        onSwitchConversation={props.onSwitchConversation}
        onRenameConversation={props.onRenameConversation}
        onArchiveConversation={props.onArchiveConversation}
        canChat={Boolean(snapshot?.permissions.canChat)}
        contextPatches={props.contextPatchDisplay}
        onAcceptContextPatch={(id) => props.onAcceptContextPatch?.(id)}
        onRejectContextPatch={(id) => props.onRejectContextPatch?.(id)}
        onEditContextPatch={(id) => props.onEditContextPatch?.(id)}
        onRevertContextPatch={(id) => props.onRevertContextPatch?.(id)}
        onReviewContextPatch={(id) => props.onReviewContextPatch?.(id)}
        onOpenContextInTree={(id) => props.onOpenContextInTree?.(id)}
        pastedImage={props.pastedImage}
        onRemovePastedImage={props.onRemovePastedImage}
        onPreparePlan={props.onPreparePlan}
        startScreen
        recentProjects={recentProjects}
        onStartNew={() => {
          window.setTimeout(() => document.getElementById('bago-chat-composer')?.focus(), 0);
        }}
        onContinue={() => {
          try { window.sessionStorage.removeItem('bago.context.initial-branch'); } catch { /* storage unavailable */ }
          props.onSetSection('context');
        }}
        onChooseRecent={(id) => {
          try { window.sessionStorage.setItem('bago.context.initial-branch', id); } catch { /* storage unavailable */ }
          props.onSetSection('context');
        }}
        onRefresh={props.onRefresh}
      />
    );
  }

  if (props.section === 'workspace') {
    return (
      <WorkspaceModule
        client={props.client}
        snapshot={snapshot}
        contextTree={props.contextTree}
        apiBase={props.apiBase}
        apiToken={props.apiToken}
        initialOpenPath={props.workspaceOpenRequest?.path || null}
        onInspect={props.onInspect}
        onNavigate={props.onSetSection}
        onSendChat={props.onSendChat}
        onCreatePlan={props.onRunPlanTask}
        onRunCommand={async (command) => { await props.onRunCommand(command); }}
        onChooseWorkspace={props.onChooseWorkspace}
      />
    );
  }

  if (props.section === 'pipeline') {
    const task = props.drafts.pipeline || '';
    const taskNodes = props.contextTree.tree
      ? Object.values(props.contextTree.tree.nodes)
        .filter((node) => node.parentId === props.contextTree.tree?.rootId && (node.type === 'pending' || node.metadata?.branch === true))
        .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
      : [];
    const canRetry = statusTone(pipelineStatus) === 'error' && Boolean(task.trim()) && Boolean(snapshot?.permissions.canRetryPipeline);
    const stopCommand = commandAvailable(props.menu, props.routes, /task cancel|\/stop|pipeline stop/) ? '/task cancel' : null;
    const canStop = statusTone(pipelineStatus) === 'running' && Boolean(stopCommand) && Boolean(snapshot?.permissions.canStopPipeline);
    const codeTaskSnapshot = asRecord(snapshot?.codeTask) || {};
    const codeTaskClassification = asRecord(codeTaskSnapshot.classification) || {};
    const codeTaskContract = asRecord(codeTaskSnapshot.contract) || {};
    const codeTaskPlan = asRecord(codeTaskContract.plan) || {};
    const codeReadFiles = stringList(codeTaskPlan?.read_files);
    const codeEditFiles = stringList(codeTaskPlan?.edit_files);
    const codeCreateFiles = stringList(codeTaskPlan?.create_files);
    const codeVerifySteps = stringList(codeTaskPlan?.verify_steps);
    const codeTaskObjective = String(codeTaskContract?.objective || codeTaskClassification?.objective || snapshot?.system.objective || 'Sin objetivo');
    const codeTaskOperation = String(codeTaskContract?.operation || codeTaskClassification?.kind || 'unknown');
    const hasCodeTask = Object.keys(codeTaskContract).length > 0 || Object.keys(codeTaskClassification).length > 0;
    const pipelineTitle = String(
      planData?.task
      || planData?.objective
      || planData?.execution_id
      || snapshot?.system.objective
      || (steps.length ? 'Flujo en ejecución' : 'No hay un flujo activo')
    );
    const startPendingPlan = async () => {
      if (!pendingStep) return;
      setPendingStepBusy(true);
      setPendingStepError('');
      try {
        const listed = await props.client.listPlans();
        const availablePlans = Array.isArray(listed.plans)
          ? listed.plans.filter((item): item is RecordValue => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
          : [];
        const taskName = String(planData?.task || planData?.objective || '').trim();
        const matchedPlan = availablePlans.find((item) => String(item.id || item.plan_id || '') === String(planData?.id || planData?.plan_id || ''))
          || availablePlans.find((item) => taskName && String(item.task || item.objective || '').trim() === taskName)
          || availablePlans.find((item) => String(item.status || '').toLowerCase() === 'pending');
        const planId = String(planData?.id || planData?.plan_id || matchedPlan?.id || matchedPlan?.plan_id || '').trim();
        if (!planId) throw new Error('No se encontró un plan ejecutable para este paso. Vuelve a generar el plan antes de iniciarlo.');
        const result = await props.client.executePlan(planId, { stop_on_failure: true });
        if (result.ok === false) throw new Error(String(result.error || 'El backend no pudo iniciar el plan.'));
        setPendingStep(null);
        props.onRefresh();
      } catch (error) {
        setPendingStepError(error instanceof Error ? error.message : 'No se pudo iniciar el plan.');
      } finally {
        setPendingStepBusy(false);
      }
    };
    const startFlowTask = (title: string, summary: string) => {
      const task = [title.trim(), summary.trim()].filter(Boolean).join('\n\n');
      props.onDraftChange('pipeline', task);
      setPipelineView('create');
    };
    const pipelineTabs = <nav className="pipeline-view-tabs contextual-subnav" aria-label="Vistas de Pipeline">
      <button type="button" aria-current={pipelineView === 'create' ? 'page' : undefined} className={pipelineView === 'create' ? 'is-active' : ''} onClick={() => setPipelineView('create')}><Icon name="plus" size={16} /> Crear</button>
      <button type="button" aria-current={pipelineView === 'execution' ? 'page' : undefined} className={pipelineView === 'execution' ? 'is-active' : ''} onClick={() => setPipelineView('execution')}><Icon name="pipeline" size={16} /> Ejecución</button>
      <button type="button" aria-current={pipelineView === 'flow' ? 'page' : undefined} className={pipelineView === 'flow' ? 'is-active' : ''} onClick={() => setPipelineView('flow')}><Icon name="graph" size={16} /> Flujo</button>
      <button type="button" aria-current={pipelineView === 'control' ? 'page' : undefined} className={pipelineView === 'control' ? 'is-active' : ''} onClick={() => setPipelineView('control')}><Icon name="history" size={16} /> Planes y programación</button>
      <button type="button" aria-current={pipelineView === 'capabilities' ? 'page' : undefined} className={pipelineView === 'capabilities' ? 'is-active' : ''} onClick={() => setPipelineView('capabilities')}><Icon name="pack" size={16} /> Capacidades</button>
      <button type="button" aria-current={pipelineView === 'simulation' ? 'page' : undefined} className={pipelineView === 'simulation' ? 'is-active' : ''} onClick={() => setPipelineView('simulation')}><Icon name="trace" size={16} /> Simulación</button>
      <button type="button" aria-current={pipelineView === 'rl' ? 'page' : undefined} className={pipelineView === 'rl' ? 'is-active' : ''} onClick={() => setPipelineView('rl')}><Icon name="live" size={16} /> Entrenamiento RL</button>
    </nav>;
    if (pipelineView === 'create') {
      return <div className="pipeline-surface contextual-surface pipeline-create-view" {...inspectMenuAttrs(screenSelection, props.onInspect)}>
        {pipelineTabs}
        <PipelineGuidedBuilder
          client={props.client}
          task={task}
          hasSteps={steps.length > 0}
          onTaskChange={(value) => props.onDraftChange('pipeline', value)}
          onCreatePlan={props.onRunPlanTask}
          onOpenCapabilities={() => setPipelineView('capabilities')}
          onCreated={() => { props.onRefresh(); setPipelineView('execution'); }}
        />
      </div>;
    }
    if (pipelineView === 'flow') {
      return <div className="pipeline-surface pipeline-flow-view" {...inspectMenuAttrs(screenSelection, props.onInspect)}>
        {pipelineTabs}
        {flowNotice && (
          <div className={`context-collection-notice tone-${flowNotice.tone}`} style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 12px 0' }}>
            <Icon name={flowNotice.tone === 'error' ? 'warning' : flowNotice.tone === 'warning' ? 'alert' : 'check-circle'} size={12} />
            <span style={{ flex: 1 }}>{flowNotice.message}</span>
            <button type="button" className="icon-only" aria-label="Cerrar aviso" onClick={() => setFlowNotice(null)}><Icon name="close" size={12} /></button>
          </div>
        )}
        <WorkGraph
          proposals={props.contextTree.proposals}
          tasks={taskNodes}
          steps={steps}
          pipelineStatus={pipelineStatus}
          focused={graphFiltered}
          onFocusedChange={setGraphFiltered}
          onValidate={(proposal) => { void props.contextTree.acceptPatch(proposal.id).then((result) => { if (!result.ok) setFlowNotice({ tone: 'error', message: result.error || 'No se pudo validar la mención.' }); }); }}
          onEdit={(proposal) => { props.onEditContextPatch?.(proposal.id); props.onSetSection('context'); }}
          onStartProposal={(proposal) => startFlowTask(proposal.title, proposal.reason || 'Ejecutar la tarea mencionada en el contexto.')}
          onStartTask={(taskNode) => startFlowTask(taskNode.title, taskNode.summary || 'Ejecutar la tarea abierta desde el contexto de trabajo.')}
          onOpenTask={(taskNode) => { try { window.sessionStorage.setItem('bago.context.initial-branch', taskNode.id); } catch { /* unavailable */ } props.onSetSection('context'); }}
          onOpenContext={() => props.onSetSection('context')}
          onOpenPipeline={() => setPipelineView('execution')}
        />
      </div>;
    }
    if (pipelineView === 'control') {
      return <div className="pipeline-surface contextual-surface">
        {pipelineTabs}
        <PipelineControlPanel client={props.client} onRefreshSnapshot={props.onRefresh} onSetSection={props.onSetSection} />
      </div>;
    }
    if (pipelineView === 'capabilities') {
      return <div className="pipeline-surface contextual-surface">
        {pipelineTabs}
        <CapabilityAnatomyModule client={props.client} onInspect={(selection) => props.onInspect(selection, 'detail')} />
        <ExternalCapabilitiesPanel client={props.client} />
      </div>;
    }
    if (pipelineView === 'simulation') {
      return <div className="pipeline-surface contextual-surface system-surface">
        {pipelineTabs}
        <SimulationLaboratory client={props.client} />
      </div>;
    }
    if (pipelineView === 'rl') {
      return <div className="pipeline-surface contextual-surface system-surface">
        {pipelineTabs}
        <RlTrainingLaboratory client={props.client} />
      </div>;
    }
    return (
      <div className="pipeline-surface pipeline-execution-view" {...inspectMenuAttrs(screenSelection, props.onInspect)}>
        {pipelineTabs}
        <section className="pipeline-page-head">
          <div className="pipeline-summary-copy">
            <StatusBadge status={pipelineStatus} />
            <h2>{pipelineTitle}</h2>
            <p>{steps.length ? `${doneCount} de ${steps.length} pasos completados${blockedCount + failedCount ? ` · ${blockedCount + failedCount} requieren atención` : ''}` : 'Describe el resultado que necesitas.'}</p>
          </div>
          <div className="pipeline-summary-actions">
            {canRetry && <ActionButton icon="retry" onClick={() => void props.onRunPlanTask(task)}>Reintentar</ActionButton>}
            {canStop && stopCommand && <ActionButton icon="stop" onClick={() => void props.onRunCommand(stopCommand)}>Detener</ActionButton>}
          </div>
        </section>

        {hasCodeTask && (
          <section className="pipeline-contract">
            <div className="pipeline-contract-status">
              <StatusBadge status={codeTaskContract?.refused ? 'rejected' : codeTaskPlan?.requires_model_review ? 'blocked' : 'confirmed'} label={codeTaskOperation} />
            </div>
            <div className="pipeline-contract-overview">
              <article className="contract-card">
                <span>Objetivo</span>
                <strong>{codeTaskObjective}</strong>
                <p>{String(codeTaskContract?.language || codeTaskClassification?.language || 'unknown')} · {String(codeTaskContract?.task_id || 'sin task id')}</p>
              </article>
              <article className="contract-card">
                <span>Estado</span>
                <strong>{codeTaskContract?.refused ? 'Rechazado' : codeTaskPlan?.requires_model_review ? 'Requiere revisión' : 'Compilado'}</strong>
                <p>{String(codeTaskContract?.refusal_reason || codeTaskPlan?.finish_message || 'Sin observaciones')}</p>
              </article>
            </div>
            <div className="pipeline-contract-grid">
              <button type="button" className="contract-group" onClick={() => props.onInspect(buildSelection(
                'code-task-read',
                'code-task-plan',
                'Archivos a leer',
                codeReadFiles.join(', ') || 'Sin archivos de lectura',
                [`count: ${codeReadFiles.length}`, `operation: ${codeTaskOperation}`],
                codeTaskPlan?.read_files || []
              ))}>
                <span className="contract-group-label">Read</span>
                <strong>{codeReadFiles.length}</strong>
                <small>{codeReadFiles.length ? codeReadFiles.join(' · ') : 'Sin archivos de lectura'}</small>
              </button>
              <button type="button" className="contract-group" onClick={() => props.onInspect(buildSelection(
                'code-task-edit',
                'code-task-plan',
                'Archivos a editar',
                codeEditFiles.join(', ') || 'Sin archivos de edición',
                [`count: ${codeEditFiles.length}`, `operation: ${codeTaskOperation}`],
                codeTaskPlan?.edit_files || []
              ))}>
                <span className="contract-group-label">Edit</span>
                <strong>{codeEditFiles.length}</strong>
                <small>{codeEditFiles.length ? codeEditFiles.join(' · ') : 'Sin archivos de edición'}</small>
              </button>
              <button type="button" className="contract-group" onClick={() => props.onInspect(buildSelection(
                'code-task-create',
                'code-task-plan',
                'Archivos a crear',
                codeCreateFiles.join(', ') || 'Sin archivos de creación',
                [`count: ${codeCreateFiles.length}`, `operation: ${codeTaskOperation}`],
                codeTaskPlan?.create_files || []
              ))}>
                <span className="contract-group-label">Create</span>
                <strong>{codeCreateFiles.length}</strong>
                <small>{codeCreateFiles.length ? codeCreateFiles.join(' · ') : 'Sin archivos de creación'}</small>
              </button>
              <button type="button" className="contract-group" onClick={() => props.onInspect(buildSelection(
                'code-task-verify',
                'code-task-plan',
                'Verificaciones',
                codeVerifySteps.join(', ') || 'Sin verificaciones',
                [`count: ${codeVerifySteps.length}`, `operation: ${codeTaskOperation}`],
                codeTaskPlan?.verify_steps || []
              ))}>
                <span className="contract-group-label">Verify</span>
                <strong>{codeVerifySteps.length}</strong>
                <small>{codeVerifySteps.length ? codeVerifySteps.join(' · ') : 'Sin verificaciones'}</small>
              </button>
            </div>
          </section>
        )}

        <section className="pipeline-timeline">
          <div className="pipeline-section-head"><strong>Pasos</strong><span>{steps.length ? `${doneCount} completados · ${steps.length - doneCount} pendientes` : 'Aún no hay pasos'}</span></div>
          {steps.length ? steps.map((step, index) => {
            const status = String(step.status || 'pending');
            const stepSelection = buildSelection(
              String(step.number || index + 1),
              'pipeline-step',
              String(step.description || `Paso ${index + 1}`),
              status,
              [`status: ${status}`, `evidence: ${Array.isArray(step.evidence) ? step.evidence.length : 0}`, `required evidence: ${Array.isArray(step.required_evidence) ? step.required_evidence.length : 0}`, `block reason: ${String(step.block_reason || 'none')}`],
              step,
              'pipeline.step'
            );
            return (
              <button
                key={String(step.number || index)}
                type="button"
                className={`pipeline-step state-${statusTone(status)}`}
                {...inspectMenuAttrs(stepSelection, props.onInspect)}
                onClick={() => {
                  if (status.toLowerCase() === 'pending') {
                    setPendingStep(step);
                    setPendingStepError('');
                    return;
                  }
                  props.onInspect(stepSelection);
                }}
              >
                <span className="step-index">{String(step.number || index + 1)}</span>
                <span className="step-copy"><strong>{String(step.description || `Paso ${index + 1}`)}</strong><small>{String(step.block_reason || step.result || status)}</small></span>
                <StatusBadge status={status} />
                <Icon name="chevron" size={15} />
              </button>
            );
          }) : (
            <div className="empty-state"><Icon name="pipeline" size={25} /><h3>Sin pasos todavía</h3><p>Genera un plan para visualizar su ejecución.</p></div>
          )}
        </section>

        <ConfirmDialog
          open={Boolean(pendingStep)}
          title={`¿Iniciar ${String(pendingStep?.description || pendingStep?.label || `Paso ${pendingStep?.number || ''}`)}?`}
          description="BAGO ejecutará el plan desde el primer paso pendiente y se detendrá si encuentra un bloqueo."
          confirmLabel="Sí, iniciar"
          busy={pendingStepBusy}
          error={pendingStepError}
          onConfirm={() => void startPendingPlan()}
          onClose={() => {
            if (pendingStepBusy) return;
            setPendingStep(null);
            setPendingStepError('');
          }}
        />
      </div>
    );
  }

  if (props.section === 'evidence') {
    const evidenceTabs = <nav className="contextual-subnav" aria-label="Vistas de Evidencia">
      <button type="button" className={evidenceView === 'receipts' ? 'is-active' : ''} onClick={() => setEvidenceView('receipts')}><Icon name="evidence" size={13} /> Recibos y trazas</button>
      <button type="button" className={evidenceView === 'audit' ? 'is-active' : ''} onClick={() => setEvidenceView('audit')}><Icon name="inspector" size={13} /> Auditoría</button>
    </nav>;
    if (evidenceView === 'audit') {
      return <div className="evidence-surface contextual-surface system-surface">
        {evidenceTabs}
        <SystemTabs
          apiBase={props.apiBase}
          apiToken={props.apiToken}
          providers={providers}
          routerEntries={chatModelEntries}
          routerAuto={false}
          routerSelectedCount={0}
          routerLastPick=""
          onRefreshRouter={props.onRefreshRouter}
          onToggleRouter={props.onToggleRouter}
          onSetRouterAuto={props.onSetRouterAuto}
          onConfigureProvider={(name, config) => props.onConfigureProvider ? props.onConfigureProvider(name, config) : Promise.resolve()}
          onInspectSelection={(selection, position) => props.onInspect(selection, position)}
          allowedTabs={['audit']}
          activeTab="audit"
          hideTabList
        />
      </div>;
    }
    const latest = evidenceItems.length ? (evidenceItems[0] as RecordValue) : historyMessages.length ? historyMessages[historyMessages.length - 1] : (asRecord(snapshot?.context) || {});
    const previous = historyMessages.length > 1 ? historyMessages[historyMessages.length - 2] : null;
    const receiptId = snapshot?.context.receiptId || String(latest.id || latest.receipt_id || latest.envelope_id || 'Sin identificador');
    const latestSelection = buildSelection(
      receiptId,
      'evidence',
      'Última evidencia',
      String(latest.message || latest.text || latest.summary || summarizeMessage(latest) || `Evidencia ${receiptId}`),
      [`status: ${snapshot?.context.certificationStatus || snapshot?.context.state || 'unknown'}`, `source: ${String(latest.source || latest.origin || 'backend')}`, `context revision: ${String(snapshot?.context.revision || 'unknown')}`],
      latest,
      'evidence.item'
    );
    return (
      <div className="evidence-surface" {...inspectMenuAttrs(screenSelection, props.onInspect)}>
        {evidenceTabs}
        <section className="evidence-primary" {...inspectMenuAttrs(latestSelection, props.onInspect)}>
          <div className="evidence-heading">
            <div>
              <span className="surface-eyebrow">Última evidencia</span>
              <h2>{receiptId}</h2>
            </div>
          </div>
          <p className="evidence-narrative">{latestSelection.summary}</p>
          <div className="evidence-actions">
            <ActionButton icon="inspector" primary onClick={() => props.onInspect(latestSelection, 'detail')}>Ver detalle</ActionButton>
            {previous && <ActionButton icon="compare" onClick={() => setEvidenceCompare((value) => !value)}>Comparar</ActionButton>}
            <span className="context-hint"><Icon name="more" size={14} /> Click derecho para raw, copiar ID, certificar contexto o abrir vínculos.</span>
            <ContextActionButton selection={latestSelection} onInspect={props.onInspect} label="Acciones de evidencia" />
          </div>
        </section>

        {evidenceCompare && previous && (
          <section className="evidence-comparison">
            <div className="comparison-grid">
              <article><span>Anterior</span><strong>{String(previous.id || previous.receipt_id || 'sin id')}</strong><p>{summarizeMessage(previous).slice(0, 240) || 'Sin resumen'}</p></article>
              <article><span>Actual</span><strong>{receiptId}</strong><p>{latestSelection.summary}</p></article>
            </div>
          </section>
        )}

        <section className="evidence-history">
          <div className="compact-list">
            {(evidenceItems.length ? evidenceItems : historyMessages).slice(-6).reverse().map((message, index) => {
              const historySelection = buildSelection(
                String(message.id || index),
                'history-message',
                String(message.role || message.type || 'Evidencia'),
                String(message.message || message.text || summarizeMessage(message)).slice(0, 220),
                [`timestamp: ${String(message.timestamp || message.created_at || 'unknown')}`, `source: ${String(message.source || message.origin || 'history')}`],
                message,
                'evidence.item'
              );
              return (
              <button
                key={`${String(message.id || message.timestamp || index)}`}
                type="button"
                {...inspectMenuAttrs(historySelection, props.onInspect)}
                onClick={() => props.onInspect(historySelection)}
              >
                <span className="compact-list-icon"><Icon name="evidence" size={16} /></span>
                <span><strong>{String(message.role || message.type || 'evidencia')}</strong><small>{String(message.message || message.text || summarizeMessage(message)).slice(0, 110) || 'Sin resumen'}</small></span>
                <Icon name="chevron" size={14} />
              </button>
              );
            })}
          </div>
        </section>
      </div>
    );
  }

  if (props.section === 'context') {
    const contextTabs = <nav className="contextual-subnav" aria-label="Vistas de Contexto">
      <button type="button" className={contextView === 'work' ? 'is-active' : ''} onClick={() => setContextView('work')}><Icon name="context" size={13} /> Contexto de trabajo</button>
      <button type="button" className={contextView === 'routes' ? 'is-active' : ''} onClick={() => setContextView('routes')}><Icon name="actions" size={13} /> API avanzada</button>
    </nav>;
    if (contextView === 'routes') {
      return <div className="contextual-surface system-surface">
        {contextTabs}
        <SystemTabs
          apiBase={props.apiBase}
          apiToken={props.apiToken}
          providers={providers}
          routerEntries={chatModelEntries}
          routerAuto={false}
          routerSelectedCount={0}
          routerLastPick=""
          onRefreshRouter={props.onRefreshRouter}
          onToggleRouter={props.onToggleRouter}
          onSetRouterAuto={props.onSetRouterAuto}
          onConfigureProvider={(name, config) => props.onConfigureProvider ? props.onConfigureProvider(name, config) : Promise.resolve()}
          onInspectSelection={(selection, position) => props.onInspect(selection, position)}
          allowedTabs={['routes']}
          activeTab="routes"
          hideTabList
        />
      </div>;
    }
    return (
      <div className="contextual-surface context-contextual-surface">
        {contextTabs}
        <ContextTreeModule
        ctx={props.contextTree}
        apiBase={props.apiBase}
        apiToken={props.apiToken}
        workspaceRoot={snapshot?.project.root || snapshot?.workspace.scopeRoot || snapshot?.workspace.repoRoot || ''}
        onSetSection={props.onSetSection}
        onCreatePlan={(title, summary) => {
          const task = [title.trim(), summary.trim()].filter(Boolean).join('\n\n');
          props.onDraftChange('pipeline', task);
          props.onSetSection('pipeline');
          return Promise.resolve();
        }}
        onRunContextCommand={props.onRunContextCommand}
        onOpenInWorkspace={(path) => {
          // CANON[WS-009]: abrir un archivo desde el árbol de contexto
          // lo enfoca en la pantalla Workspace (mismo flujo que el menú
          // contextual del árbol). El módulo de contexto no salta
          // secciones: pide al workspace que muestre el archivo.
          props.onSetSection('workspace');
          props.onInspect(
            buildSelection(
              path,
              'workspace-file',
              String(path.split('/').pop() || path),
              `Abierto desde Árbol de Contexto`,
              [`path: ${path}`],
              { path },
              'workspace.file'
            ),
            'detail'
          );
        }}
        incomingPatches={props.incomingContextPatches}
        onPatchHandled={props.onContextPatchHandled}
        bankPending={props.contextBankPending}
        onBankPendingConsumed={props.onContextBankPendingConsumed}
        initialSelectedNodeId={props.initialContextSelectedNodeId}
        initialEditingPatchId={props.initialContextEditingPatchId}
        onInitialStateConsumed={props.onInitialContextStateConsumed}
        />
      </div>
    );
  }

  if (props.section === "system") {
    const routerEntries = resolveRouterEntries(props.router);
    const routerAuto = Boolean(props.router?.policy?.auto_switch ?? props.router?.list?.auto_switch);
    const routerSelectedCount = props.router?.policy?.selected_count ?? props.router?.list?.selected_count ?? routerEntries.filter((entry) => Boolean(entry.selected)).length;
    const routerLastPick = String(props.router?.policy?.last_pick || props.router?.list?.last_pick || "—");
    const operationTabs = [
      ['providers', 'Proveedores', 'server'],
      ['runtime', 'Runtime', 'live'],
      ['memory', 'Memoria', 'bank'],
      ['vision', 'Visión', 'review'],
      ['configuration', 'Configuración', 'cog']
    ] as const;
    const selectOperationView = (id: typeof operationView) => {
      setOperationView(id);
      if (id === 'configuration') {
        // Opening the configuration surface is an explicit read of its
        // backend authority. The cards also hydrate themselves on mount, but
        // preloading here keeps the transition deterministic in Electron.
        void Promise.all([
          props.client.getAutoConfigStatus(),
          props.client.getModelBlacklist(),
        ]).catch(() => undefined);
      }
    };
    const providerCenter = <ProviderCenterModule
      title="Centro de proveedores"
      subtitle="Configura proveedores, elige modelos para la sesión y controla el router desde una sola superficie."
      frameworkLabel={String(snapshot?.framework.root || 'Framework no confirmado')}
      projectLabel={String(snapshot?.project.root || 'Proyecto no confirmado')}
      scopeLabel={String(snapshot?.workspace.scopeRoot || 'Scope no confirmado')}
      providers={providers.map((provider, index): ProviderCenterProvider => ({
        id: String(provider.id || provider.name || index),
        name: String(provider.name || provider.id || 'Proveedor'),
        description: String(provider.description || ''),
        state: String(provider.state || ''),
        configured: Boolean(provider.configured ?? false),
        modelCount: Array.isArray(provider.models) ? provider.models.length : Number(provider.modelCount ?? 0),
        models: Array.isArray(provider.models) ? provider.models.map((model) => typeof model === 'string' ? model : String((model as RecordValue).id || (model as RecordValue).model_id || '')).filter(Boolean) : [],
        raw: provider
      }))}
      routerEntries={chatModelEntries.map((entry, index): ProviderCenterRouterEntry => ({
        id: String(entry.key || `${entry.provider || 'provider'}/${entry.model_id || entry.wire_name || index}`),
        label: String(entry.wire_name || entry.model_id || entry.provider || 'Modelo'),
        provider: String(entry.provider || ''),
        bestFor: String(entry.best_for || entry.provider || ''),
        available: entry.available !== false,
        selected: Boolean(entry.selected),
        contextTokens: Number(entry.context_tokens ?? 0) || undefined,
        raw: entry
      }))}
      routerAuto={routerAuto}
      routerSelectedCount={routerSelectedCount}
      routerLastPick={routerLastPick}
      sessionModel={props.sessionModel}
      onRefreshRouter={() => void props.onRefreshRouter()}
      onSetRouterAuto={(enabled) => void props.onSetRouterAuto(enabled)}
      onToggleRouter={(key) => void props.onToggleRouter(key)}
      onConfigureProvider={props.onConfigureProvider}
      onSetSessionModel={props.onSetSessionModel}
      onInspectProvider={(provider) => props.onInspect(buildSelection(
        provider.id,
        'provider',
        provider.name,
        provider.description || provider.state || 'Sin descripción',
        [`configured: ${String(provider.configured ?? false)}`, `models: ${String(provider.modelCount ?? 0)}`],
        provider.raw,
        'system.provider'
      ))}
      onInspectRouterEntry={(entry) => props.onInspect(buildSelection(
        entry.id,
        'router-entry',
        entry.label,
        entry.bestFor || entry.provider || 'Sin descripción',
        [`provider: ${entry.provider || 'unknown'}`, `selected: ${String(Boolean(entry.selected))}`, `context_tokens: ${String(entry.contextTokens ?? 'unknown')}`],
        entry.raw,
        'system.router'
      ))}
    />;
    return (
      <div className="system-surface contextual-surface operation-surface" {...inspectMenuAttrs(screenSelection, props.onInspect)}>
        <nav className="contextual-subnav operation-subnav" aria-label="Herramientas de Operaciones">
          {operationTabs.map(([id, label, icon]) => <button key={id} type="button" className={operationView === id ? 'is-active' : ''} aria-current={operationView === id ? 'page' : undefined} onClick={() => selectOperationView(id)}>
            <Icon name={icon} size={14} /> {label}
          </button>)}
        </nav>
        <div className="operation-workspace">
          {operationView === 'providers' && providerCenter}
          {operationView === 'runtime' && <section className="operation-tool-view"><header><h2>Runtime de modelos</h2><p>Catálogo visible, modelos locales cargados y políticas de descarga.</p></header><ProviderRuntimeTools client={props.client} /></section>}
          {operationView === 'memory' && <MemoryOperations client={props.client} />}
          {operationView === 'vision' && <VisionOperations client={props.client} />}
          {operationView === 'configuration' && <section className="operation-tool-view"><header><h2>Configuración operativa</h2><p>Descubrimiento automático y exclusiones del catálogo local.</p></header><div className="operation-configuration-grid"><AutoConfigCard client={props.client} /><BlacklistCard client={props.client} /></div></section>}
        </div>
      </div>
    );
  }

  const recentJobs = Array.isArray(snapshot?.jobs) ? snapshot.jobs.slice(0, 6) : [];
  const systemItems = [
    { label: 'Herramientas', state: snapshot?.permissions.canRunTools ? 'confirmed' : 'blocked', detail: `${snapshot?.system.activeBridges?.length || 0} bridges activos`, icon: 'actions' as IconName },
    { label: 'Contexto', state: snapshot?.context.state || 'unknown', detail: snapshot?.context.receiptId || 'Sin receipt', icon: 'context' as IconName },
    { label: 'Router', state: routerSelectedCount > 0 ? 'confirmed' : 'blocked', detail: routerSelectedCount > 0 ? `${routerSelectedCount} rutas activas` : 'sin rutas activas', icon: 'model' as IconName }
  ];
  return (
    <div className="system-surface" {...inspectMenuAttrs(screenSelection, props.onInspect)}>
      <section className="system-grid">
        {systemItems.map((item) => (
          <button
            key={item.label}
            type="button"
            className="system-item"
            onClick={() => props.onInspect(buildSelection(item.label.toLowerCase(), 'system-component', item.label, item.detail, [`state: ${item.state}`], item))}
          >
            <span className="system-item-icon"><Icon name={item.icon} size={18} /></span>
            <span><small>{item.label}</small><strong>{item.detail}</strong></span>
            <StatusBadge status={item.state} />
          </button>
        ))}
      </section>

      <section className="system-secondary-grid">
        <article className="system-panel">
          <div className="system-panel-head">
            <div>
              <span className="surface-eyebrow">Router</span>
              <strong>{routerSelectedCount ? `${routerSelectedCount} seleccionados` : 'Sin selección activa'}</strong>
            </div>
            <div className="system-panel-actions">
              <button className="text-button" type="button" onClick={() => void props.onRefreshRouter?.()}>
                <Icon name="refresh" size={14} /> Refrescar
              </button>
              <button className={`text-button ${routerAuto ? 'is-active' : ''}`} type="button" onClick={() => void props.onSetRouterAuto(!routerAuto)}>
                <Icon name="layout" size={14} /> Auto {routerAuto ? 'on' : 'off'}
              </button>
            </div>
          </div>
          <div className="compact-list">
            {routerEntries.slice(0, 8).map((entry, index) => {
              const key = String(entry.key || `${entry.provider || 'provider'}:${entry.model_id || entry.wire_name || index}`);
              return (
                <div key={key} className="system-router-row">
                  <button
                    type="button"
                    onClick={() => props.onInspect(buildSelection(
                      key,
                      'router-entry',
                      String(entry.wire_name || entry.model_id || entry.provider || 'Modelo'),
                      String(entry.best_for || entry.wire_name || entry.model_id || 'Sin descripción'),
                      [
                        `provider: ${String(entry.provider || 'unknown')}`,
                        `available: ${String(Boolean(entry.available))}`,
                        `selected: ${String(Boolean(entry.selected))}`,
                        `context_tokens: ${String(entry.context_tokens ?? 'unknown')}`
                      ],
                      entry
                    ))}
                  >
                    <span className="compact-list-icon"><Icon name="model" size={16} /></span>
                    <span><strong>{String(entry.wire_name || entry.model_id || entry.provider || 'Modelo')}</strong><small>{String(entry.best_for || entry.provider || '')}</small></span>
                    <StatusBadge status={entry.selected ? 'confirmed' : entry.available === false ? 'blocked' : 'unknown'} />
                  </button>
                  <button className="secondary-button compact" type="button" onClick={() => void props.onToggleRouter(key)}>
                    {entry.selected ? 'Quitar' : 'Usar'}
                  </button>
                </div>
              );
            })}
            {!routerEntries.length && (
              <div className="palette-empty">No hay política de router disponible.</div>
            )}
          </div>
          <div className="system-panel-foot">
            <span>Última selección: {routerLastPick}</span>
          </div>
        </article>

        <article className="system-panel">
          <dl className="authority-list">
            <div><dt>Framework</dt><dd>{snapshot?.framework.root || 'No confirmado'}</dd></div>
            <div><dt>Proyecto</dt><dd>{snapshot?.project.root || 'No confirmado'}</dd></div>
            <div><dt>Scope</dt><dd>{snapshot?.workspace.scopeRoot || 'No confirmado'}</dd></div>
            <div><dt>Jobs</dt><dd>{recentJobs.length}</dd></div>
          </dl>
          <div className="system-panel-actions">
            <button className="text-button" type="button" onClick={() => void props.onRunCommand('/project status')}>
              Estado proyecto <Icon name="chevron" size={14} />
            </button>
            <button className="text-button" type="button" onClick={() => void props.onRunCommand('/project analyze')}>
              Analizar proyecto <Icon name="chevron" size={14} />
            </button>
            <button className="text-button" type="button" onClick={() => props.onSetSection('workspace')}>
              Abrir workspace <Icon name="chevron" size={14} />
            </button>
            <button className="text-button" type="button" onClick={() => props.onSetSection('evidence')}>
              Abrir evidencia <Icon name="chevron" size={14} />
            </button>
          </div>
          <button
            className="text-button"
            type="button"
            onClick={() => props.onInspect(buildSelection('routes', 'backend-routes', 'Rutas del backend', `${props.routes?.count || 0} rutas`, [`auth: ${String(props.routes?.auth || 'unknown')}`, `prefixes: ${props.routes?.api_prefixes?.join(', ') || 'none'}`], props.routes), 'raw')}
          >
            Inspeccionar rutas API <Icon name="chevron" size={14} />
          </button>
        </article>

        <article className="system-panel">
          <div className="system-panel-head">
            <div>
              <span className="surface-eyebrow">Jobs</span>
              <strong>{recentJobs.length ? `${recentJobs.length} recientes` : 'Sin jobs visibles'}</strong>
            </div>
            <button className="text-button" type="button" onClick={() => props.onSetSection('pipeline')}>
              Ir a pipeline <Icon name="chevron" size={14} />
            </button>
          </div>
          <div className="compact-list">
            {recentJobs.map((job, index) => (
              <button
                key={String(job.execution_id || index)}
                type="button"
                onClick={() => props.onInspect(buildSelection(
                  String(job.execution_id || index),
                  'job',
                  String(job.kind || 'job'),
                  String(job.status || 'unknown'),
                  [
                    `execution_id: ${String(job.execution_id || 'unknown')}`,
                    `status: ${String(job.status || 'unknown')}`,
                    `kind: ${String(job.kind || 'unknown')}`
                  ],
                  job
                ))}
              >
                <span className="compact-list-icon"><Icon name="history" size={16} /></span>
                <span><strong>{String(job.kind || 'job')}</strong><small>{String(job.status || 'unknown')}</small></span>
                <Icon name="chevron" size={14} />
              </button>
            ))}
          </div>
          <div className="system-panel-foot">
            <span>Los jobs cancelables se resuelven en Pipeline.</span>
          </div>
        </article>

        <AutoConfigCard client={props.client} />

        <BlacklistCard client={props.client} />

        <ProviderCenterModule
          title="Catálogo del sistema"
          subtitle="Las tarjetas de esta superficie son reutilizables y pueden extraerse a otra app sin depender del shell de BAGO."
          frameworkLabel={String(snapshot?.framework.root || 'No confirmado')}
          projectLabel={String(snapshot?.project.root || 'No confirmado')}
          scopeLabel={String(snapshot?.workspace.scopeRoot || 'No confirmado')}
          providers={providers.map((provider, index): ProviderCenterProvider => ({
            id: String(provider.id || provider.name || index),
            name: String(provider.name || provider.id || 'Provider'),
            description: String(provider.description || ''),
            state: String(provider.state || ''),
            configured: Boolean(provider.configured ?? false),
            modelCount: Array.isArray(provider.models) ? provider.models.length : Number(provider.modelCount ?? 0),
            models: Array.isArray(provider.models) ? provider.models.map((model) => String(model)).filter(Boolean) : [],
            raw: provider
          }))}
          routerEntries={routerEntries.map((entry, index): ProviderCenterRouterEntry => ({
            id: String(entry.key || `${entry.provider || 'provider'}:${entry.model_id || entry.wire_name || index}`),
            label: String(entry.wire_name || entry.model_id || entry.provider || 'Modelo'),
            provider: String(entry.provider || ''),
            bestFor: String(entry.best_for || entry.provider || ''),
            available: Boolean(entry.available),
            selected: Boolean(entry.selected),
            contextTokens: Number(entry.context_tokens ?? 0) || undefined,
            raw: entry
          }))}
          routerAuto={routerAuto}
          routerSelectedCount={routerSelectedCount}
          routerLastPick={routerLastPick}
          sessionModel={props.sessionModel}
          onRefreshRouter={() => void props.onRefreshRouter?.()}
          onSetRouterAuto={(enabled) => void props.onSetRouterAuto(enabled)}
          onToggleRouter={(key) => void props.onToggleRouter(key)}
          onConfigureProvider={props.onConfigureProvider}
          onSetSessionModel={props.onSetSessionModel}
          onInspectProvider={(provider) => props.onInspect(buildSelection(
            provider.id,
            'provider',
            provider.name,
            provider.description || provider.state || 'Sin descripción',
            [
              `configured: ${String(provider.configured ?? false)}`,
              `models: ${String(provider.modelCount ?? 0)}`
            ],
            provider.raw,
            'system.provider'
          ))}
          onProviderContextMenu={(provider, event) => {
            event.preventDefault();
            event.stopPropagation();
            props.onInspect(buildSelection(
              provider.id,
              'provider',
              provider.name,
              provider.description || provider.state || 'Sin descripción',
              [
                `configured: ${String(provider.configured ?? false)}`,
                `models: ${String(provider.modelCount ?? 0)}`
              ],
              provider.raw,
              'system.provider'
            ), { x: event.clientX, y: event.clientY });
          }}
          onInspectRouterEntry={(entry) => props.onInspect(buildSelection(
            entry.id,
            'router-entry',
            entry.label,
            entry.bestFor || entry.provider || 'Sin descripción',
            [
              `provider: ${String(entry.provider || 'unknown')}`,
              `available: ${String(Boolean(entry.available))}`,
              `selected: ${String(Boolean(entry.selected))}`,
              `context_tokens: ${String(entry.contextTokens ?? 'unknown')}`
            ],
            entry.raw,
            'system.router'
          ))}
          onRouterEntryContextMenu={(entry, event) => {
            event.preventDefault();
            event.stopPropagation();
            props.onInspect(buildSelection(
              entry.id,
              'router-entry',
              entry.label,
              entry.bestFor || entry.provider || 'Sin descripción',
              [
                `provider: ${String(entry.provider || 'unknown')}`,
                `available: ${String(Boolean(entry.available))}`,
                `selected: ${String(Boolean(entry.selected))}`,
                `context_tokens: ${String(entry.contextTokens ?? 'unknown')}`
              ],
              entry.raw,
              'system.router'
            ), { x: event.clientX, y: event.clientY });
          }}
          onPanelContextMenu={(panel, event) => {
            event.preventDefault();
            event.stopPropagation();
            props.onInspect(buildSelection(
              `provider-center-${panel}`,
              `provider-center-${panel}`,
              panel === 'router' ? 'Router / Orquestador' : panel === 'providers' ? 'Catálogo de proveedores' : 'Centro de proveedores',
              `${providers.length} proveedores · ${routerEntries.length} rutas`,
              [
                `router_auto: ${String(routerAuto)}`,
                `selected: ${String(routerSelectedCount)}`,
                `last_pick: ${routerLastPick}`
              ],
              { panel, providers, routerEntries, routerAuto, routerSelectedCount, routerLastPick },
              panel === 'router' ? 'system.router' : panel === 'providers' ? 'system.provider' : 'system.surface'
            ), { x: event.clientX, y: event.clientY });
          }}
        />
      </section>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────
// AutoConfigCard: lanza y muestra el estado de la auto-configuración
// generada por tests (backend en /configure/auto/*).
// ────────────────────────────────────────────────────────────────────
function AutoConfigCard({ client }: { client: BagoClient }) {
  const [status, setStatus] = useState<{ kind: 'idle' | 'running' | 'done' | 'error'; data: Record<string, unknown> | null; lastApplied?: Record<string, unknown> }>({ kind: 'idle', data: null });
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    try {
      const d = await client.getAutoConfigStatus();
      setStatus((prev) => ({ ...prev, kind: (d.status as typeof status.kind) || 'idle', data: d }));
    } catch {
      setStatus({ kind: 'error', data: null });
    }
  };

  useEffect(() => { void refresh(); }, [client]);

  const start = async () => {
    setBusy(true);
    try {
      await client.startAutoConfig();
      await refresh();
    } finally {
      setBusy(false);
    }
  };
  const apply = async () => {
    setBusy(true);
    try {
      const d = await client.applyAutoConfig();
      if (d.applied) setStatus((prev) => ({ ...prev, lastApplied: d.applied as Record<string, unknown> }));
      await refresh();
    } finally {
      setBusy(false);
    }
  };

  const last = status.data?.last_job as Record<string, unknown> | undefined;
  const isRunning = status.kind === 'running';
  const total = (status.data?.total_models ?? last?.total_models ?? 0) as number;
  const tested = (status.data?.tested_models ?? last?.tested_models ?? 0) as number;
  const progress = total ? Math.round((tested / total) * 100) : 0;

  return (
    <article className="system-panel auto-config-card">
      <div className="system-panel-head">
        <div>
          <span className="surface-eyebrow"><Icon name="sparkle" size={14} /> Auto-configuración</span>
          <strong>{isRunning ? `Probando modelos… ${progress}%` : 'Genera la config óptima para esta máquina'}</strong>
          <small>Corre tests contra los modelos y propone default, traductor, blacklist y timeouts. Todo en LOCALAPPDATA.</small>
        </div>
        <div className="system-panel-actions">
          {isRunning ? (
            <button className="text-button" type="button" disabled>
              <Icon name="live" size={14} /> {tested}/{total}
            </button>
          ) : (
            <button className="primary-button compact" type="button" onClick={start} disabled={busy}>
              <Icon name="sparkle" size={14} /> Lanzar auto-test
            </button>
          )}
          {last && status.kind === 'done' && (
            <button className="secondary-button compact" type="button" onClick={apply} disabled={busy}>
              <Icon name="check" size={14} /> Aplicar
            </button>
          )}
        </div>
      </div>
      {last && (
        <div className="auto-config-summary">
          <span className="auto-config-pill"><Icon name="model" size={12} /> default: <strong>{(last as any).generated_config?.default_model || '—'}</strong></span>
          <span className="auto-config-pill"><Icon name="copy" size={12} /> traductor: <strong>{(last as any).generated_config?.translation_middleware?.translator_model || '—'}</strong></span>
          <span className="auto-config-pill"><Icon name="warning" size={12} /> blacklist: <strong>{((last as any).generated_config?.blacklist || []).length}</strong></span>
        </div>
      )}
    </article>
  );
}

// ────────────────────────────────────────────────────────────────────
// BlacklistCard: muestra y permite editar la blacklist local de modelos.
// ────────────────────────────────────────────────────────────────────
function BlacklistCard({ client }: { client: BagoClient }) {
  const [data, setData] = useState<{ models: string[]; reasons: Record<string, string>; path?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [modelToAdd, setModelToAdd] = useState('');
  const [reasonToAdd, setReasonToAdd] = useState('');
  const requestVersion = useRef(0);

  const applyData = (payload: Record<string, unknown>) => {
    setData({
      models: Array.isArray(payload.models) ? payload.models.map(String) : [],
      reasons: payload.reasons && typeof payload.reasons === 'object' && !Array.isArray(payload.reasons) ? payload.reasons as Record<string, string> : {},
      path: typeof payload.path === 'string' ? payload.path : undefined,
    });
  };

  const refresh = async () => {
    const version = ++requestVersion.current;
    try {
      const d = await client.getModelBlacklist();
      if (version === requestVersion.current) applyData(d);
    } catch {
      if (version === requestVersion.current) setData(null);
    }
  };
  useEffect(() => { void refresh(); }, [client]);

  const remove = async (model: string) => {
    ++requestVersion.current;
    setBusy(true);
    try {
      applyData(await client.modifyModelBlacklist({ action: 'remove', model }));
    } finally { setBusy(false); }
  };

  const add = async () => {
    const model = modelToAdd.trim();
    if (!model) return;
    ++requestVersion.current;
    setBusy(true);
    try {
      applyData(await client.modifyModelBlacklist({ action: 'add', model, reason: reasonToAdd.trim() }));
      setModelToAdd('');
      setReasonToAdd('');
    } finally { setBusy(false); }
  };

  return (
    <article className="system-panel blacklist-card">
      <div className="system-panel-head">
        <div>
          <span className="surface-eyebrow"><Icon name="shield" size={14} /> Blacklist local</span>
          <strong>{(data?.models.length ?? 0)} modelos bloqueados en esta máquina</strong>
          <small>Solo afecta a este PC. El archivo vive en {data?.path || 'LOCALAPPDATA\\.bago\\state\\'}.</small>
        </div>
        <div className="system-panel-actions">
          <button className="text-button" type="button" onClick={refresh} disabled={busy}>
            <Icon name="refresh" size={14} /> Refrescar
          </button>
        </div>
      </div>
      <form className="blacklist-add-form" onSubmit={(event) => { event.preventDefault(); void add(); }}>
        <label className="blacklist-add-field">
          <span>Modelo</span>
          <input aria-label="Modelo para blacklist" value={modelToAdd} onChange={(event) => setModelToAdd(event.target.value)} placeholder="provider/model" disabled={busy} />
        </label>
        <label className="blacklist-add-field">
          <span>Motivo</span>
          <input aria-label="Motivo de blacklist" value={reasonToAdd} onChange={(event) => setReasonToAdd(event.target.value)} placeholder="Motivo opcional" disabled={busy} />
        </label>
        <button className="primary-button compact" type="submit" disabled={busy || !modelToAdd.trim()}>
          <Icon name="plus" size={14} /> Añadir
        </button>
      </form>
      {data && data.models.length > 0 && (
        <ul className="blacklist-list">
          {data.models.map((model) => (
            <li key={model} className="blacklist-item">
              <span className="blacklist-model"><Icon name="warning" size={12} /> {model}</span>
              <span className="blacklist-reason">{data.reasons[model] || 'Sin razón'}</span>
              <button className="text-button" type="button" onClick={() => remove(model)} disabled={busy} title={`Quitar ${model} de la blacklist`}>
                <Icon name="close" size={12} /> Quitar
              </button>
            </li>
          ))}
        </ul>
      )}
      {data && data.models.length === 0 && (
        <p className="blacklist-empty">Blacklist vacía.</p>
      )}
    </article>
  );
}

// ────────────────────────────────────────────────────────────────────
// Sub-componentes de la pantalla Workspace.
//
// Estos cinco componentes son la nueva capa de chrome de la pantalla
// Workspace. Reemplazan la franja fija grande que antes mezclaba
// buscador + chips de filtro + acciones + bloque de fuentes + form de
// "añadir fuente". Cada uno tiene una responsabilidad única:
//   - FilterDropdown:           lista de filtros en un <details>.
//   - WorkspaceMenuButton:      botón con menú para el workspace
//                                (cambiar, sincronizar, persistir, etc).
//   - WorkspaceActionsMenu:     menú ⋯ con acciones secundarias
//                                (expandir, contraer, releer, etc).
//   - WorkspaceReadinessAlert:  aviso compacto cuando el workspace
//                                tiene un problema accionable.
//   - SourcesDrawer:            drawer que lista fuentes y permite
//                                añadir/quitar.
// ────────────────────────────────────────────────────────────────────

// Catálogo único de filtros. Se mantiene aquí (y no en filterLabelForType)
// porque es la fuente de verdad del menú desplegable.
const WORKSPACE_FILTER_OPTIONS: { id: WorkspaceFilter; label: string; icon: IconName }[] = [
  { id: 'all', label: 'Todo', icon: 'actions' },
  { id: 'code', label: 'Código', icon: 'file' },
  { id: 'python', label: 'Python', icon: 'file' },
  { id: 'text', label: 'Texto', icon: 'file' },
  { id: 'json', label: 'JSON', icon: 'file' },
  { id: 'web', label: 'Web', icon: 'file' },
  { id: 'shell', label: 'Shell', icon: 'file' },
  { id: 'other', label: 'Otros', icon: 'file' },
  { id: 'directory', label: 'Carpetas', icon: 'folder' }
];

function FilterDropdown(props: { value: WorkspaceFilter; onChange: (next: WorkspaceFilter) => void }) {
  const current = WORKSPACE_FILTER_OPTIONS.find((opt) => opt.id === props.value) || WORKSPACE_FILTER_OPTIONS[0];
  return (
    <details className="filter-dropdown" role="listbox" aria-label="Filtrar archivos">
      <summary className="toolbar-button" aria-haspopup="listbox" title="Filtrar archivos por tipo">
        <Icon name="filter" size={15} />
        <span className="filter-dropdown-label">
          <small>Filtro</small>
          <strong>{current.label}</strong>
        </span>
        <Icon name="chevron" size={12} />
      </summary>
      <div className="filter-dropdown-menu" role="listbox">
        {WORKSPACE_FILTER_OPTIONS.map((opt) => (
          <button
            key={opt.id}
            type="button"
            role="option"
            aria-selected={opt.id === props.value}
            className={`filter-dropdown-item ${opt.id === props.value ? 'is-active' : ''}`}
            onClick={(event) => {
              event.preventDefault();
              props.onChange(opt.id);
              // Cierra el <details> tras seleccionar.
              const host = (event.currentTarget.closest('details') as HTMLDetailsElement | null);
              if (host) host.open = false;
            }}
          >
            <Icon name={opt.icon} size={14} />
            <span>{opt.label}</span>
            {opt.id === props.value && <Icon name="check" size={13} />}
          </button>
        ))}
      </div>
    </details>
  );
}

// Botón con menú desplegable genérico para acciones agrupadas. El
// padre define las acciones y los iconos; este componente solo
// renderiza el <details> + <summary> + lista. Se usa para el selector
// de workspace (cambiar/sincronizar/persistir) y se puede reusar para
// cualquier otro selector con el mismo patrón visual.
function WorkspaceMenuButton(props: {
  icon: IconName;
  label: string;
  title?: string;
  actions: { id: string; label: string; icon: IconName; onClick: () => void }[];
}) {
  return (
    <details className="workspace-menu-button" role="menu">
      <summary className="toolbar-button" aria-haspopup="menu" title={props.title || props.label}>
        <Icon name={props.icon} size={15} />
        <span className="workspace-menu-button-label">
          <small>Workspace</small>
          <strong>{props.label}</strong>
        </span>
        <Icon name="chevron" size={12} />
      </summary>
      <div className="workspace-menu-button-menu" role="menu">
        {props.actions.map((action) => (
          <button
            key={action.id}
            type="button"
            role="menuitem"
            className="workspace-menu-button-item"
            onClick={(event) => {
              event.preventDefault();
              action.onClick();
              const host = (event.currentTarget.closest('details') as HTMLDetailsElement | null);
              if (host) host.open = false;
            }}
          >
            <Icon name={action.icon} size={14} />
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </details>
  );
}

// Menú ⋯ de la toolbar. Mantiene centralizadas las acciones secundarias
// del workspace para que la barra principal no se sature.
function WorkspaceActionsMenu(props: {
  allExpanded: boolean;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  onReread: () => void;
  onOpenSources: () => void;
  onCopyWorkspacePath: () => void;
  onOpenProjectStatus: () => void;
  onOpenProjectAnalyze: () => void;
}) {
  const close = (event: ReactMouseEvent<HTMLButtonElement>) => {
    const host = (event.currentTarget.closest('details') as HTMLDetailsElement | null);
    if (host) host.open = false;
  };
  return (
    <details className="workspace-actions-menu" role="menu">
      <summary className="toolbar-button icon-only" aria-haspopup="menu" title="Más acciones del workspace">
        <Icon name="more" size={15} />
        <span className="visually-hidden">Más acciones</span>
      </summary>
      <div className="workspace-actions-menu-popover" role="menu">
        <div className="workspace-actions-menu-section">
          <span className="workspace-actions-menu-title">Explorador</span>
          <button type="button" role="menuitem" onClick={(event) => { close(event); props.onExpandAll(); }} disabled={props.allExpanded}>
            <Icon name="expand" size={14} /> Expandir todo
          </button>
          <button type="button" role="menuitem" onClick={(event) => { close(event); props.onCollapseAll(); }} disabled={!props.allExpanded}>
            <Icon name="close" size={14} /> Contraer todo
          </button>
          <button type="button" role="menuitem" onClick={(event) => { close(event); props.onReread(); }}>
            <Icon name="refresh" size={14} /> Releer árbol
          </button>
        </div>
        <div className="workspace-actions-menu-section">
          <span className="workspace-actions-menu-title">Fuentes</span>
          <button type="button" role="menuitem" onClick={(event) => { close(event); props.onOpenSources(); }}>
            <Icon name="folder" size={14} /> Gestionar fuentes
          </button>
        </div>
        <div className="workspace-actions-menu-section">
          <span className="workspace-actions-menu-title">Workspace</span>
          <button type="button" role="menuitem" onClick={(event) => { close(event); props.onCopyWorkspacePath(); }}>
            <Icon name="copy" size={14} /> Copiar ruta del workspace
          </button>
          <button type="button" role="menuitem" onClick={(event) => { close(event); props.onOpenProjectStatus(); }}>
            <Icon name="inspector" size={14} /> Estado del proyecto
          </button>
          <button type="button" role="menuitem" onClick={(event) => { close(event); props.onOpenProjectAnalyze(); }}>
            <Icon name="sparkle" size={14} /> Analizar proyecto
          </button>
        </div>
      </div>
    </details>
  );
}

// Avisador compacto: solo aparece si la readiness tiene un problema
// accionable. Si todo está OK, el componente no se renderiza y la
// superficie queda en silencio (no hay barra de 67%).
function WorkspaceReadinessAlert(props: {
  tone: 'ok' | 'warn' | 'error';
  issues: { kind: 'warn' | 'error'; title: string; detail: string; action?: { label: string; onClick: () => void } }[];
}) {
  if (props.tone === 'ok') return null;
  const iconName: IconName = props.tone === 'error' ? 'warning' : 'warning';
  return (
    <div className={`workspace-readiness-alert tone-${props.tone}`} role="status">
      <span className="workspace-readiness-alert-icon">
        <Icon name={iconName} size={14} />
      </span>
      <div className="workspace-readiness-alert-body">
        {props.issues.map((issue, idx) => (
          <div key={`${issue.title}-${idx}`} className="workspace-readiness-alert-row">
            <strong>{issue.title}</strong>
            <span>{issue.detail}</span>
            {issue.action && (
              <button type="button" className="text-button" onClick={issue.action.onClick}>
                {issue.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// Drawer de fuentes: lista activa + form de alta + acciones por fuente.
// Solo se monta cuando el padre lo solicita (sourcesDrawerOpen).
function SourcesDrawer(props: {
  sourceRoots: BackendFileSourceRoot[];
  sourcePath: string;
  sourceLabel: string;
  sourceBusy: boolean;
  sourceMessage: string;
  canManage: boolean;
  onClose: () => void;
  onPathChange: (value: string) => void;
  onLabelChange: (value: string) => void;
  onAdd: (path: string, label: string) => void;
  onRemove: (key: string) => void;
  onCopyPath: (path: string) => void;
}) {
  return (
    <section id="workspace-sources-drawer" className="workspace-sources-drawer" role="region" aria-label="Fuentes del workspace">
      <header className="workspace-sources-drawer-head">
        <div>
          <strong>Fuentes</strong>
          <span>{props.sourceRoots.length} activas</span>
        </div>
        <button type="button" className="icon-button" onClick={props.onClose} title="Cerrar drawer de fuentes" aria-label="Cerrar drawer de fuentes">
          <Icon name="close" size={14} />
        </button>
      </header>
      <div className="workspace-sources-drawer-list">
        {props.sourceRoots.length ? (
          props.sourceRoots.map((root) => {
            const key = String(root.key || root.path || '');
            const label = String(root.label || root.key || root.path || 'Fuente');
            const path = String(root.path || '');
            const isWorkspace = key === 'workspace';
            return (
              <article key={key} className={`workspace-sources-drawer-item ${isWorkspace ? 'is-workspace' : ''}`}>
                <header>
                  <span className="workspace-sources-drawer-item-name">
                    <Icon name={isWorkspace ? 'workspace' : 'folder'} size={14} />
                    <strong>{label}</strong>
                    {isWorkspace && <span className="workspace-sources-drawer-pill">activo</span>}
                  </span>
                  <div className="workspace-sources-drawer-item-actions">
                    <button type="button" className="text-button" onClick={() => props.onCopyPath(path)} title="Copiar ruta">
                      <Icon name="copy" size={12} /> Copiar
                    </button>
                    {!isWorkspace && props.canManage && (
                      <button type="button" className="text-button" onClick={() => props.onRemove(key)} disabled={props.sourceBusy} title="Quitar fuente">
                        <Icon name="close" size={12} /> Quitar
                      </button>
                    )}
                  </div>
                </header>
                <code title={path}>{shortenPath(path, 90)}</code>
              </article>
            );
          })
        ) : (
          <div className="empty-state compact">
            <Icon name="folder" size={18} />
            <p>No hay fuentes extra registradas.</p>
          </div>
        )}
      </div>
      {props.canManage && (
        <form
          className="workspace-sources-drawer-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (props.sourcePath.trim()) props.onAdd(props.sourcePath, props.sourceLabel);
          }}
        >
          <label>
            <span>Ruta</span>
            <input
              value={props.sourcePath}
              onChange={(event) => props.onPathChange(event.target.value)}
              placeholder="Ruta absoluta o relativa de la fuente"
            />
          </label>
          <label>
            <span>Etiqueta</span>
            <input
              value={props.sourceLabel}
              onChange={(event) => props.onLabelChange(event.target.value)}
              placeholder="Etiqueta opcional"
            />
          </label>
          <button type="submit" className="primary-button compact" disabled={props.sourceBusy || !props.sourcePath.trim()}>
            <Icon name="plus" size={13} /> Añadir fuente
          </button>
        </form>
      )}
      {props.sourceMessage && <p className="workspace-sources-drawer-message">{props.sourceMessage}</p>}
    </section>
  );
}
