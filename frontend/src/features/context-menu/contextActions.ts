import type { ActiveSection, BackendCommandResult, BackendRouterList, BackendRouterPolicy, ChatMode, ChatTurn, ContextTargetKind, OpeningDecision, SelectionRecord, UiBootstrapSnapshot } from '@/contracts/backend';
import type { ContextMenuAction } from '@/layout/ContextMenu';

type GlobalMode = 'normal' | 'focus' | 'review';

export interface ContextActionDeps {
  turns: ChatTurn[];
  snapshot: UiBootstrapSnapshot | null;
  opening: OpeningDecision;
  booting: boolean;
  routerState: { list: BackendRouterList | null; policy: BackendRouterPolicy | null };
  uiState: { drafts: Record<string, string>; chatMode: ChatMode; globalMode: GlobalMode };
  readSelectionPath: (selection: SelectionRecord) => string;
  useSelectionInChat: (selection: SelectionRecord) => void;
  openInspector: (selection: SelectionRecord, level?: 'summary' | 'detail' | 'raw') => void;
  openShell: (section: ActiveSection, mode?: GlobalMode) => void;
  openWorkspacePicker: () => void;
  openWorkspaceFileFromMenu: (path: string, kind?: 'file' | 'directory') => void;
  openSectionFromSelection: (selection: SelectionRecord) => void;
  navigate: (section: ActiveSection) => void;
  runCommand: (command: string) => Promise<BackendCommandResult | null>;
  runContextCommand: (command: string) => Promise<void>;
  bootstrap: () => Promise<unknown> | unknown;
  refreshAfterMutation: () => Promise<unknown>;
  refreshRouterState: () => Promise<void>;
  setRouterAutoSwitch: (enabled: boolean) => Promise<void>;
  setDraft: (key: string, text: string) => void;
  ensureChatPanel: () => void;
  writeClipboard: (label: string, value: string) => Promise<void>;
  setAndPersistUiState: (patch: Partial<{ commandPaletteOpen: boolean; chatMode: ChatMode }>) => void;
  confirm: (message: string) => boolean;
  // CANON[CTX-005]: acciones de Workspace → Árbol de Contexto. Permiten
  // crear un nodo de tipo file/source con un sourceRef, añadirlo al
  // pack activo o crear un claim a partir de un archivo.
  addWorkspacePathToContextTree?: (path: string, kind: 'file' | 'directory' | 'source') => Promise<void>;
  addSelectionAsContextRule?: (text: string) => Promise<void>;
  addWorkspacePathToContextPack?: (path: string) => Promise<void>;
  createContextClaimFromWorkspacePath?: (path: string) => Promise<void>;
}

function includesAny(value: string, needles: string[]): boolean {
  return needles.some((needle) => value.includes(needle));
}

export function classifyContextTarget(selection: SelectionRecord): ContextTargetKind {
  if (selection.targetKind) return selection.targetKind;
  const kind = selection.kind.toLowerCase();
  const id = String(selection.id || selection.title || '').toLowerCase();

  if (kind.includes('workspace-file')) return 'workspace.file';
  if (kind.includes('workspace-directory')) return 'workspace.directory';
  if (kind.includes('workspace-source')) return 'workspace.source';
  if (kind.includes('chat-turn') || kind.includes('screen-chat') || kind === 'chat') return 'screen.chat';
  if (kind.includes('home') || id.includes('home')) return 'screen.home';
  if (kind.includes('pipeline-step') || kind.includes('job') || kind.includes('code-task')) return 'pipeline.step';
  if (kind.includes('pipeline')) return 'pipeline.surface';
  if (includesAny(kind, ['evidence', 'receipt', 'history-message'])) return 'evidence.item';
  if (kind.includes('context')) return 'context.item';
  if (kind.includes('router')) return 'system.router';
  if (kind.includes('provider')) return 'system.provider';
  if (includesAny(kind, ['system', 'backend'])) return 'system.surface';
  if (kind.includes('graph') || kind.includes('node') || ['entrada', 'transformación', 'validación', 'salida'].includes(kind)) return 'graph.node';
  if (kind.startsWith('screen-') || kind.startsWith('module-')) return 'screen.other';
  return 'unknown';
}


function actionGroup(action: ContextMenuAction): string {
  if (['inspect-detail', 'use-in-chat', 'home-primary', 'open-workspace', 'open-pipeline', 'open-evidence', 'open-context', 'open-system', 'open-related'].includes(action.id)) return 'Principal';
  if (action.id.includes('context') || action.id.includes('certify') || action.id.includes('tune')) return 'Contexto';
  if (action.id.includes('chat') || action.id.includes('command') || action.id.includes('plan') || action.id.includes('project') || action.id.includes('audit') || action.id.includes('roadmap') || action.id.includes('task')) return 'Comandos';
  if (action.id.includes('router') || action.id.includes('provider') || action.id.includes('system') || action.id.includes('palette')) return 'Sistema';
  if (action.id.startsWith('copy-')) return 'Copiar / raw';
  return 'Acciones';
}

function grouped(actions: ContextMenuAction[]): ContextMenuAction[] {
  return actions.map((action) => ({ ...action, group: action.group || actionGroup(action) }));
}
export function createContextActions(selection: SelectionRecord, deps: ContextActionDeps): ContextMenuAction[] {
  const targetKind = classifyContextTarget(selection);
  const id = selection.id || selection.title;
  const path = deps.readSelectionPath(selection);
  const rawText = JSON.stringify(selection.raw ?? {}, null, 2) || '';
  const lastCommand = [...deps.turns].reverse().find((turn) => turn.role === 'command');
  const draftCommand = (command: string) => {
    deps.setDraft('chat', command);
    deps.ensureChatPanel();
  };
  const isWorkspaceTarget = targetKind.startsWith('workspace.');

  const actions: ContextMenuAction[] = [
    { id: 'inspect-detail', label: 'Ver detalle', icon: 'inspector', emphasis: 'primary', onClick: () => deps.openInspector(selection, 'detail') },
    { id: 'use-in-chat', label: 'Enviar al chat', icon: 'send', onClick: () => deps.useSelectionInChat(selection) }
  ];

  switch (targetKind) {
    case 'screen.home':
      actions.push(
        { id: 'home-primary', label: deps.opening.actionLabel || 'Ejecutar acción principal', icon: 'plus', onClick: () => deps.openShell(deps.opening.targetSection === 'home' && deps.snapshot?.permissions.canChat ? 'chat' : deps.opening.targetSection), disabled: deps.booting || (!deps.snapshot?.permissions.canChat && deps.opening.targetSection === 'chat') },
        { id: 'home-continue', label: 'Continuar última sesión', icon: 'history', onClick: () => { void deps.runCommand('/session').then(() => deps.openShell(deps.snapshot?.permissions.canChat ? 'chat' : 'home')); }, disabled: deps.booting || !deps.snapshot?.system.backendAvailable },
        { id: 'home-workspace', label: 'Elegir workspace', icon: 'folder', onClick: deps.openWorkspacePicker, disabled: deps.booting },
        { id: 'home-refresh', label: 'Refrescar estado', icon: 'refresh', onClick: () => void deps.bootstrap(), disabled: deps.booting }
      );
      break;

    case 'screen.chat':
      actions.push(
        { id: 'chat-command-prefix', label: 'Preparar comando /', icon: 'command', onClick: () => draftCommand((deps.uiState.drafts.chat || '').trim().startsWith('/') ? deps.uiState.drafts.chat : '/') },
        { id: 'chat-last-command', label: 'Pegar último comando', icon: 'history', onClick: () => lastCommand && draftCommand(lastCommand.text), disabled: !lastCommand },
        { id: 'chat-attach-context', label: 'Adjuntar contexto', icon: 'attach', onClick: () => void deps.runContextCommand('/context attach'), disabled: !deps.snapshot?.permissions.canInspectContext },
        { id: 'chat-plan', label: 'Preparar /plan', icon: 'pipeline', onClick: () => draftCommand('/plan ') },
        { id: 'chat-measure', label: 'Medir contexto', icon: 'context', onClick: () => void deps.runContextCommand('/context measure'), disabled: !deps.snapshot?.permissions.canInspectContext },
        { id: 'chat-project', label: 'Estado de proyecto', icon: 'workspace', onClick: () => void deps.runCommand('/project status') },
        { id: 'chat-audit', label: 'Auditoría ledger', icon: 'evidence', onClick: () => void deps.runCommand('/audit ledger') },
        { id: 'chat-live', label: 'Modo live', icon: 'live', onClick: () => deps.setAndPersistUiState({ chatMode: 'live' }), disabled: deps.uiState.chatMode === 'live', separatorBefore: true },
        { id: 'chat-trace', label: 'Modo trace', icon: 'trace', onClick: () => deps.setAndPersistUiState({ chatMode: 'trace' }), disabled: deps.uiState.chatMode === 'trace' },
        { id: 'chat-context', label: 'Abrir contexto', icon: 'context', onClick: () => deps.navigate('context') },
        { id: 'chat-evidence', label: 'Abrir evidencia', icon: 'evidence', onClick: () => deps.navigate('evidence') }
      );
      break;

    case 'workspace.file':
    case 'workspace.directory':
    case 'workspace.source': {
      const isDirectory = targetKind === 'workspace.directory';
      actions.push(
        { id: 'open-workspace', label: isDirectory ? 'Ir a carpeta' : 'Abrir en workspace', icon: isDirectory ? 'folder' : 'file', onClick: () => deps.openWorkspaceFileFromMenu(path, isDirectory ? 'directory' : 'file'), disabled: !path },
        { id: 'attach-context', label: isDirectory ? 'Adjuntar carpeta a contexto' : 'Adjuntar archivo a contexto', icon: 'attach', onClick: () => {
          if (isDirectory && !deps.confirm(`Adjuntar la carpeta al contexto puede incorporar muchos archivos.\n\n${path}\n\n¿Continuar?`)) return;
          void deps.runContextCommand(`/context attach ${path}`);
        }, disabled: !path || !deps.snapshot?.permissions.canInspectContext },
        { id: 'plan-from-file', label: 'Planificar sobre este elemento', icon: 'pipeline', onClick: () => draftCommand(`/plan Revisar ${path}`), disabled: !path },
        { id: 'open-evidence', label: 'Abrir Evidencia', icon: 'evidence', onClick: () => deps.navigate('evidence') }
      );
      // CANON[CTX-006]: integración Workspace → Árbol de Contexto.
      // Solo tiene sentido si la selección tiene una ruta real
      // (workspace.file y workspace.directory). Las fuentes raíces
      // también se pueden añadir como "source_root".
      if (path) {
        if (deps.addWorkspacePathToContextTree) {
          actions.push(
            { id: 'add-to-context-tree', label: 'Añadir al Árbol de Contexto', icon: 'tree', separatorBefore: true, onClick: () => void deps.addWorkspacePathToContextTree?.(path, targetKind === 'workspace.source' ? 'source' : isDirectory ? 'directory' : 'file') },
            { id: 'add-to-context-pack', label: 'Enviar al pack activo', icon: 'pack', onClick: () => void deps.addWorkspacePathToContextPack?.(path) }
          );
        }
        if (deps.createContextClaimFromWorkspacePath && !isDirectory) {
          actions.push({ id: 'create-claim-from-file', label: 'Crear Claim desde archivo', icon: 'claim', onClick: () => void deps.createContextClaimFromWorkspacePath?.(path) });
        }
        if (deps.addSelectionAsContextRule && !isDirectory) {
          actions.push({ id: 'add-as-rule', label: 'Crear regla desde selección', icon: 'rule', onClick: () => void deps.addSelectionAsContextRule?.(path) });
        }
      }
      break;
    }

    case 'pipeline.step':
    case 'pipeline.surface':
      actions.push(
        { id: 'open-pipeline', label: 'Abrir pipeline', icon: 'pipeline', onClick: () => deps.navigate('pipeline') },
        { id: 'roadmap', label: 'Ejecutar roadmap', icon: 'history', onClick: () => void deps.runCommand('/roadmap') },
        { id: 'open-evidence', label: 'Abrir evidencia', icon: 'evidence', onClick: () => deps.navigate('evidence') },
        { id: 'retry-task', label: 'Reintentar flujo', icon: 'retry', onClick: () => void deps.runCommand('/task retry'), disabled: !deps.snapshot?.permissions.canRetryPipeline },
        { id: 'stop-task', label: 'Detener flujo', icon: 'stop', emphasis: 'danger', onClick: () => {
          if (deps.confirm('Detener el flujo activo puede dejar pasos incompletos. ¿Continuar?')) void deps.runCommand('/task cancel');
        }, disabled: !deps.snapshot?.permissions.canStopPipeline }
      );
      break;

    case 'evidence.item':
      actions.push(
        { id: 'open-evidence', label: 'Abrir evidencia', icon: 'evidence', onClick: () => deps.navigate('evidence') },
        { id: 'open-context', label: 'Abrir contexto', icon: 'context', onClick: () => deps.navigate('context') },
        { id: 'certify-context', label: 'Certificar contexto', icon: 'check', onClick: () => void deps.runContextCommand('/context certify'), disabled: !deps.snapshot?.permissions.canInspectContext },
        { id: 'audit-ledger', label: 'Auditoría ledger', icon: 'command', onClick: () => void deps.runCommand('/audit ledger') }
      );
      break;

    case 'context.item':
      actions.push(
        { id: 'open-context', label: 'Abrir contexto', icon: 'context', onClick: () => deps.navigate('context') },
        { id: 'measure-context', label: 'Medir contexto', icon: 'refresh', onClick: () => void deps.runContextCommand('/context measure'), disabled: !deps.snapshot?.permissions.canInspectContext },
        { id: 'certify-context', label: 'Certificar contexto', icon: 'check', onClick: () => void deps.runContextCommand('/context certify'), disabled: !deps.snapshot?.permissions.canInspectContext },
        { id: 'tune-context', label: 'Proponer reducción', icon: 'filter', onClick: () => void deps.runContextCommand('/context tune'), disabled: !deps.snapshot?.permissions.canInspectContext },
        { id: 'attach-context', label: 'Adjuntar contexto', icon: 'attach', onClick: () => void deps.runContextCommand('/context attach'), disabled: !deps.snapshot?.permissions.canInspectContext }
      );
      break;

    case 'graph.node':
      actions.push(
        { id: 'open-related', label: 'Abrir sección relacionada', icon: 'chevron', onClick: () => deps.openSectionFromSelection(selection) },
        { id: 'open-graph', label: 'Abrir grafo', icon: 'graph', onClick: () => deps.navigate('graph') },
        { id: 'open-evidence', label: 'Abrir evidencia', icon: 'evidence', onClick: () => deps.navigate('evidence') },
        { id: 'open-context', label: 'Abrir contexto', icon: 'context', onClick: () => deps.navigate('context') }
      );
      break;

    case 'system.router':
    case 'system.provider':
    case 'system.surface':
      actions.push(
        { id: 'open-system', label: 'Abrir sistema', icon: 'system', onClick: () => deps.navigate('system') },
        { id: 'refresh-system', label: 'Refrescar estado', icon: 'refresh', onClick: () => void deps.refreshAfterMutation() },
        { id: 'refresh-router', label: 'Refrescar router', icon: 'model', onClick: () => void deps.refreshRouterState() },
        { id: 'toggle-auto-router', label: 'Alternar auto-router', icon: 'layout', onClick: () => {
          if (deps.confirm('Cambiar el auto-router afecta la selección de modelo de la sesión. ¿Continuar?')) void deps.setRouterAutoSwitch(!Boolean(deps.routerState.policy?.auto_switch ?? deps.routerState.list?.auto_switch));
        } },
        { id: 'open-palette', label: 'Abrir comandos', icon: 'command', onClick: () => deps.setAndPersistUiState({ commandPaletteOpen: true }) }
      );
      break;

    case 'screen.other':
    case 'unknown':
    default:
      actions.push({ id: 'open-related', label: 'Abrir sección relacionada', icon: 'chevron', onClick: () => deps.openSectionFromSelection(selection) });
      break;
  }

  actions.push(
    { id: 'copy-path', label: isWorkspaceTarget ? 'Copiar ruta' : 'Copiar ID', icon: 'copy', separatorBefore: true, onClick: () => void deps.writeClipboard(isWorkspaceTarget ? 'Ruta' : 'ID', path || id), disabled: !(path || id) },
    { id: 'copy-summary', label: 'Copiar resumen', icon: 'copy', onClick: () => void deps.writeClipboard('Resumen', selection.summary), disabled: !selection.summary.trim() },
    { id: 'copy-detail', label: 'Copiar detalles', icon: 'copy', onClick: () => void deps.writeClipboard('Detalles', selection.detail.join('\n')), disabled: !selection.detail.join('').trim() },
    { id: 'copy-raw', label: 'Copiar raw', icon: 'copy', onClick: () => void deps.writeClipboard('Raw', rawText), disabled: !rawText.trim() }
  );

  return grouped(actions);
}
