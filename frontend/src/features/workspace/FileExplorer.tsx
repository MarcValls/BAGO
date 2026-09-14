// src/features/workspace/FileExplorer.tsx
// Vista de árbol de archivos del workspace. Soporta búsqueda,
// expansión y selección, badges de estado.

import { useMemo } from 'react';
import type { MouseEvent } from 'react';
import type { ExplorerNode, OpenFileTab, WorkspaceFilter } from './workspaceTypes';
import { languageLabel } from './detectLanguage';
import { Icon } from '@/shared/Icon';
import { FileTypeIcon } from './FileTypeIcon';

interface Props {
  explorer: ExplorerNode[];
  expanded: string[];
  activePath: string | null;
  tabs: OpenFileTab[];
  query: string;
  filter: WorkspaceFilter;
  loading: boolean;
  onToggle: (path: string) => void;
  onOpen: (path: string) => void;
  onContextMenuFile: (event: MouseEvent<HTMLElement>, path: string) => void;
  onContextMenuDirectory: (event: MouseEvent<HTMLElement>, path: string) => void;
}

export function FileExplorer(props: Props) {
  const filtered = useMemo(() => filterTree(props.explorer, props.query, props.filter, props.tabs), [props.explorer, props.query, props.filter, props.tabs]);
  if (props.loading) {
    return <div className="workspace-explorer-empty">Cargando explorador…</div>;
  }
  if (!filtered.length) {
    return (
      <div className="workspace-explorer-empty">
        <Icon name="folder" size={22} />
        <h3>Sin coincidencias</h3>
        <p>No hay archivos que coincidan con el filtro o búsqueda.</p>
      </div>
    );
  }
  return (
    <div className="workspace-explorer-tree">
      {filtered.map((node) => (
        <TreeNode
          key={node.path}
          node={node}
          depth={0}
          expanded={props.expanded}
          activePath={props.activePath}
          tabs={props.tabs}
          onToggle={props.onToggle}
          onOpen={props.onOpen}
          onContextMenuFile={props.onContextMenuFile}
          onContextMenuDirectory={props.onContextMenuDirectory}
        />
      ))}
    </div>
  );
}

interface NodeProps {
  node: ExplorerNode;
  depth: number;
  expanded: string[];
  activePath: string | null;
  tabs: OpenFileTab[];
  onToggle: (path: string) => void;
  onOpen: (path: string) => void;
  onContextMenuFile: (event: MouseEvent<HTMLElement>, path: string) => void;
  onContextMenuDirectory: (event: MouseEvent<HTMLElement>, path: string) => void;
}

function TreeNode(p: NodeProps) {
  const isOpen = p.expanded.includes(p.node.path);
  const isActive = p.node.path === p.activePath;
  const tab = p.tabs.find((t) => t.path === p.node.path);
  const hasError = tab ? tab.diagnostics.some((d) => d.severity === 'error') : false;
  const hasWarning = tab ? tab.diagnostics.some((d) => d.severity === 'warning') : false;
  const isDirty = tab ? tab.state === 'dirty' || tab.state === 'saving' : false;
  const isReadonly = tab ? tab.state === 'readonly' : false;
  const inContext = tab?.inContext;
  const withEvidence = tab?.withEvidence;

  if (p.node.kind === 'directory') {
    return (
      <div className={`workspace-explorer-row kind-directory ${isActive ? 'is-active' : ''}`}>
        <button
          type="button"
          className="workspace-explorer-item"
          style={{ paddingLeft: `${8 + p.depth * 14}px` }}
          onClick={() => p.onToggle(p.node.path)}
          onContextMenu={(event) => p.onContextMenuDirectory(event, p.node.path)}
          aria-expanded={isOpen}
        >
          <span className={`workspace-explorer-caret ${isOpen ? 'is-open' : ''}`}><Icon name="chevron" size={11} /></span>
          <span className="workspace-explorer-icon"><FileTypeIcon node={p.node} size={14} /></span>
          <span className="workspace-explorer-name">{p.node.name}</span>
        </button>
        {isOpen && p.node.children.length > 0 && (
          <div className="workspace-explorer-children">
            {p.node.children.map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                depth={p.depth + 1}
                expanded={p.expanded}
                activePath={p.activePath}
                tabs={p.tabs}
                onToggle={p.onToggle}
                onOpen={p.onOpen}
                onContextMenuFile={p.onContextMenuFile}
                onContextMenuDirectory={p.onContextMenuDirectory}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={`workspace-explorer-row kind-file ${isActive ? 'is-active' : ''}`}>
      <button
        type="button"
        className="workspace-explorer-item"
        style={{ paddingLeft: `${8 + p.depth * 14 + 11}px` }}
        onClick={() => p.onOpen(p.node.path)}
        onContextMenu={(event) => p.onContextMenuFile(event, p.node.path)}
        title={p.node.path}
      >
        <span className="workspace-explorer-icon"><FileTypeIcon node={p.node} size={13} /></span>
        <span className="workspace-explorer-name">{p.node.name}</span>
        <span className="workspace-explorer-kind">{languageLabel(p.node.language)}</span>
        <span className="workspace-explorer-flags">
          {isDirty && <span className="workspace-flag state-dirty" title="Modificado sin guardar">●</span>}
          {isReadonly && <span className="workspace-flag state-readonly" title="Solo lectura">🔒</span>}
          {hasError && <span className="workspace-flag state-error" title="Errores">!</span>}
          {hasWarning && !hasError && <span className="workspace-flag state-warning" title="Warnings">⚠</span>}
          {inContext && <span className="workspace-flag state-context" title="En Árbol de Contexto">◇</span>}
          {withEvidence && <span className="workspace-flag state-evidence" title="Con evidencia">✓</span>}
        </span>
      </button>
    </div>
  );
}

function filterTree(nodes: ExplorerNode[], query: string, filter: WorkspaceFilter, tabs: OpenFileTab[]): ExplorerNode[] {
  const lower = query.trim().toLowerCase();
  const matchesFilter = (node: ExplorerNode): boolean => {
    switch (filter) {
      case 'all': return true;
      case 'code': return node.kind === 'code';
      case 'python': return node.language === 'python';
      case 'typescript': return node.language === 'typescript' || node.language === 'tsx';
      case 'javascript': return node.language === 'javascript' || node.language === 'jsx';
      case 'json': return node.language === 'json';
      case 'markdown': return node.language === 'markdown';
      case 'shell': return node.language === 'shell';
      case 'web': return node.language === 'css' || node.language === 'html';
      case 'text': return node.language === 'text' || node.language === 'unknown' || node.language === 'dotenv';
      case 'directory': return node.kind === 'directory';
      case 'with-errors': {
        const tab = tabs.find((t) => t.path === node.path);
        return tab ? tab.diagnostics.some((d) => d.severity === 'error' || d.severity === 'warning') : false;
      }
      default: return true;
    }
  };
  const matchesQuery = (node: ExplorerNode): boolean => {
    if (!lower) return true;
    return node.name.toLowerCase().includes(lower) || node.path.toLowerCase().includes(lower) || (node.extension || '').includes(lower);
  };
  const visit = (node: ExplorerNode): ExplorerNode | null => {
    if (node.kind === 'directory') {
      const filteredChildren = node.children.map(visit).filter(Boolean) as ExplorerNode[];
      if (filteredChildren.length > 0) {
        return { ...node, children: filteredChildren };
      }
      if (matchesQuery(node) && matchesFilter(node)) return node;
      return null;
    }
    if (matchesQuery(node) && matchesFilter(node)) return node;
    return null;
  };
  return nodes.map(visit).filter(Boolean) as ExplorerNode[];
}
