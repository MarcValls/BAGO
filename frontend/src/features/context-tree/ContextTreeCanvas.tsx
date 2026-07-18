// Canvas del árbol. Muestra los nodos en una jerarquía compacta con
// drag & drop entre padres, soporte para teclado, selección múltiple
// y menú contextual (vía ⋯ en cada nodo y click derecho).
import { useMemo, useState } from 'react';
import type { ContextNode, ContextNodeStatus, ContextNodeType } from './contextTreeTypes';
import { Icon, type IconName } from '@/shared/Icon';
import { shortenPath } from './utils';

interface Props {
  treeRootId: string | null;
  nodes: Record<string, ContextNode>;
  selectedNodeId: string | null;
  packNodeIds: string[];
  onSelectNode: (nodeId: string) => void;
  onToggleExpand: (nodeId: string) => void;
  expanded: Set<string>;
  onMoveNode: (nodeId: string, newParentId: string) => void;
  onExcludeNode: (nodeId: string) => void;
  onRestoreNode: (nodeId: string) => void;
  onToggleCanon: (nodeId: string) => void;
  onAddChild: (parentId: string) => void;
  onToggleInPack?: (nodeId: string) => void;
  onOpenInWorkspace?: (path: string) => void;
  onCopyId: (id: string) => void;
}

function statusClass(status: ContextNodeStatus): string {
  return `is-${status}`;
}

function typeIcon(type: ContextNodeType): IconName {
  switch (type) {
    case 'root': return 'tree';
    case 'intent': return 'intent';
    case 'source': return 'folder';
    case 'file': return 'file';
    case 'decision': return 'decision';
    case 'rule': return 'rule';
    case 'claim': return 'claim';
    case 'risk': return 'risk';
    case 'pending': return 'stale';
    case 'evidence': return 'evidence';
    case 'proposal': return 'proposed';
    case 'pack': return 'pack';
    case 'note': return 'node';
    default: return 'node';
  }
}

function statusLabel(status: ContextNodeStatus): string {
  switch (status) {
    case 'active': return 'ACTIVO';
    case 'proposed': return 'PROPUESTO';
    case 'excluded': return 'EXCLUIDO';
    case 'archived': return 'ARCHIVADO';
    case 'canon': return 'CANON';
    case 'conflict': return 'CONFLICTO';
    case 'stale': return 'STALE';
    default: return '';
  }
}

interface NodeRowProps {
  node: ContextNode;
  depth: number;
  selected: boolean;
  inPack: boolean;
  expanded: boolean;
  hasChildren: boolean;
  childCount?: number;
  childConflicts?: number;
  childStale?: number;
  onSelect: (id: string) => void;
  onToggle: (id: string) => void;
  onMove: (id: string, newParentId: string) => void;
  onExclude: (id: string) => void;
  onRestore: (id: string) => void;
  onCanon: (id: string) => void;
  onAddChild: (id: string) => void;
  onToggleInPack?: (id: string) => void;
  onCopyId: (id: string) => void;
  onOpenInWorkspace?: (path: string) => void;
  children?: React.ReactNode;
}

function NodeRow(props: NodeRowProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const isCanon = props.node.status === 'canon';
  const isRoot = props.node.type === 'root';
  const isExcluded = props.node.status === 'excluded' || props.node.status === 'archived';

  const filePath = props.node.sourceRefs.find((ref) => ref.kind === 'workspace_file')?.path;

  return (
    <div
      className={`context-tree-row ${statusClass(props.node.status)} ${props.selected ? 'is-selected' : ''} ${props.inPack ? 'is-in-pack' : ''} ${dragOver ? 'is-drop-target' : ''} ${isExcluded ? 'is-faded' : ''}`}
      draggable={!isRoot}
      onDragStart={(event) => {
        if (isRoot) {
          event.preventDefault();
          return;
        }
        event.dataTransfer.setData('text/x-context-node', props.node.id);
        event.dataTransfer.effectAllowed = 'move';
      }}
      onDragOver={(event) => {
        if (isRoot) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setDragOver(false);
        const sourceId = event.dataTransfer.getData('text/x-context-node');
        if (sourceId && sourceId !== props.node.id) {
          props.onMove(sourceId, props.node.id);
        }
      }}
    >
      <div
        className="context-tree-row-head"
        style={{ paddingLeft: 8 + props.depth * 14 }}
        onClick={() => props.onSelect(props.node.id)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            props.onSelect(props.node.id);
          }
          if (event.key === 'Delete' || event.key === 'Backspace') {
            event.preventDefault();
            if (props.node.status === 'excluded' || props.node.status === 'archived') {
              props.onRestore(props.node.id);
            } else if (!isRoot && !isCanon) {
              props.onExclude(props.node.id);
            }
          }
        }}
        tabIndex={0}
        role="treeitem"
        aria-selected={props.selected}
        aria-expanded={props.hasChildren ? props.expanded : undefined}
      >
        <button
          type="button"
          className="context-tree-row-toggle"
          onClick={(event) => { event.stopPropagation(); if (props.hasChildren) props.onToggle(props.node.id); }}
          title={props.expanded ? 'Contraer' : 'Expandir'}
          aria-label={props.expanded ? 'Contraer rama' : 'Expandir rama'}
        >
          {props.hasChildren ? (
            <Icon name="chevron" size={12} style={{ transform: props.expanded ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform .12s' }} />
          ) : (
            <span className="context-tree-row-dot" />
          )}
        </button>
        <span className="context-tree-row-icon"><Icon name={typeIcon(props.node.type)} size={12} /></span>
        <span className="context-tree-row-title">{props.node.title}</span>
        {props.hasChildren && (
          <span className="context-tree-row-count">
            {props.childCount ?? 0}
            {(props.childConflicts ?? 0) > 0 && <em className="is-warn"> · {props.childConflicts} conflicto{(props.childConflicts ?? 0) > 1 ? 's' : ''}</em>}
            {(props.childStale ?? 0) > 0 && <em className="is-warn"> · {props.childStale} stale</em>}
          </span>
        )}
        {!props.hasChildren && typeof props.node.weightTokens === 'number' && (
          <span className="context-tree-row-weight" title="Tokens estimados">{props.node.weightTokens}t</span>
        )}
        {props.inPack && (
          <span className="context-tree-row-inpack" title="En el pack">
            <Icon name="pack" size={10} />
          </span>
        )}
        {isCanon && (
          <span className="context-tree-row-canon" title="Canónica">
            <Icon name="canon" size={10} />
          </span>
        )}
        {props.node.status !== 'active' && props.node.status !== 'proposed' && (
          <span className={`context-tree-row-state ${statusClass(props.node.status)}`}>{statusLabel(props.node.status)}</span>
        )}
        {props.node.conflictNodeIds.length > 0 && (
          <span className="context-tree-row-conflict" title={`${props.node.conflictNodeIds.length} conflictos`}>
            <Icon name="conflict" size={10} />
          </span>
        )}
        {filePath && (
          <span className="context-tree-row-path" title={filePath}>{shortenPath(filePath, 40)}</span>
        )}
        <button
          type="button"
          className="icon-button context-tree-row-actions"
          onClick={(event) => { event.stopPropagation(); setMenuOpen((v) => !v); }}
          title="Acciones"
          aria-label="Acciones del nodo"
        >
          <Icon name="more" size={12} />
        </button>
      </div>
      {menuOpen && (
        <div className="context-tree-row-menu" role="menu">
          <button type="button" onClick={() => { props.onSelect(props.node.id); setMenuOpen(false); }}>
            <Icon name="inspector" size={11} /> Inspeccionar
          </button>
          {!isRoot && !isCanon && (
            <button type="button" onClick={() => { props.onCanon(props.node.id); setMenuOpen(false); }}>
              <Icon name="canon" size={11} /> {props.node.status === 'canon' ? 'Quitar CANON' : 'Marcar como CANON'}
            </button>
          )}
          {isCanon && (
            <button type="button" onClick={() => { setMenuOpen(false); props.onSelect(props.node.id); }}>
              <Icon name="lock" size={11} /> Abrir en inspector para revisión
            </button>
          )}
          {!isRoot && !isCanon && props.node.status !== 'excluded' && (
            <button type="button" onClick={() => { props.onExclude(props.node.id); setMenuOpen(false); }}>
              <Icon name="close" size={11} /> Excluir del contexto
            </button>
          )}
          {!isRoot && (props.node.status === 'excluded' || props.node.status === 'archived') && (
            <button type="button" onClick={() => { props.onRestore(props.node.id); setMenuOpen(false); }}>
              <Icon name="refresh" size={11} /> Restaurar
            </button>
          )}
          {props.inPack && (
            <button type="button" onClick={() => { props.onToggleInPack?.(props.node.id); setMenuOpen(false); }}>
              <Icon name="close" size={11} /> Quitar del pack
            </button>
          )}
          {!isRoot && !props.inPack && (
            <button type="button" onClick={() => { props.onToggleInPack?.(props.node.id); setMenuOpen(false); }}>
              <Icon name="pack" size={11} /> Añadir al pack activo
            </button>
          )}
          {!isRoot && (
            <button type="button" onClick={() => { props.onAddChild(props.node.id); setMenuOpen(false); }}>
              <Icon name="plus" size={11} /> Añadir hijo
            </button>
          )}
          {filePath && props.onOpenInWorkspace && (
            <button type="button" onClick={() => { props.onOpenInWorkspace?.(filePath); setMenuOpen(false); }}>
              <Icon name="workspace" size={11} /> Abrir en workspace
            </button>
          )}
          <button type="button" onClick={() => { props.onCopyId(props.node.id); setMenuOpen(false); }}>
            <Icon name="copy" size={11} /> Copiar ID
          </button>
        </div>
      )}
      {props.children && <ul className="context-tree-list context-tree-children">{props.children}</ul>}
    </div>
  );
}

export function ContextTreeCanvas(props: Props) {
  const { nodes, treeRootId } = props;
  const childrenByParent = useMemo(() => {
    const map = new Map<string, ContextNode[]>();
    if (!treeRootId) return map;
    for (const node of Object.values(nodes)) {
      const list = map.get(node.parentId || '') || [];
      list.push(node);
      map.set(node.parentId || '', list);
    }
    for (const list of map.values()) {
      list.sort((a, b) => {
        if (a.type === 'root') return -1;
        if (b.type === 'root') return 1;
        return a.title.localeCompare(b.title, 'es');
      });
    }
    return map;
  }, [nodes, treeRootId]);

  const renderNode = (nodeId: string, depth: number): JSX.Element | null => {
    const node = nodes[nodeId];
    if (!node) return null;
    const children = childrenByParent.get(nodeId) || [];
    const isExpanded = props.expanded.has(nodeId);
    // CANON: las ramas muestran un resumen de hijos para que el
    // usuario sepa qué hay sin tener que expandir.
    let childConflicts = 0;
    let childStale = 0;
    for (const child of children) {
      if (child.conflictNodeIds.length > 0) childConflicts += 1;
      if (child.status === 'stale') childStale += 1;
    }
    return (
      <NodeRow
        key={nodeId}
        node={node}
        depth={depth}
        selected={props.selectedNodeId === nodeId}
        inPack={props.packNodeIds.includes(nodeId)}
        expanded={isExpanded}
        hasChildren={children.length > 0}
        childCount={children.length}
        childConflicts={childConflicts}
        childStale={childStale}
        onSelect={props.onSelectNode}
        onToggle={props.onToggleExpand}
        onMove={props.onMoveNode}
        onExclude={props.onExcludeNode}
        onRestore={props.onRestoreNode}
        onCanon={props.onToggleCanon}
        onAddChild={props.onAddChild}
        onToggleInPack={props.onToggleInPack}
        onCopyId={props.onCopyId}
        onOpenInWorkspace={props.onOpenInWorkspace}
      >
        {isExpanded && children.map((child) => renderNode(child.id, depth + 1))}
      </NodeRow>
    );
  };

  if (!treeRootId || !nodes[treeRootId]) {
    return (
      <div className="context-tree-canvas empty">
        <div className="context-tree-empty">
          <Icon name="tree" size={28} />
          <h3>No hay árbol de contexto</h3>
          <p>Empieza creando un árbol para empezar a arquitecturar el contexto del workspace.</p>
        </div>
      </div>
    );
  }
  return (
    <div className="context-tree-canvas" role="tree">
      <ul className="context-tree-list">
        <li className="context-tree-list-root">
          {renderNode(treeRootId, 0)}
        </li>
      </ul>
    </div>
  );
}
