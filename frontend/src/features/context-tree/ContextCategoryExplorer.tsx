import { useMemo } from 'react';
import { Icon } from '@/shared/Icon';
import type { ContextNode } from './contextTreeTypes';

export type ContextDisplayMode = 'map' | 'board' | 'document';

interface Props {
  nodes: ContextNode[];
  mode: ContextDisplayMode;
  onModeChange: (mode: ContextDisplayMode) => void;
  onOpen: (nodeId: string) => void;
  onCreate: () => void;
}

type MapPoint = { id: string; x: number; y: number };

function reviewState(node: ContextNode): string {
  const review = node.metadata?.context_review;
  if (!review || typeof review !== 'object' || Array.isArray(review)) return 'pending';
  return String((review as Record<string, unknown>).status || 'pending');
}

function mapPoints(nodes: ContextNode[]): MapPoint[] {
  if (nodes.length === 1) return [{ id: nodes[0].id, x: 50, y: 50 }];
  return nodes.map((node, index) => {
    if (index === 0) return { id: node.id, x: 50, y: 18 };
    const children = Math.max(nodes.length - 1, 1);
    const angle = Math.PI * (.92 + ((index - 1) / Math.max(children - 1, 1)) * 1.16);
    return {
      id: node.id,
      x: 50 + Math.cos(angle) * 39,
      y: 68 + Math.sin(angle) * 27
    };
  });
}

function ContextMap(props: Pick<Props, 'nodes' | 'onOpen'>) {
  const points = useMemo(() => mapPoints(props.nodes), [props.nodes]);
  const pointById = useMemo(() => new Map(points.map((point) => [point.id, point])), [points]);
  const relations = useMemo(() => {
    const ids = new Set(props.nodes.map((node) => node.id));
    const seen = new Set<string>();
    return props.nodes.flatMap((node) => {
      const targets = [node.parentId, ...node.linkedNodeIds, ...node.conflictNodeIds].filter((id): id is string => Boolean(id && ids.has(id)));
      return targets.flatMap((targetId) => {
        const key = [node.id, targetId].sort().join(':');
        if (seen.has(key)) return [];
        seen.add(key);
        return [{ from: node.id, to: targetId, conflict: node.conflictNodeIds.includes(targetId) }];
      });
    });
  }, [props.nodes]);

  return (
    <div className="context-map-canvas" aria-label="Mapa visual del contexto">
      <div className="context-map-glow" />
      <svg className="context-map-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {relations.map((relation) => {
          const from = pointById.get(relation.from);
          const to = pointById.get(relation.to);
          if (!from || !to) return null;
          return <line key={`${relation.from}-${relation.to}`} x1={from.x} y1={from.y} x2={to.x} y2={to.y} className={relation.conflict ? 'is-conflict' : ''} />;
        })}
      </svg>
      {props.nodes.map((node) => {
        const point = pointById.get(node.id) || { x: 50, y: 50 };
        const state = reviewState(node);
        return (
          <button
            key={node.id}
            type="button"
            className="context-map-node"
            data-status={node.status}
            data-review={state}
            style={{ left: `${point.x}%`, top: `${point.y}%` }}
            onClick={() => props.onOpen(node.id)}
          >
            <span className="context-map-node-icon"><Icon name={state === 'validated' ? 'verified' : state === 'conflict' ? 'conflict' : 'context'} size={15} /></span>
            <span><strong>{node.title}</strong><small>{node.summary || 'Sin resumen'}</small></span>
            <em>{state === 'validated' ? 'Validado' : state === 'warning' || state === 'conflict' ? 'Revisar' : node.status}</em>
          </button>
        );
      })}
    </div>
  );
}

function ContextBoard(props: Pick<Props, 'nodes' | 'onOpen'>) {
  const lanes = [
    { id: 'active', label: 'En trabajo', nodes: props.nodes.filter((node) => !['validated', 'warning', 'conflict', 'unavailable'].includes(reviewState(node)) && !['canon', 'conflict', 'stale'].includes(node.status)) },
    { id: 'attention', label: 'Revisar', nodes: props.nodes.filter((node) => ['warning', 'conflict', 'unavailable'].includes(reviewState(node)) || ['conflict', 'stale'].includes(node.status)) },
    { id: 'closed', label: 'Validadas', nodes: props.nodes.filter((node) => reviewState(node) === 'validated' || node.status === 'canon') }
  ];
  return <div className="context-board" aria-label="Tablero del contexto">
    {lanes.map((lane) => <section key={lane.id} className="context-board-lane" data-lane={lane.id}>
      <header><strong>{lane.label}</strong><span>{lane.nodes.length}</span></header>
      <div>{lane.nodes.length === 0 ? <p>Sin elementos</p> : lane.nodes.map((node) => <button key={node.id} type="button" onClick={() => props.onOpen(node.id)}><strong>{node.title}</strong><span>{node.summary || 'Sin resumen'}</span><small>{node.priority} · {node.status}</small></button>)}</div>
    </section>)}
  </div>;
}

function ContextDocument(props: Pick<Props, 'nodes' | 'onOpen'>) {
  return <div className="context-document" aria-label="Documento de contexto">
    {props.nodes.map((node, index) => <article key={node.id}>
      <span>{String(index + 1).padStart(2, '0')}</span>
      <div><h3>{node.title}</h3><p>{node.summary || 'Sin resumen'}</p>{node.body && <div>{node.body}</div>}</div>
      <button type="button" className="secondary-button compact" onClick={() => props.onOpen(node.id)}>Editar</button>
    </article>)}
  </div>;
}

export function ContextCategoryExplorer(props: Props) {
  return <section className="context-explorer">
    <header className="context-explorer-toolbar">
      <div className="context-view-switch" role="group" aria-label="Representación del contexto">
        {([['map', 'Mapa', 'graph'], ['board', 'Tablero', 'layout'], ['document', 'Documento', 'file']] as const).map(([id, label, icon]) => <button key={id} type="button" className={props.mode === id ? 'is-active' : ''} aria-pressed={props.mode === id} onClick={() => props.onModeChange(id)}><Icon name={icon} size={12} /> {label}</button>)}
      </div>
      <button type="button" className="primary-button compact" onClick={props.onCreate}><Icon name="plus" size={12} /> Añadir</button>
    </header>
    {props.nodes.length === 0 ? <div className="context-category-empty-state"><Icon name="context" size={22} /><p>No hay contenido todavía.</p><span>Usa Añadir para crear la primera entrada.</span></div> : props.mode === 'map' ? <ContextMap nodes={props.nodes} onOpen={props.onOpen} /> : props.mode === 'board' ? <ContextBoard nodes={props.nodes} onOpen={props.onOpen} /> : <ContextDocument nodes={props.nodes} onOpen={props.onOpen} />}
  </section>;
}
