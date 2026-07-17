import type { ContextPack, ContextNode, ContextTree, ContextBankItem, ContextBankSnapshot, ContextPatchRequest, ContextReceipt, SourceDirectory } from './contextTreeTypes';
import { ContextBank } from './ContextBank';
import { ContextTreeCanvas } from './ContextTreeCanvas';
import { ContextPackBar } from './ContextPackBar';
import { ContextActivityTray } from './ContextActivityTray';
import { FlowStageScreen } from '@/lib/flow-shell/FlowStageScreen';
import { Icon } from '@/shared/Icon';

export interface ContextStageSourcesProps {
  bank: ContextBankSnapshot;
  loading: boolean;
  treeNodes: ContextNode[];
  onOpenRelatedNode: (nodeId: string) => void;
  sourceDirectories: SourceDirectory[];
  sourceDirectoriesLoading: boolean;
  onReloadBank: () => void;
  onAddToTree: (item: ContextBankItem) => void;
  onAddToPack: (item: ContextBankItem) => void;
  onAddManualItem?: (path: string, kind: 'source_root' | 'workspace_file' | 'workspace_directory') => Promise<void>;
  onRemoveManualItem?: (itemId: string) => Promise<void>;
  onAddSourceDirectory?: (path: string) => Promise<void>;
  onRemoveSourceDirectory?: (id: string) => Promise<void>;
  onRefreshSourceDirectoryFiles?: (id: string) => Promise<void>;
  onToggleSourceFileInclude?: (id: string, filePath: string, include: boolean) => Promise<void>;
  onSetSourceFileBranch?: (id: string, filePath: string, branch: ContextNode['type']) => Promise<void>;
  onLinkSourceDirectoryToTree?: (id: string) => Promise<void>;
}

export function ContextStageSources(props: ContextStageSourcesProps) {
  return (
    <FlowStageScreen
      title={<><Icon name="folder" size={14} /> Fuentes</>}
      subtitle="Vincula directorios y selecciona piezas del contexto raíz."
    >
      <ContextBank
        bank={props.bank}
        loading={props.loading}
        tree={props.treeNodes}
        onAddToTree={props.onAddToTree}
        onOpenRelatedNode={props.onOpenRelatedNode}
        onReload={props.onReloadBank}
        onAddToActivePack={props.onAddToPack}
        onAddManualItem={props.onAddManualItem}
        onRemoveManualItem={props.onRemoveManualItem}
        sourceDirectories={props.sourceDirectories}
        sourceDirectoriesLoading={props.sourceDirectoriesLoading}
        onAddSourceDirectory={props.onAddSourceDirectory}
        onRemoveSourceDirectory={props.onRemoveSourceDirectory}
        onRefreshSourceDirectoryFiles={props.onRefreshSourceDirectoryFiles}
        onToggleSourceFileInclude={props.onToggleSourceFileInclude}
        onSetSourceFileBranch={props.onSetSourceFileBranch}
        onLinkSourceDirectoryToTree={props.onLinkSourceDirectoryToTree}
      />
    </FlowStageScreen>
  );
}

export interface ContextStageStructureProps {
  tree: ContextTree;
  selectedNodeId: string | null;
  expanded: Set<string>;
  packNodeIds: string[];
  hasSelectedNode: boolean;
  onSelectNode: (nodeId: string) => void;
  onToggleExpand: (nodeId: string) => void;
  onMoveNode: (nodeId: string, newParentId: string) => void;
  onExcludeNode: (nodeId: string) => void;
  onRestoreNode: (nodeId: string) => void;
  onToggleCanon: (nodeId: string) => void;
  onAddChild: (nodeId: string) => void;
  onToggleInPack: (nodeId: string) => void;
  onOpenInWorkspace?: (path: string) => void;
  onCopyId: (id: string) => void;
  onOpenInspectorDrawer: () => void;
  onContinueToPack: () => void;
  canContinueToPack: boolean;
}

export function ContextStageStructure(props: ContextStageStructureProps) {
  return (
    <FlowStageScreen
      title={<><Icon name="tree" size={14} /> Estructura</>}
      subtitle="Organiza el árbol contextual y selecciona el nodo a inspeccionar."
      className="context-flow-structure"
    >
      <div className="context-tree-panel">
        <ContextTreeCanvas
          treeRootId={props.tree.rootId}
          nodes={props.tree.nodes}
          selectedNodeId={props.selectedNodeId}
          packNodeIds={props.packNodeIds}
          onSelectNode={props.onSelectNode}
          onToggleExpand={props.onToggleExpand}
          expanded={props.expanded}
          onMoveNode={props.onMoveNode}
          onExcludeNode={props.onExcludeNode}
          onRestoreNode={props.onRestoreNode}
          onToggleCanon={props.onToggleCanon}
          onAddChild={props.onAddChild}
          onToggleInPack={props.onToggleInPack}
          onOpenInWorkspace={props.onOpenInWorkspace}
          onCopyId={props.onCopyId}
        />
      </div>
      <div className="context-flow-actions">
        <button
          type="button"
          className="secondary-button compact"
          onClick={props.onOpenInspectorDrawer}
          disabled={!props.hasSelectedNode}
        >
          <Icon name="inspector" size={12} /> Abrir inspector temporal
        </button>
        <button
          type="button"
          className="primary-button compact"
          onClick={props.onContinueToPack}
          disabled={!props.canContinueToPack}
        >
          <Icon name="pack" size={12} /> Revisar pack
        </button>
      </div>
    </FlowStageScreen>
  );
}

export interface ContextStagePackProps {
  pack: ContextPack | null;
  packBlockedReason: string | null;
  packNodes: ContextNode[];
  selectableNodes: ContextNode[];
  onToggleNodeInPack: (nodeId: string) => void;
  onCompile: () => void;
  onSendToChat: () => void;
  onSendToPipeline: () => void;
  onShowCompiled: () => void;
  onCopyPack: () => void;
}

export function ContextStagePack(props: ContextStagePackProps) {
  return (
    <FlowStageScreen
      title={<><Icon name="pack" size={14} /> Pack</>}
      subtitle="Revisa y ajusta qué nodos entran al contexto final."
      className="context-flow-pack"
    >
      <ContextPackBar
        pack={props.pack}
        blockedReason={props.packBlockedReason}
        onCompile={props.onCompile}
        onSendToChat={props.onSendToChat}
        onSendToPipeline={props.onSendToPipeline}
        onShowCompiled={props.onShowCompiled}
        onCopyPack={props.onCopyPack}
      />
      <section className="context-pack-review-list">
        <h4>Incluidos ({props.packNodes.length})</h4>
        {props.packNodes.length === 0 && <p className="context-pack-review-empty">Todavía no hay piezas seleccionadas en el pack.</p>}
        {props.packNodes.map((node) => (
          <article key={node.id} className="context-pack-review-item">
            <div>
              <strong>{node.title}</strong>
              <small>{node.type} · {node.status}</small>
            </div>
            <button type="button" className="text-button" onClick={() => props.onToggleNodeInPack(node.id)}>
              <Icon name="close" size={11} /> Quitar
            </button>
          </article>
        ))}
      </section>
      <section className="context-pack-review-list">
        <h4>Disponibles ({props.selectableNodes.length - props.packNodes.length})</h4>
        {props.selectableNodes.filter((node) => !props.packNodes.some((inPack) => inPack.id === node.id)).slice(0, 40).map((node) => (
          <article key={node.id} className="context-pack-review-item">
            <div>
              <strong>{node.title}</strong>
              <small>{node.type} · {node.status}</small>
            </div>
            <button type="button" className="text-button" onClick={() => props.onToggleNodeInPack(node.id)}>
              <Icon name="plus" size={11} /> Añadir
            </button>
          </article>
        ))}
      </section>
    </FlowStageScreen>
  );
}

export interface ContextStageCompileProps {
  pack: ContextPack | null;
  proposals: ContextPatchRequest[];
  receipts: ContextReceipt[];
  compiledMarkdown?: string | null;
  onAcceptPatch: (patchId: string) => void;
  onRejectPatch: (patchId: string) => void;
  onRevertPatch: (patchId: string) => void;
  onEditPatch: (patchId: string) => void;
  onOpenRelated: (nodeId: string) => void;
  onClear: () => void;
  onCompile: () => void;
}

export function ContextStageCompile(props: ContextStageCompileProps) {
  return (
    <FlowStageScreen
      title={<><Icon name="refresh" size={14} /> Compilación</>}
      subtitle="Compila el pack y resuelve conflictos antes del destino."
      className="context-flow-compile"
    >
      <div className="context-flow-actions">
        <button type="button" className="primary-button compact" onClick={props.onCompile} disabled={!props.pack?.nodeIds.length}>
          <Icon name="refresh" size={12} /> Compilar ahora
        </button>
      </div>
      {props.compiledMarkdown && (
        <pre className="context-compiled-markdown">{props.compiledMarkdown.slice(0, 4000)}</pre>
      )}
      <ContextActivityTray
        proposals={props.proposals}
        receipts={props.receipts || []}
        defaultOpen={props.proposals.some((p) => p.status === 'pending')}
        onAcceptPatch={props.onAcceptPatch}
        onRejectPatch={props.onRejectPatch}
        onRevertPatch={props.onRevertPatch}
        onEditPatch={props.onEditPatch}
        onOpenRelated={props.onOpenRelated}
        onClear={props.onClear}
      />
    </FlowStageScreen>
  );
}

export interface ContextStageDestinationProps {
  pack: ContextPack | null;
  packBlockedReason: string | null;
  onCompile: () => void;
  onSendToChat: () => void;
  onSendToPipeline: () => void;
  onShowCompiled: () => void;
  onCopyPack: () => void;
}

export function ContextStageDestination(props: ContextStageDestinationProps) {
  return (
    <FlowStageScreen
      title={<><Icon name="send" size={14} /> Destino</>}
      subtitle="Envía el contexto compilado al módulo de trabajo final."
      className="context-flow-destination"
    >
      <ContextPackBar
        pack={props.pack}
        blockedReason={props.packBlockedReason}
        onCompile={props.onCompile}
        onSendToChat={props.onSendToChat}
        onSendToPipeline={props.onSendToPipeline}
        onShowCompiled={props.onShowCompiled}
        onCopyPack={props.onCopyPack}
      />
      <div className="context-flow-actions">
        <button type="button" className="primary-button" disabled={!props.pack?.markdown} onClick={props.onSendToChat}>
          <Icon name="chat" size={13} /> Abrir Chat con contexto
        </button>
        <button type="button" className="secondary-button" disabled={!props.pack?.markdown} onClick={props.onSendToPipeline}>
          <Icon name="pipeline" size={13} /> Abrir Pipeline con contexto
        </button>
      </div>
    </FlowStageScreen>
  );
}
