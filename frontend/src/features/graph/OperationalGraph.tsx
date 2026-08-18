import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon, type IconName } from '@/shared/Icon';

export type GraphLayout = 'hierarchical' | 'radial' | 'linear';

export interface OperationalGraphNode {
  id: string;
  type: string;
  label: string;
  value: string;
  icon: IconName;
}

type Point = { x: number; y: number };
type Drag = { kind: 'node' | 'pan'; id?: string; startX: number; startY: number; originX: number; originY: number };

const EDGES: Array<[string, string]> = [
  ['input', 'workspace'], ['context', 'workspace'], ['workspace', 'validation'],
  ['workspace', 'evidence'], ['validation', 'output'], ['evidence', 'output']
];

const LAYOUTS: Record<GraphLayout, Record<string, Point>> = {
  hierarchical: {
    input: { x: 14, y: 25 }, context: { x: 17, y: 73 }, workspace: { x: 48, y: 46 },
    validation: { x: 78, y: 24 }, evidence: { x: 79, y: 72 }, output: { x: 51, y: 88 }
  },
  radial: {
    input: { x: 26, y: 25 }, context: { x: 23, y: 70 }, workspace: { x: 50, y: 47 },
    validation: { x: 76, y: 25 }, evidence: { x: 78, y: 70 }, output: { x: 50, y: 87 }
  },
  linear: {
    input: { x: 10, y: 48 }, context: { x: 27, y: 48 }, workspace: { x: 44, y: 48 },
    validation: { x: 61, y: 48 }, evidence: { x: 78, y: 48 }, output: { x: 91, y: 48 }
  }
};

interface Props {
  nodes: OperationalGraphNode[];
  layout: GraphLayout;
  filtered: boolean;
  isLive: boolean;
  onLayoutChange: (layout: GraphLayout) => void;
  onFilteredChange: (filtered: boolean) => void;
  onInspect: (node: OperationalGraphNode) => void;
}

export function OperationalGraph({ nodes, layout, filtered, isLive, onLayoutChange, onFilteredChange, onInspect }: Props) {
  const [selectedId, setSelectedId] = useState('workspace');
  const [positions, setPositions] = useState<Record<string, Point>>(LAYOUTS[layout]);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [drag, setDrag] = useState<Drag | null>(null);
  const boardRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    setPositions(LAYOUTS[layout]);
    setPan({ x: 0, y: 0 });
  }, [layout]);

  const selected = nodes.find((node) => node.id === selectedId) || nodes[0] || null;
  const neighbourIds = useMemo(() => new Set([
    selected?.id,
    ...EDGES.flatMap(([from, to]) => from === selected?.id ? [to] : to === selected?.id ? [from] : [])
  ]), [selected?.id]);
  const visibleNodes = filtered ? nodes.filter((node) => neighbourIds.has(node.id)) : nodes;
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const visibleEdges = EDGES.filter(([from, to]) => visibleIds.has(from) && visibleIds.has(to));
  const neighbours = nodes.filter((node) => neighbourIds.has(node.id) && node.id !== selected?.id);

  const reset = () => {
    setPositions(LAYOUTS[layout]);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };
  const select = (node: OperationalGraphNode) => setSelectedId(node.id);
  const startDrag = (event: React.PointerEvent<HTMLElement>, kind: Drag['kind'], id?: string) => {
    event.stopPropagation();
    const origin = id ? positions[id] : pan;
    setDrag({ kind, id, startX: event.clientX, startY: event.clientY, originX: origin?.x || 0, originY: origin?.y || 0 });
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };
  const moveDrag = (event: React.PointerEvent<HTMLElement>) => {
    if (!drag) return;
    const dx = (event.clientX - drag.startX) / zoom;
    const dy = (event.clientY - drag.startY) / zoom;
    if (drag.kind === 'node' && drag.id) {
      setPositions((current) => ({ ...current, [drag.id as string]: { x: Math.max(5, Math.min(95, drag.originX + dx / 6)), y: Math.max(10, Math.min(90, drag.originY + dy / 5)) } }));
    } else {
      setPan({ x: drag.originX + dx, y: drag.originY + dy });
    }
  };

  if (!selected) return null;
  return <section className="operational-graph" aria-label="Grafo operativo">
    <header className="operational-graph-head">
      <div>
        <span>MAPA OPERATIVO</span>
        <h2>Flujo de trabajo</h2>
        <p>Relaciones activas entre sesión, contexto, workspace y evidencia.</p>
      </div>
      <div className="operational-graph-stats" aria-label="Resumen del grafo">
        <span><b>{visibleNodes.length}{filtered ? ` / ${nodes.length}` : ''}</b> nodos</span><span><b>{visibleEdges.length}</b> vínculos</span><span className={isLive ? 'is-live' : 'is-muted'}><i /> {isLive ? 'vivo' : 'sin conexión'}</span>
      </div>
    </header>

    <div className="operational-graph-toolbar">
      <div className="graph-segmented" role="group" aria-label="Alcance visible">
        <button type="button" className={!filtered ? 'is-active' : ''} onClick={() => onFilteredChange(false)}>Todo</button>
        <button type="button" className={filtered ? 'is-active' : ''} onClick={() => onFilteredChange(true)}>Conectados</button>
      </div>
      <div className="graph-segmented" role="group" aria-label="Distribución del grafo">
        {(['hierarchical', 'radial', 'linear'] as GraphLayout[]).map((item) => <button key={item} type="button" className={layout === item ? 'is-active' : ''} onClick={() => onLayoutChange(item)}>{item === 'hierarchical' ? 'Jerarquía' : item === 'radial' ? 'Radial' : 'Línea'}</button>)}
      </div>
      <div className="graph-viewport-controls" role="group" aria-label="Zoom del grafo">
        <button type="button" aria-label="Alejar" onClick={() => setZoom((value) => Math.max(.7, Number((value - .1).toFixed(2))))}><Icon name="zoomOut" size={14} /></button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" aria-label="Acercar" onClick={() => setZoom((value) => Math.min(1.45, Number((value + .1).toFixed(2))))}><Icon name="zoomIn" size={14} /></button>
        <button type="button" aria-label="Restablecer vista" onClick={reset}><Icon name="center" size={14} /></button>
      </div>
    </div>

    <div className="operational-graph-body">
      <section
        ref={boardRef}
        className={`operational-graph-board ${drag?.kind === 'pan' ? 'is-panning' : ''}`}
        onPointerDown={(event) => { if (!(event.target as HTMLElement).closest('button')) startDrag(event, 'pan'); }}
        onPointerMove={moveDrag}
        onPointerUp={() => setDrag(null)}
        onPointerCancel={() => setDrag(null)}
        onPointerLeave={() => setDrag(null)}
        onWheel={(event) => { event.preventDefault(); setZoom((value) => Math.max(.7, Math.min(1.45, Number((value + (event.deltaY < 0 ? .08 : -.08)).toFixed(2))))); }}
        aria-label="Lienzo del flujo; arrastra un nodo o el espacio vacío"
      >
        <div className="operational-graph-stage" style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
          <svg className="operational-graph-links" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            <defs><marker id="graph-arrow" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0,0 L5,2.5 L0,5 z" /></marker></defs>
            {visibleEdges.map(([from, to]) => {
              const start = positions[from]; const end = positions[to];
              const isActive = from === selected.id || to === selected.id;
              return <path key={`${from}-${to}`} className={isActive ? 'is-active' : ''} markerEnd="url(#graph-arrow)" d={`M ${start.x} ${start.y} C ${(start.x + end.x) / 2} ${start.y}, ${(start.x + end.x) / 2} ${end.y}, ${end.x} ${end.y}`} />;
            })}
          </svg>
          {visibleNodes.map((node) => <button
            key={node.id}
            type="button"
            className={`operational-graph-node is-${node.type} ${node.id === selected.id ? 'is-selected' : ''}`}
            style={{ left: `${positions[node.id].x}%`, top: `${positions[node.id].y}%` }}
            onPointerDown={(event) => startDrag(event, 'node', node.id)}
            onClick={() => select(node)}
            aria-pressed={node.id === selected.id}
          >
            <span className="operational-graph-node-icon"><Icon name={node.icon} size={17} /></span>
            <span><small>{node.type}</small><strong>{node.label}</strong><em>{node.value}</em></span>
            <i />
          </button>)}
        </div>
        <div className="operational-graph-board-hint"><Icon name="expand" size={13} /> Arrastra, rueda para zoom y selecciona un nodo.</div>
      </section>

      <aside className="operational-graph-detail" aria-live="polite">
        <header><span>NODO SELECCIONADO</span><button type="button" aria-label="Abrir en inspector" onClick={() => onInspect(selected)}><Icon name="inspector" size={14} /></button></header>
        <div className="operational-graph-detail-title"><span className={`type-${selected.type}`}><Icon name={selected.icon} size={18} /></span><div><strong>{selected.label}</strong><small>{selected.type}</small></div></div>
        <dl><div><dt>Estado</dt><dd>{selected.value}</dd></div><div><dt>Conexiones</dt><dd>{neighbours.length}</dd></div><div><dt>Vista</dt><dd>{layout === 'hierarchical' ? 'Jerarquía' : layout === 'radial' ? 'Radial' : 'Línea'}</dd></div></dl>
        <section><span>RELACIONADOS</span>{neighbours.length ? neighbours.map((node) => <button key={node.id} type="button" onClick={() => select(node)}><Icon name={node.icon} size={13} /><span>{node.label}</span><Icon name="chevron" size={13} /></button>) : <p>Sin conexiones visibles.</p>}</section>
        <button type="button" className="operational-graph-inspect" onClick={() => onInspect(selected)}>Abrir inspector <Icon name="arrowRight" size={14} /></button>
      </aside>
    </div>
  </section>;
}
