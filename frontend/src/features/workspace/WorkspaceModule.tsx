// src/features/workspace/WorkspaceModule.tsx
// Punto de entrada del editor de Workspace. Orquesta toolbar,
// explorador, tabs, editor, inspector y panel inferior.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { MouseEvent } from 'react';
import type { BagoClient } from '@/api/client';
import type { ActiveSection, ContextTargetKind, InspectorLevel, SelectionRecord, UiBootstrapSnapshot } from '@/contracts/backend';
import type { UseContextTreeState } from '@/features/context-tree/useContextTree';
import type { ContextBankItem } from '@/features/context-tree/contextTreeTypes';
import { useResizable } from '@/lib/useResizable';
import { ResizableHandle } from '@/lib/ResizableHandle';
import { Modal } from '@/lib/Modal';
import { Drawer } from '@/lib/Drawer';
import type {
  SelectedRange,
  WorkspaceDiagnostic,
  WorkspacePattern
} from './workspaceTypes';
import { useWorkspaceEditor } from './useWorkspaceEditor';
import { WorkspaceToolbar } from './WorkspaceToolbar';
import { FileExplorer } from './FileExplorer';
import { EditorTabs } from './EditorTabs';
import { CodeEditorPane } from './CodeEditorPane';
import { WorkspaceInspector } from './WorkspaceInspector';
import { ProblemsPanel } from './ProblemsPanel';
import { PatternsPanel } from './PatternsPanel';
import { ChangesPanel } from './ChangesPanel';
import { OutputPanel } from './OutputPanel';
import { Icon, type IconName } from '@/shared/Icon';

interface Props {
  client: BagoClient;
  snapshot: UiBootstrapSnapshot | null;
  contextTree: UseContextTreeState;
  apiBase: string;
  apiToken: string;
  initialOpenPath?: string | null;
  onInspect: (selection: SelectionRecord, hint?: InspectorLevel | { x: number; y: number }) => void;
  onNavigate: (section: ActiveSection) => void;
  onSendChat: (message: string) => void;
  onCreatePlan: (title: string, summary: string) => Promise<void> | void;
  onRunCommand: (command: string) => Promise<void>;
  onChooseWorkspace: () => void;
}

export function WorkspaceModule(props: Props) {
  const editor = useWorkspaceEditor({
    client: props.client,
    workspaceRoot: props.snapshot?.workspace.root || '',
    initialPath: props.initialOpenPath || null,
    contextTreeNodes: props.contextTree.tree ? Object.values(props.contextTree.tree.nodes) : []
  });
  const [ignoredDiagnosticIds, setIgnoredDiagnosticIds] = useState<Set<string>>(new Set());
  const [fileContextMenu, setFileContextMenu] = useState<{ path: string; x: number; y: number } | null>(null);
  const [directoryContextMenu, setDirectoryContextMenu] = useState<{ path: string; x: number; y: number } | null>(null);
  const [editorContextMenu, setEditorContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [diffModal, setDiffModal] = useState<{ path: string; baseline: string; current: string } | null>(null);
  // CANON[WS-013]: panel inferior redimensionable verticalmente.
  // Splitter vertical entre el cuerpo del editor (explorer + center + inspector)
  // y el panel inferior (problemas/cambios/patrones/salida). El hook maneja
  // la persistencia en localStorage y el cálculo del alto.
  const bottomResizable = useResizable({
    id: 'workspace-bottom',
    panels: ['body', 'bottom'],
    defaultSizes: [70, 30],
    minSizes: [240, 80],
    direction: 'vertical'
  });
  // Modal separado del editor principal (abre en una ventana propia).
  const [editingPath, setEditingPath] = useState<string | null>(null);
  const [githubRepo, setGithubRepo] = useState('');
  const [githubState, setGithubState] = useState<Record<string, unknown> | null>(null);
  const [githubMessage, setGithubMessage] = useState('');
  const editorRef = useRef<HTMLDivElement | null>(null);

  const hasDirty = editor.tabs.some((tab) => tab.state === 'dirty');
  const isSaving = editor.tabs.some((tab) => tab.state === 'saving');
  const workspaceLabel = props.snapshot?.workspace.id || (props.snapshot?.workspace.root?.split(/[\\/]/).filter(Boolean).pop() || 'Workspace');
  const workspaceTitle = props.snapshot?.workspace.root || 'Sin ruta';
  const connectedRepo = typeof githubState?.repo === 'string' ? githubState.repo : '';

  const refreshGitHub = useCallback(async () => {
    try {
      const result = await props.client.getGitHubStatus();
      setGithubState(result);
      if (typeof result.repo === 'string') setGithubRepo(result.repo);
      setGithubMessage('');
    } catch (error) {
      setGithubMessage(error instanceof Error ? error.message : 'No se pudo consultar GitHub');
    }
  }, [props.client]);

  useEffect(() => { void refreshGitHub(); }, [refreshGitHub]);

  const connectGitHub = async () => {
    try {
      const result = await props.client.connectGitHubRepository(githubRepo);
      setGithubState(result);
      setGithubMessage(`Repositorio conectado: ${String(result.repo || githubRepo)}`);
    } catch (error) {
      setGithubMessage(error instanceof Error ? error.message : 'No se pudo conectar el repositorio');
    }
  };

  const createGitHub = async () => {
    const name = window.prompt('Nombre del nuevo repositorio GitHub');
    if (!name) return;
    if (!window.confirm(`Crear ${name} en GitHub como repositorio privado?`)) return;
    try {
      const result = await props.client.createGitHubRepository(name, { private: true });
      setGithubMessage(`Repositorio creado: ${String(result.url || name)}`);
    } catch (error) {
      setGithubMessage(error instanceof Error ? error.message : 'No se pudo crear el repositorio');
    }
  };

  // Atajo de teclado: Ctrl+S ya está capturado en CodeEditorPane.
  // Ctrl+F: focus al buscador. Ctrl+Shift+P: problems. Etc.
  useEffect(() => {
    const handler = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === '/') {
        event.preventDefault();
        const input = document.querySelector<HTMLInputElement>('.workspace-toolbar-search input');
        input?.focus();
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'j') {
        event.preventDefault();
        editor.setBottomPanel(editor.bottomPanel === 'problems' ? null : 'problems');
      } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'p') {
        event.preventDefault();
        editor.setBottomPanel(editor.bottomPanel === 'patterns' ? null : 'patterns');
      } else if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'o') {
        event.preventDefault();
        editor.setBottomPanel(editor.bottomPanel === 'output' ? null : 'output');
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [editor]);

  // Asegurar que el panel inferior aparece automáticamente si hay errores
  // o patrones graves.
  useEffect(() => {
    const hasError = editor.tabs.some((tab) => tab.diagnostics.some((d) => d.severity === 'error'));
    if (hasError && !editor.bottomPanel) {
      editor.setBottomPanel('problems');
    }
  }, [editor.tabs, editor.bottomPanel, editor]);

  const handleJump = useCallback((path: string, line: number) => {
    if (editor.activePath !== path) {
      void editor.openFile(path);
    }
    setTimeout(() => {
      const target = document.querySelector(`.code-editor-textarea`);
      if (target instanceof HTMLTextAreaElement) {
        const lines = target.value.split(/\r?\n/);
        let pos = 0;
        for (let i = 0; i < line - 1 && i < lines.length; i++) {
          pos += lines[i].length + 1;
        }
        target.focus();
        target.setSelectionRange(pos, Math.min(target.value.length, pos + (lines[line - 1]?.length || 0)));
      }
    }, 80);
  }, [editor]);

  const handleSendSelectionToChat = useCallback(() => {
    if (!editor.activeTab) return;
    const tab = editor.activeTab;
    const range = editor.selectedRange;
    const message = formatWorkspaceMessage(tab, range);
    void props.onSendChat(message);
  }, [editor.activeTab, editor.selectedRange, props]);

  const handleAddFileToContext = useCallback((path: string, title?: string) => {
    const node = createWorkspaceFileNode(path, title);
    void props.contextTree.addBankItemToTree(node);
  }, [props.contextTree]);

  const handleAddSelectionToContext = useCallback(() => {
    if (!editor.activeTab || !editor.selectedRange) return;
    const tab = editor.activeTab;
    const range = editor.selectedRange;
    const node = createSelectionNode(tab, range);
    void props.contextTree.addBankItemToTree(node);
  }, [editor.activeTab, editor.selectedRange, props.contextTree]);

  const handleCreatePlanFromDiagnostic = useCallback(async (diagnostic: WorkspaceDiagnostic) => {
    const tab = editor.tabs.find((t) => t.diagnostics.includes(diagnostic));
    if (!tab) return;
    await props.onCreatePlan(
      `Corregir ${diagnostic.severity} en ${tab.label}:${diagnostic.startLine}`,
      `El editor detectó un ${diagnostic.severity} (${diagnostic.source || diagnostic.origin}) en ${tab.path}:${diagnostic.startLine}.${diagnostic.startColumn}\n\nMensaje: ${diagnostic.message}`
    );
  }, [editor.tabs, props]);

  const handleCreatePlanFromPattern = useCallback(async (tab: typeof editor.tabs[number], pattern: WorkspacePattern) => {
    await props.onCreatePlan(
      `Resolver patrón ${pattern.kind} en ${tab.label}:${pattern.startLine}`,
      `Patrón: ${pattern.title}\nCategoría: ${pattern.category}\nDetalle: ${pattern.detail}\nSugerencia: ${pattern.suggestion || '—'}\nUbicación: ${tab.path}:${pattern.startLine}`
    );
  }, [editor.tabs, props]);

  const handleAddDiagnosticAsRisk = useCallback((diagnostic: WorkspaceDiagnostic) => {
    const tab = editor.tabs.find((t) => t.diagnostics.includes(diagnostic));
    if (!tab) return;
    const node = createRiskNodeFromDiagnostic(tab, diagnostic);
    void props.contextTree.addBankItemToTree(node);
  }, [editor.tabs, props.contextTree]);

  const handleAddPatternAsPending = useCallback((tab: typeof editor.tabs[number], pattern: WorkspacePattern) => {
    const node = createPendingNodeFromPattern(tab, pattern);
    void props.contextTree.addBankItemToTree(node);
  }, [props.contextTree]);

  const handleAddPatternAsRule = useCallback((tab: typeof editor.tabs[number], pattern: WorkspacePattern) => {
    const node = createRuleNodeFromPattern(tab, pattern);
    void props.contextTree.addBankItemToTree(node);
  }, [props.contextTree]);

  const handleAddPatternAsRisk = useCallback((tab: typeof editor.tabs[number], pattern: WorkspacePattern) => {
    const node = createRiskNodeFromPattern(tab, pattern);
    void props.contextTree.addBankItemToTree(node);
  }, [props.contextTree]);

  const handleSendDiagnosticToChat = useCallback((diagnostic: WorkspaceDiagnostic) => {
    const tab = editor.tabs.find((t) => t.diagnostics.includes(diagnostic));
    if (!tab) return;
    const message = formatDiagnosticMessage(tab, diagnostic);
    void props.onSendChat(message);
  }, [editor.tabs, props]);

  const handleSendPatternToChat = useCallback((tab: typeof editor.tabs[number], pattern: WorkspacePattern) => {
    const message = formatPatternMessage(tab, pattern);
    void props.onSendChat(message);
  }, [props]);

  const handleViewDiff = useCallback((path: string) => {
    const tab = editor.tabs.find((t) => t.path === path);
    if (!tab) return;
    setDiffModal({ path: tab.path, baseline: tab.baseline, current: tab.content });
  }, [editor.tabs]);

  const onFileContextMenu = useCallback((event: MouseEvent<HTMLElement>, path: string) => {
    event.preventDefault();
    setDirectoryContextMenu(null);
    setEditorContextMenu(null);
    setFileContextMenu({ path, x: event.clientX, y: event.clientY });
  }, []);

  const onDirectoryContextMenu = useCallback((event: MouseEvent<HTMLElement>, path: string) => {
    event.preventDefault();
    setFileContextMenu(null);
    setEditorContextMenu(null);
    setDirectoryContextMenu({ path, x: event.clientX, y: event.clientY });
  }, []);

  const onEditorContextMenu = useCallback((event: MouseEvent<HTMLDivElement>, range: SelectedRange | null) => {
    event.preventDefault();
    setFileContextMenu(null);
    setDirectoryContextMenu(null);
    setEditorContextMenu({ x: event.clientX, y: event.clientY });
  }, []);

  const allDirectoryPaths = useMemo(() => {
    const paths: string[] = [];
    const visit = (nodes: typeof editor.explorer) => {
      for (const n of nodes) {
        if (n.kind === 'directory') {
          paths.push(n.path);
          visit(n.children);
        }
      }
    };
    visit(editor.explorer);
    return paths;
  }, [editor.explorer]);

  const closeContextMenus = useCallback(() => {
    setFileContextMenu(null);
    setDirectoryContextMenu(null);
    setEditorContextMenu(null);
  }, []);

  useEffect(() => {
    const handler = () => closeContextMenus();
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, [closeContextMenus]);

  // Al entrar en la pantalla, abrimos el panel inferior si hay algo.
  useEffect(() => {
    if (editor.tabs.length > 0 && !editor.bottomPanel) {
      const errors = editor.tabs.flatMap((t) => t.diagnostics).filter((d) => d.severity === 'error').length;
      const patterns = editor.tabs.flatMap((t) => t.patterns).length;
      if (errors > 0) editor.setBottomPanel('problems');
      else if (patterns > 0) editor.setBottomPanel('patterns');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editor.tabs.length]);

  const onInspectorDiagnostic = editor.tabs.flatMap((t) => t.diagnostics).find((d) => d.id === editor.inspector.refId) || null;
  const onInspectorPattern = editor.tabs.flatMap((t) => t.patterns).find((p) => p.id === editor.inspector.refId) || null;

  return (
    <div className="workspace-editor" onClick={closeContextMenus}>
      <WorkspaceToolbar
        query={editor.query}
        onQueryChange={editor.setQuery}
        filter={editor.filter}
        onFilterChange={editor.setFilter}
        workspaceLabel={workspaceLabel}
        workspaceTitle={workspaceTitle}
        onChooseWorkspace={props.onChooseWorkspace}
        onRunCommand={(cmd) => props.onRunCommand(cmd)}
        onPersist={() => props.onRunCommand('/workspace persist')}
        onSync={() => props.onRunCommand('/workspace sync')}
        onCopyPath={() => navigator.clipboard?.writeText(workspaceTitle)}
        onOpenExternal={() => props.onInspect(buildWorkspaceStatusSelection('open-external', workspaceTitle), 'detail')}
        onStatus={() => props.onInspect(buildWorkspaceStatusSelection('status', workspaceTitle), 'detail')}
        hasDirty={hasDirty}
        isSaving={isSaving}
        onSave={() => editor.activePath && void editor.saveTab(editor.activePath)}
        onSaveAll={() => void editor.saveAll()}
        onExpandAll={() => allDirectoryPaths.forEach((p) => { if (!editor.expandedDirectories.includes(p)) editor.toggleDirectory(p); })}
        onCollapseAll={() => allDirectoryPaths.forEach((p) => { if (editor.expandedDirectories.includes(p)) editor.toggleDirectory(p); })}
        onReread={() => void editor.refreshExplorer()}
        onToggleBottom={(panel) => editor.setBottomPanel(editor.bottomPanel === panel ? null : panel)}
      />

      <section className="workspace-github-card" aria-label="Conexión con GitHub">
        <div><strong>GitHub</strong><span>{githubState?.authenticated === true ? 'Autenticado' : 'No autenticado'}</span>{connectedRepo ? <small> · {connectedRepo}</small> : null}</div>
        <div className="workspace-github-actions">
          <input aria-label="Repositorio GitHub" value={githubRepo} onChange={(event) => setGithubRepo(event.target.value)} placeholder="owner/repo" />
          <button type="button" className="secondary-button compact" onClick={() => void connectGitHub()} disabled={!githubRepo.trim()}>Conectar y leer</button>
          <button type="button" className="secondary-button compact" onClick={() => void createGitHub()} disabled={githubState?.authenticated !== true}>Crear repositorio</button>
          <button type="button" className="text-button" onClick={() => void refreshGitHub()}>Actualizar</button>
        </div>
        {githubMessage && <small className="workspace-github-message" role="status">{githubMessage}</small>}
      </section>

      <div className="workspace-editor-split" ref={bottomResizable.containerRef}>
      <div className="workspace-editor-body" style={bottomResizable.getPanelStyle('body')}>
        <div className="workspace-editor-grid">
        <aside className="workspace-editor-explorer">
          <header className="workspace-panel-head">
            <strong>Explorador</strong>
            <span className="workspace-panel-head-meta">{editor.explorer.length} raíces · {allDirectoryPaths.length} carpetas</span>
          </header>
          <FileExplorer
            explorer={editor.explorer}
            expanded={editor.expandedDirectories}
            activePath={editor.activePath}
            tabs={editor.tabs}
            query={editor.query}
            filter={editor.filter}
            loading={editor.loadingExplorer}
            onToggle={editor.toggleDirectory}
            onOpen={(path) => void editor.openFile(path)}
            onContextMenuFile={onFileContextMenu}
            onContextMenuDirectory={onDirectoryContextMenu}
          />
        </aside>

        <section className="workspace-editor-center">
          <EditorTabs
            tabs={editor.tabs}
            activePath={editor.activePath}
            onSelect={editor.setActive}
            onClose={editor.closeTab}
          />
          <div className="workspace-editor-pane" ref={editorRef}>
            {editor.activeTab ? (
              <CodeEditorPane
                tab={editor.activeTab}
                selectedRange={editor.selectedRange}
                onChange={(content) => editor.setContent(editor.activeTab!.path, content)}
                onSelect={editor.setSelectedRange}
                onRunCommand={(cmd) => props.onRunCommand(cmd)}
                onRequestSave={() => editor.activePath && void editor.saveTab(editor.activePath)}
                onRequestDiagnostic={(diag) => editor.setInspector({ kind: 'diagnostic', refId: diag.id })}
                onRequestPattern={(pat) => editor.setInspector({ kind: 'pattern', refId: pat.id })}
                onContextMenu={onEditorContextMenu}
              />
            ) : (
              <div className="workspace-editor-empty">
                <Icon name="file" size={28} />
                <h3>Sin archivo seleccionado</h3>
                <p>Selecciona un archivo del explorador o usa Ctrl+/ para buscar.</p>
                {!props.snapshot?.workspace.root && (
                  <button type="button" onClick={props.onChooseWorkspace} className="workspace-empty-action">
                    <Icon name="folder" size={12} /> Elegir workspace
                  </button>
                )}
              </div>
            )}
          </div>
        </section>

        {editor.inspectorOpen && (
          <WorkspaceInspector
            tab={editor.activeTab}
            inspector={editor.inspector}
            diagnostic={onInspectorDiagnostic}
            pattern={onInspectorPattern}
            onClose={() => { editor.setInspectorOpen(false); editor.setInspector({ kind: null }); }}
            onSendToChat={() => {
              if (editor.inspector.kind === 'diagnostic' && onInspectorDiagnostic) handleSendDiagnosticToChat(onInspectorDiagnostic);
              else if (editor.inspector.kind === 'pattern' && editor.activeTab && onInspectorPattern) handleSendPatternToChat(editor.activeTab, onInspectorPattern);
              else handleSendSelectionToChat();
            }}
            onAddToContext={() => {
              if (editor.inspector.kind === 'diagnostic' && onInspectorDiagnostic) handleAddDiagnosticAsRisk(onInspectorDiagnostic);
              else if (editor.inspector.kind === 'pattern' && editor.activeTab && onInspectorPattern) handleAddPatternAsRisk(editor.activeTab, onInspectorPattern);
              else if (editor.activeTab) handleAddFileToContext(editor.activeTab.path, editor.activeTab.label);
            }}
            onCreatePlan={() => {
              if (editor.inspector.kind === 'diagnostic' && onInspectorDiagnostic) void handleCreatePlanFromDiagnostic(onInspectorDiagnostic);
              else if (editor.inspector.kind === 'pattern' && editor.activeTab && onInspectorPattern) void handleCreatePlanFromPattern(editor.activeTab, onInspectorPattern);
            }}
            onCopyPath={() => editor.activeTab && navigator.clipboard?.writeText(editor.activeTab.path)}
            onViewEvidence={() => editor.activeTab && props.onInspect(buildEvidenceSelection(editor.activeTab), 'detail')}
            onJump={(line) => editor.activePath && handleJump(editor.activePath, line)}
          />
        )}
      </div>

      </div>
      <ResizableHandle onMouseDown={() => bottomResizable.startResize(0)} />
      <div
        className={`workspace-bottom-wrap ${editor.bottomPanel ? 'is-open' : 'is-collapsed'}`}
        style={bottomResizable.getPanelStyle('bottom')}
      >
        <div className={`workspace-bottom-panel ${editor.bottomPanel ? 'is-open' : 'is-collapsed'}`}>
        <nav className="workspace-bottom-tabs" role="tablist">
          {(['problems', 'changes', 'patterns', 'output'] as const).map((panel) => {
            const counts: Record<typeof panel, number> = {
              problems: editor.tabs.flatMap((t) => t.diagnostics).filter((d) => !ignoredDiagnosticIds.has(d.id)).length,
              changes: editor.tabs.filter((t) => t.state === 'dirty' || t.state === 'save_error').length,
              patterns: editor.tabs.flatMap((t) => t.patterns).length,
              output: editor.output.length
            };
            const labels: Record<typeof panel, string> = {
              problems: 'Problemas',
              changes: 'Cambios',
              patterns: 'Patrones',
              output: 'Salida'
            };
            const isActive = editor.bottomPanel === panel;
            return (
              <button
                key={panel}
                type="button"
                role="tab"
                aria-selected={isActive}
                className={`workspace-bottom-tab ${isActive ? 'is-active' : ''}`}
                onClick={() => editor.setBottomPanel(isActive ? null : panel)}
              >
                {labels[panel]}
                {counts[panel] > 0 && <span className="workspace-bottom-tab-count">{counts[panel]}</span>}
              </button>
            );
          })}
        </nav>
        <div className="workspace-bottom-content" role="tabpanel">
          {editor.bottomPanel === 'problems' && (
            <ProblemsPanel
              tabs={editor.tabs}
              ignoredIds={ignoredDiagnosticIds}
              onJump={handleJump}
              onOpenInContext={handleAddDiagnosticAsRisk}
              onSendToChat={handleSendDiagnosticToChat}
              onCreatePlan={handleCreatePlanFromDiagnostic}
              onIgnore={(id) => setIgnoredDiagnosticIds((current) => new Set([...current, id]))}
            />
          )}
          {editor.bottomPanel === 'changes' && (
            <ChangesPanel
              tabs={editor.tabs}
              onSave={(path) => void editor.saveTab(path)}
              onRevert={editor.revertTab}
              onViewDiff={handleViewDiff}
              onSelect={editor.setActive}
            />
          )}
          {editor.bottomPanel === 'patterns' && (
            <PatternsPanel
              tabs={editor.tabs}
              onJump={handleJump}
              onSendToChat={handleSendPatternToChat}
              onAddAsRisk={handleAddPatternAsRisk}
              onAddAsPending={handleAddPatternAsPending}
              onAddAsRule={handleAddPatternAsRule}
              onCreatePlan={handleCreatePlanFromPattern}
            />
          )}
          {editor.bottomPanel === 'output' && (
            <OutputPanel entries={editor.output} onClear={editor.clearOutput} />
          )}
        </div>
        </div>
      </div>
      </div>

      {fileContextMenu && (
        <ContextMenu
          x={fileContextMenu.x}
          y={fileContextMenu.y}
          items={fileMenuItems(fileContextMenu.path, {
            onOpen: () => void editor.openFile(fileContextMenu.path),
            onCopyPath: () => navigator.clipboard?.writeText(fileContextMenu.path),
            onCopyContent: () => {
              const tab = editor.tabs.find((t) => t.path === fileContextMenu.path);
              if (tab) {
                navigator.clipboard?.writeText(tab.content || '');
                return;
              }
              void editor.openFile(fileContextMenu.path).then(() => {
                const t = editor.tabs.find((x) => x.path === fileContextMenu.path);
                if (t) navigator.clipboard?.writeText(t.content || '');
              });
            },
            onAddToContext: () => handleAddFileToContext(fileContextMenu.path, fileContextMenu.path.split(/[\\/]/).pop()),
            onSendToChat: () => {
              const tab = editor.tabs.find((t) => t.path === fileContextMenu.path);
              if (tab) {
                void props.onSendChat(formatWorkspaceMessage(tab, null));
              } else {
                void editor.openFile(fileContextMenu.path).then(() => {
                  const t = editor.tabs.find((x) => x.path === fileContextMenu.path);
                  if (t) void props.onSendChat(formatWorkspaceMessage(t, null));
                });
              }
            },
            onCreatePlan: () => {
              const tab = editor.tabs.find((t) => t.path === fileContextMenu.path);
              if (tab) {
                const firstDiag = tab.diagnostics[0];
                if (firstDiag) {
                  void handleCreatePlanFromDiagnostic(firstDiag);
                  return;
                }
                const firstPattern = tab.patterns[0];
                if (firstPattern) {
                  void handleCreatePlanFromPattern(tab, firstPattern);
                  return;
                }
              }
              void props.onCreatePlan(
                `Revisar ${fileContextMenu.path.split(/[\\/]/).pop() || fileContextMenu.path}`,
                `Tarea creada desde el menú contextual de archivo en ${fileContextMenu.path}. El archivo no tiene diagnósticos ni patrones pendientes; abrir y revisar manualmente.`
              );
            },
            onViewProblems: () => editor.setBottomPanel('problems'),
            onViewEvidence: () => props.onInspect(buildEvidenceSelectionFromPath(fileContextMenu.path), 'detail'),
            onRevert: () => editor.revertTab(fileContextMenu.path),
            onSave: () => void editor.saveTab(fileContextMenu.path)
          })}
        />
      )}

      {directoryContextMenu && (
        <ContextMenu
          x={directoryContextMenu.x}
          y={directoryContextMenu.y}
          items={directoryMenuItems(directoryContextMenu.path, {
            onExpand: () => editor.toggleDirectory(directoryContextMenu.path),
            onCollapse: () => editor.toggleDirectory(directoryContextMenu.path),
            onCopyPath: () => navigator.clipboard?.writeText(directoryContextMenu.path),
            onAddToContext: () => handleAddFileToContext(directoryContextMenu.path, directoryContextMenu.path.split(/[\\/]/).pop()),
            onSendToChat: () => {
              const message = `Resumen de la carpeta ${directoryContextMenu.path} solicitado desde Workspace.`;
              void props.onSendChat(message);
            },
            onCreatePlan: () => props.onCreatePlan(`Revisar ${directoryContextMenu.path}`, `Tarea generada desde menú contextual de carpeta en ${directoryContextMenu.path}`),
            onReread: () => void editor.refreshExplorer()
          })}
        />
      )}

      {editorContextMenu && editor.activeTab && (
        <ContextMenu
          x={editorContextMenu.x}
          y={editorContextMenu.y}
          items={selectionMenuItems({
            tab: editor.activeTab,
            range: editor.selectedRange,
            onSendToChat: handleSendSelectionToChat,
            onAskExplain: () => {
              if (!editor.activeTab || !editor.selectedRange) return;
              const tab = editor.activeTab;
              const range = editor.selectedRange;
              const message = `Explica esta selección de ${tab.label} (líneas ${range.startLine}-${range.endLine}).\n\n${formatWorkspaceMessage(tab, range)}`;
              void props.onSendChat(message);
            },
            onAskRefactor: () => {
              if (!editor.activeTab || !editor.selectedRange) return;
              const tab = editor.activeTab;
              const range = editor.selectedRange;
              const message = `Refactoriza esta selección de ${tab.label} (líneas ${range.startLine}-${range.endLine}).\n\n${formatWorkspaceMessage(tab, range)}`;
              void props.onSendChat(message);
            },
            onAddAsContextRule: () => {
              if (!editor.activeTab || !editor.selectedRange) return;
              const node = createSelectionRuleNode(editor.activeTab, editor.selectedRange);
              void props.contextTree.addBankItemToTree(node);
            },
            onAddAsClaim: () => {
              if (!editor.activeTab || !editor.selectedRange) return;
              const node = createSelectionClaimNode(editor.activeTab, editor.selectedRange);
              void props.contextTree.addBankItemToTree(node);
            },
            onAddToContext: handleAddSelectionToContext,
            onCreatePlan: () => {
              if (!editor.activeTab || !editor.selectedRange) return;
              props.onCreatePlan(
                `Refactor en ${editor.activeTab.label}:${editor.selectedRange.startLine}-${editor.selectedRange.endLine}`,
                `Tarea generada desde selección en ${editor.activeTab.path}:${editor.selectedRange.startLine}-${editor.selectedRange.endLine}\n\nSelección:\n${editor.selectedRange.text}`
              );
            }
          })}
        />
      )}

      <Modal
        open={diffModal !== null}
        onClose={() => setDiffModal(null)}
        title={diffModal ? `Diff: ${diffModal.path}` : ''}
        subtitle={diffModal ? `Cambios entre la versión guardada y el contenido en memoria.` : ''}
        width={920}
        height="70vh"
        footer={diffModal && (
          <button type="button" className="primary-button" onClick={() => setDiffModal(null)}>
            Cerrar
          </button>
        )}
      >
        {diffModal && <DiffView baseline={diffModal.baseline} current={diffModal.current} />}
      </Modal>
    </div>
  );
}

interface Item { label: string; onClick: () => void; icon?: IconName; disabled?: boolean; }
function ContextMenu(p: { x: number; y: number; items: Item[] }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number }>({ left: p.x, top: p.y });
  useEffect(() => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const left = p.x + rect.width > vw - 8 ? Math.max(8, vw - rect.width - 8) : p.x;
    const top = p.y + rect.height > vh - 8 ? Math.max(8, vh - rect.height - 8) : p.y;
    setPos({ left, top });
  }, [p.x, p.y, p.items.length]);
  return (
    <div
      ref={ref}
      className="workspace-context-menu"
      style={{ left: pos.left, top: pos.top }}
      onClick={(e) => e.stopPropagation()}
      role="menu"
    >
      {p.items.map((item, idx) => (
        <button
          key={idx}
          type="button"
          role="menuitem"
          disabled={item.disabled}
          onClick={() => { if (!item.disabled) item.onClick(); }}
        >
          {item.icon && <Icon name={item.icon} size={12} />}
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  );
}

function fileMenuItems(_path: string, h: {
  onOpen: () => void;
  onCopyPath: () => void;
  onCopyContent: () => void;
  onAddToContext: () => void;
  onSendToChat: () => void;
  onCreatePlan: () => void;
  onViewProblems: () => void;
  onViewEvidence: () => void;
  onRevert: () => void;
  onSave: () => void;
}): Item[] {
  return [
    { label: 'Abrir', onClick: h.onOpen },
    { label: 'Copiar ruta', onClick: h.onCopyPath, icon: 'copy' },
    { label: 'Copiar contenido', onClick: h.onCopyContent, icon: 'copy' },
    { label: 'Enviar al Chat', onClick: h.onSendToChat, icon: 'send' },
    { label: 'Añadir al Árbol de Contexto', onClick: h.onAddToContext, icon: 'tree' },
    { label: 'Crear tarea en Pipeline', onClick: h.onCreatePlan, icon: 'pipeline' },
    { label: 'Ver problemas', onClick: h.onViewProblems, icon: 'alert' },
    { label: 'Ver evidencia', onClick: h.onViewEvidence, icon: 'evidence' },
    { label: 'Guardar', onClick: h.onSave, icon: 'check' },
    { label: 'Revertir cambios', onClick: h.onRevert, icon: 'refresh' }
  ];
}

function directoryMenuItems(_path: string, h: {
  onExpand: () => void;
  onCollapse: () => void;
  onCopyPath: () => void;
  onAddToContext: () => void;
  onSendToChat: () => void;
  onCreatePlan: () => void;
  onReread: () => void;
}): Item[] {
  return [
    { label: 'Expandir', onClick: h.onExpand, icon: 'expand' },
    { label: 'Contraer', onClick: h.onCollapse, icon: 'collapse' },
    { label: 'Copiar ruta', onClick: h.onCopyPath, icon: 'copy' },
    { label: 'Enviar al Chat', onClick: h.onSendToChat, icon: 'send' },
    { label: 'Añadir al Árbol de Contexto', onClick: h.onAddToContext, icon: 'tree' },
    { label: 'Crear tarea en Pipeline', onClick: h.onCreatePlan, icon: 'pipeline' },
    { label: 'Releer carpeta', onClick: h.onReread, icon: 'refresh' }
  ];
}

function selectionMenuItems(h: {
  tab: import('./workspaceTypes').OpenFileTab;
  range: SelectedRange | null;
  onSendToChat: () => void;
  onAskExplain: () => void;
  onAskRefactor: () => void;
  onAddAsContextRule: () => void;
  onAddAsClaim: () => void;
  onAddToContext: () => void;
  onCreatePlan: () => void;
}): Item[] {
  return [
    { label: 'Enviar selección al Chat', onClick: h.onSendToChat, icon: 'send' },
    { label: 'Pedir explicación', onClick: h.onAskExplain, icon: 'chat' },
    { label: 'Pedir refactor', onClick: h.onAskRefactor, icon: 'spark' },
    { label: 'Añadir al Árbol de Contexto', onClick: h.onAddToContext, icon: 'tree' },
    { label: 'Crear claim', onClick: h.onAddAsClaim, icon: 'claim' },
    { label: 'Crear regla', onClick: h.onAddAsContextRule, icon: 'rule' },
    { label: 'Crear tarea en Pipeline', onClick: h.onCreatePlan, icon: 'pipeline' }
  ];
}

function DiffView(p: { baseline: string; current: string }) {
  const lines = useMemo(() => {
    const baselineLines = p.baseline.split(/\r?\n/);
    const currentLines = p.current.split(/\r?\n/);
    const max = Math.max(baselineLines.length, currentLines.length);
    const result: Array<{ type: 'same' | 'add' | 'del' | 'mod'; baseLine?: string; curLine?: string; num: number }> = [];
    for (let i = 0; i < max; i++) {
      const b = baselineLines[i];
      const c = currentLines[i];
      if (b === c) result.push({ type: 'same', baseLine: b, curLine: c, num: i + 1 });
      else if (b === undefined) result.push({ type: 'add', curLine: c, num: i + 1 });
      else if (c === undefined) result.push({ type: 'del', baseLine: b, num: i + 1 });
      else result.push({ type: 'mod', baseLine: b, curLine: c, num: i + 1 });
    }
    return result;
  }, [p.baseline, p.current]);
  const sameCount = lines.filter(l => l.type === 'same').length;
  const addCount = lines.filter(l => l.type === 'add').length;
  const delCount = lines.filter(l => l.type === 'del').length;
  const modCount = lines.filter(l => l.type === 'mod').length;
  return (
    <div className="workspace-diff-view">
      <div className="workspace-diff-header">
        <span>#</span>
        <span>Antes ({delCount} borradas · {modCount} modificadas)</span>
        <span>Después ({addCount} añadidas · {modCount} modificadas · {sameCount} iguales)</span>
      </div>
      {lines.map((line, idx) => (
        <div key={idx} className={`workspace-diff-line diff-${line.type}`}>
          <span className="workspace-diff-num">{line.num}</span>
          {line.baseLine !== undefined && <span className="workspace-diff-cell base">- {line.baseLine}</span>}
          {line.curLine !== undefined && <span className="workspace-diff-cell current">+ {line.curLine}</span>}
        </div>
      ))}
    </div>
  );
}

// Helpers para crear nodos de contexto desde elementos del editor.
function createWorkspaceFileNode(path: string, title?: string): ContextBankItem {
  return {
    id: `ws-file-${Date.now()}`,
    kind: 'workspace_file',
    title: title || path.split(/[\\/]/).pop() || path,
    origin: 'workspace',
    path,
    suggestedBranch: 'file',
    raw: { path }
  };
}

function createRiskNodeFromDiagnostic(tab: import('./workspaceTypes').OpenFileTab, diagnostic: WorkspaceDiagnostic): ContextBankItem {
  return {
    id: `ws-risk-${Date.now()}`,
    kind: 'risk',
    title: `${diagnostic.severity} en ${tab.label}:${diagnostic.startLine}`,
    origin: 'workspace',
    path: tab.path,
    suggestedBranch: 'risk',
    raw: { diagnostic, path: tab.path }
  };
}

function createPendingNodeFromPattern(tab: import('./workspaceTypes').OpenFileTab, pattern: WorkspacePattern): ContextBankItem {
  return {
    id: `ws-pending-${Date.now()}`,
    kind: 'pending',
    title: pattern.title,
    origin: 'workspace',
    path: tab.path,
    suggestedBranch: 'pending',
    raw: { pattern, path: tab.path }
  };
}

function createRuleNodeFromPattern(tab: import('./workspaceTypes').OpenFileTab, pattern: WorkspacePattern): ContextBankItem {
  return {
    id: `ws-rule-${Date.now()}`,
    kind: 'rule',
    title: pattern.title,
    origin: 'workspace',
    path: tab.path,
    suggestedBranch: 'rule',
    raw: { pattern, path: tab.path, suggestion: pattern.suggestion }
  };
}

function createRiskNodeFromPattern(tab: import('./workspaceTypes').OpenFileTab, pattern: WorkspacePattern): ContextBankItem {
  return {
    id: `ws-risk-pattern-${Date.now()}`,
    kind: 'risk',
    title: pattern.title,
    origin: 'workspace',
    path: tab.path,
    suggestedBranch: 'risk',
    raw: { pattern, path: tab.path }
  };
}

function createSelectionNode(tab: import('./workspaceTypes').OpenFileTab, range: SelectedRange): ContextBankItem {
  return {
    id: `ws-selection-${Date.now()}`,
    kind: 'claim',
    title: `Selección en ${tab.label}:${range.startLine}-${range.endLine}`,
    origin: 'workspace',
    path: tab.path,
    suggestedBranch: 'claim',
    raw: { range, path: tab.path }
  };
}

function createSelectionClaimNode(tab: import('./workspaceTypes').OpenFileTab, range: SelectedRange): ContextBankItem {
  return {
    id: `ws-claim-${Date.now()}`,
    kind: 'claim',
    title: `Claim en ${tab.label}:${range.startLine}`,
    origin: 'workspace',
    path: tab.path,
    suggestedBranch: 'claim',
    raw: { range, path: tab.path }
  };
}

function createSelectionRuleNode(tab: import('./workspaceTypes').OpenFileTab, range: SelectedRange): ContextBankItem {
  return {
    id: `ws-rule-selection-${Date.now()}`,
    kind: 'rule',
    title: `Regla desde ${tab.label}:${range.startLine}`,
    origin: 'workspace',
    path: tab.path,
    suggestedBranch: 'rule',
    raw: { range, path: tab.path }
  };
}

// Helpers para construir selecciones que viajarán al Chat, Inspector, etc.
function buildWorkspaceSelectionSelection(tab: import('./workspaceTypes').OpenFileTab, range: SelectedRange | null): SelectionRecord {
  return {
    id: tab.path,
    kind: 'chat-message',
    targetKind: 'screen.workspace' as ContextTargetKind,
    title: tab.label,
    summary: range ? `Selección líneas ${range.startLine}-${range.endLine}` : `Archivo completo (${tab.content.length} chars)`,
    detail: [
      `path: ${tab.path}`,
      `language: ${tab.language}`,
      range ? `lines: ${range.startLine}-${range.endLine}` : 'lines: full',
      `workspace: ${tab.path.split(/[\\/]/).slice(0, -1).join('/')}`
    ],
    raw: range ? { path: tab.path, range, content: tab.content } : { path: tab.path, content: tab.content }
  };
}

function buildDiagnosticSelection(tab: import('./workspaceTypes').OpenFileTab, diagnostic: WorkspaceDiagnostic): SelectionRecord {
  return {
    id: `diag-${tab.path}-${diagnostic.id}`,
    kind: 'chat-message',
    targetKind: 'screen.workspace' as ContextTargetKind,
    title: `${diagnostic.severity} en ${tab.label}:${diagnostic.startLine}`,
    summary: diagnostic.message,
    detail: [
      `path: ${tab.path}`,
      `line: ${diagnostic.startLine}:${diagnostic.startColumn}`,
      `source: ${diagnostic.source || diagnostic.origin}`
    ],
    raw: { path: tab.path, diagnostic }
  };
}

function buildPatternSelection(tab: import('./workspaceTypes').OpenFileTab, pattern: WorkspacePattern): SelectionRecord {
  return {
    id: `pat-${tab.path}-${pattern.id}`,
    kind: 'chat-message',
    targetKind: 'screen.workspace' as ContextTargetKind,
    title: pattern.title,
    summary: pattern.detail,
    detail: [
      `path: ${tab.path}`,
      `line: ${pattern.startLine}`,
      `category: ${pattern.category}`,
      `severity: ${pattern.severity}`
    ],
    raw: { path: tab.path, pattern }
  };
}

function buildDirectorySelection(path: string): SelectionRecord {
  return {
    id: path,
    kind: 'chat-message',
    targetKind: 'screen.workspace' as ContextTargetKind,
    title: path.split(/[\\/]/).pop() || path,
    summary: `Carpeta ${path}`,
    detail: [`path: ${path}`, 'kind: directory'],
    raw: { path, kind: 'directory' }
  };
}

function buildWorkspaceStatusSelection(reason: string, root: string): SelectionRecord {
  return {
    id: `workspace-${reason}`,
    kind: 'workspace',
    targetKind: 'screen.workspace' as ContextTargetKind,
    title: reason,
    summary: root,
    detail: [`reason: ${reason}`, `root: ${root}`],
    raw: { reason, root }
  };
}

function buildEvidenceSelection(tab: import('./workspaceTypes').OpenFileTab): SelectionRecord {
  return {
    id: `evidence-${tab.path}`,
    kind: 'evidence',
    targetKind: 'screen.workspace' as ContextTargetKind,
    title: `Evidencia de ${tab.label}`,
    summary: `Evidencia asociada a ${tab.path}`,
    detail: [`path: ${tab.path}`],
    raw: { path: tab.path }
  };
}

function buildEvidenceSelectionFromPath(path: string): SelectionRecord {
  return {
    id: `evidence-${path}`,
    kind: 'evidence',
    targetKind: 'screen.workspace' as ContextTargetKind,
    title: `Evidencia de ${path.split(/[\\/]/).pop()}`,
    summary: `Evidencia asociada a ${path}`,
    detail: [`path: ${path}`],
    raw: { path }
  };
}

// Mensajes formateados para enviar al Chat. Usan el bloque
// <<BAGO:WORKSPACE_SELECTION>> para que el modelo y el módulo de
// contexto puedan parsear el contexto asociado.
function formatWorkspaceMessage(tab: import('./workspaceTypes').OpenFileTab, range: SelectedRange | null): string {
  const header = range
    ? `<<BAGO:WORKSPACE_SELECTION>>\npath: ${tab.path}\nlines: ${range.startLine}-${range.endLine}\nlanguage: ${tab.language}\n\n\`\`\`${tab.language}\n${range.text}\n\`\`\`\n<</BAGO:WORKSPACE_SELECTION>>\n\n`
    : `<<BAGO:WORKSPACE_FILE>>\npath: ${tab.path}\nlanguage: ${tab.language}\n<</BAGO:WORKSPACE_FILE>>\n\n`;
  const body = range
    ? `Refactoriza o explica la selección de ${tab.label} (líneas ${range.startLine}-${range.endLine}).`
    : `Revisa el archivo ${tab.label}.`;
  return header + body;
}

function formatDiagnosticMessage(tab: import('./workspaceTypes').OpenFileTab, diagnostic: WorkspaceDiagnostic): string {
  const header = `<<BAGO:WORKSPACE_DIAGNOSTIC>>\npath: ${tab.path}\nline: ${diagnostic.startLine}:${diagnostic.startColumn}\nseverity: ${diagnostic.severity}\nsource: ${diagnostic.source || diagnostic.origin}\nmessage: ${diagnostic.message}\n<</BAGO:WORKSPACE_DIAGNOSTIC>>\n\n`;
  return header + `El editor detectó un ${diagnostic.severity} en ${tab.label}:${diagnostic.startLine}. Sugiere una solución.`;
}

function formatPatternMessage(tab: import('./workspaceTypes').OpenFileTab, pattern: WorkspacePattern): string {
  const header = `<<BAGO:WORKSPACE_PATTERN>>\npath: ${tab.path}\nline: ${pattern.startLine}\ncategory: ${pattern.category}\nkind: ${pattern.kind}\nseverity: ${pattern.severity}\ntitle: ${pattern.title}\ndetail: ${pattern.detail}\n<</BAGO:WORKSPACE_PATTERN>>\n\n`;
  return header + `Patrón detectado (${pattern.severity}): ${pattern.title}. Sugerencia: ${pattern.suggestion || '—'}.`;
}
