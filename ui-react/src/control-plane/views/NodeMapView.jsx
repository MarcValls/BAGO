import { useEffect, useMemo, useRef, useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { useNodeConnectors, useNodePieces, useNodeStatus } from '../useBagoData'

const NODE_COLORS = {
  installation: '#3b82f6',
  tool: '#f59e0b',
  connector: '#ec4899',
  knowledge: '#10b981',
  agent: '#a855f7',
  skill: '#06b6d4',
  model: '#ef4444',
  default: '#64748b',
}

function inferNodeColor(node) {
  const type = (node.type || node.kind || node.sub || '').toLowerCase()
  for (const [key, color] of Object.entries(NODE_COLORS)) {
    if (type.includes(key)) return color
  }
  return NODE_COLORS.default
}

function inferNodeType(node) {
  const type = (node.type || node.kind || node.sub || '').toLowerCase()
  for (const key of Object.keys(NODE_COLORS)) {
    if (type.includes(key)) return key
  }
  return 'node'
}

export default function NodeMapView({ context, onSetContext, onAction }) {
  const { data: statusData, loading: stLoading, error: stError, refresh: refreshStatus } = useNodeStatus()
  const { data: piecesData, loading: pcLoading, refresh: refreshPieces } = useNodePieces()
  const { data: connData, loading: cnLoading, refresh: refreshConnectors } = useNodeConnectors()
  const svgRef = useRef(null)
  const [scale, setScale] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(null)
  const [selected, setSelected] = useState(null)
  const [localNodes, setLocalNodes] = useState([])

  const status = statusData?.ok ? (statusData.data || statusData.text || statusData.raw) : null
  const pieces = piecesData?.ok ? (piecesData.data || piecesData.text || piecesData.raw) : null
  const connectors = connData?.ok ? (connData.data || connData.text || connData.raw) : null

  const nodes = useMemo(() => {
    const base = Array.isArray(pieces)
      ? pieces.map((p, i) => ({
          id: p.id || p.name || `piece-${i}`,
          label: p.id || p.name || `piece-${i}`,
          sub: `${p.type || p.kind || 'piece'} · ${p.enabled !== false ? 'active' : 'offline'}`,
          left: `${15 + ((i * 17) % 70)}%`,
          top: `${15 + ((i * 13) % 60)}%`,
          type: p.type || p.kind,
          piece: p,
        }))
      : []

    const installations = status?.installations || []
    installations.forEach((inst, i) => {
      if (base.some((n) => n.id === inst.id)) return
      base.push({
        id: inst.id || `inst-${i}`,
        label: inst.description || inst.id || `inst-${i}`,
        sub: `Installation · ${inst.mode || 'unknown'}`,
        left: `${20 + ((i * 25) % 55)}%`,
        top: `${20 + ((i * 19) % 45)}%`,
        core: true,
        type: 'installation',
        installation: inst,
      })
    })

    return base.map((n) => ({
      ...n,
      color: inferNodeColor(n),
      kind: inferNodeType(n),
    }))
  }, [pieces, status])

  useEffect(() => {
    setLocalNodes(nodes)
  }, [nodes])

  const displayNodes = localNodes.length > 0 ? localNodes : nodes

  const edges = useMemo(() => {
    if (!Array.isArray(connectors)) return []
    return connectors
      .filter((c) => displayNodes.some((n) => n.id === c.from) && displayNodes.some((n) => n.id === c.to))
      .map((c) => ({ ...c, color: c.active ? '#22c55e' : '#64748b' }))
  }, [connectors, displayNodes])

  function handleWheel(e) {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setScale((s) => Math.max(0.5, Math.min(2.5, s * delta)))
  }

  function startDrag(e, node) {
    e.stopPropagation()
    setDragging(node.id)
    setSelected(node)
  }

  function onMouseMove(e) {
    if (!dragging || !svgRef.current) return
    const rect = svgRef.current.getBoundingClientRect()
    const x = ((e.clientX - rect.left - pan.x) / scale / rect.width) * 100
    const y = ((e.clientY - rect.top - pan.y) / scale / rect.height) * 100
    setLocalNodes((prev) =>
      prev.map((n) =>
        n.id === dragging
          ? { ...n, left: `${Math.max(5, Math.min(95, x))}%`, top: `${Math.max(5, Math.min(95, y))}%` }
          : n
      )
    )
  }

  function endDrag() {
    setDragging(null)
  }

  useEffect(() => {
    if (!dragging) return
    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', endDrag)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', endDrag)
    }
  }, [dragging, pan, scale])

  const loading = stLoading || pcLoading || cnLoading
  const error = stError

  return (
    <section className="cp-view cp-view-active cp-node-map-view">
      <div className="cp-toolbar">
        <div className="cp-node-map-title">
          <Icon name="nodes" size={20} />
          <div>
            <div>Mapa de nodos</div>
            <div className="cp-node-map-subtitle">{displayNodes.length} nodos · {edges.length} conexiones</div>
          </div>
        </div>
        <div className="cp-node-map-controls">
          <button type="button" className="cp-btn" onClick={() => { refreshStatus(); refreshPieces(); refreshConnectors(); }}>
            Releer
          </button>
          <button type="button" className="cp-btn" onClick={() => setScale((s) => Math.min(2.5, s * 1.2))}>+</button>
          <button type="button" className="cp-btn" onClick={() => setScale((s) => Math.max(0.5, s * 0.8))}>−</button>
          <button type="button" className="cp-btn" onClick={() => { setScale(1); setPan({ x: 0, y: 0 }) }}>Reset</button>
          <button type="button" className="cp-btn" onClick={() => onAction?.('validate-node')}>Validar</button>
        </div>
      </div>

      {loading ? <ViewState loading /> :
       error ? <ViewState error={error} /> :
       !displayNodes.length ? <ViewState empty emptyLabel="Sin nodos reales disponibles" /> :
       (
        <div className="cp-node-map-stage">
          <svg
            ref={svgRef}
            className="cp-node-map-svg"
            onWheel={handleWheel}
            style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})` }}
          >
            <g className="cp-node-map-edges">
              {edges.map((edge, i) => {
                const from = displayNodes.find((n) => n.id === edge.from)
                const to = displayNodes.find((n) => n.id === edge.to)
                if (!from || !to) return null
                return (
                  <line
                    key={i}
                    x1={from.left}
                    y1={from.top}
                    x2={to.left}
                    y2={to.top}
                    stroke={edge.color}
                    strokeWidth={1.5}
                    strokeDasharray={edge.active ? undefined : '4 3'}
                  />
                )
              })}
            </g>
            <g className="cp-node-map-nodes">
              {displayNodes.map((node) => (
                <g
                  key={node.id}
                  className={`cp-node-map-node ${selected?.id === node.id ? 'is-selected' : ''}`}
                  transform={`translate(${node.left}, ${node.top})`}
                  onMouseDown={(e) => startDrag(e, node)}
                  onClick={() => setSelected(node)}
                >
                  <circle r={node.core ? 18 : 12} fill={node.color} opacity={0.2} />
                  <circle r={node.core ? 14 : 10} fill={node.color} />
                  <text y={4} textAnchor="middle" fill="#fff" fontSize={10} fontWeight={600}>
                    {node.label?.substring(0, 3).toUpperCase()}
                  </text>
                </g>
              ))}
            </g>
          </svg>

          {selected && (
            <div className="cp-node-map-detail">
              <div className="cp-node-map-detail-head">
                <span style={{ color: selected.color }}>{selected.label}</span>
                <button type="button" onClick={() => setSelected(null)}>✕</button>
              </div>
              <div className="cp-node-map-detail-body">
                <Badge variant={selected.kind === 'installation' ? 'ok' : 'neutral'}>{selected.kind}</Badge>
                <div className="cp-node-map-detail-sub">{selected.sub}</div>
                {selected.installation && (
                  <div className="cp-node-map-detail-meta">
                    <div>Path: {selected.installation.path}</div>
                    <div>Versión: {selected.installation.version}</div>
                    <div>Supervisor: {selected.installation.supervisor_alive ? 'vivo' : 'muerto'}</div>
                  </div>
                )}
                {selected.piece && (
                  <div className="cp-node-map-detail-meta">
                    <div>Tipo: {selected.piece.type}</div>
                    <div>Estado: {selected.piece.enabled !== false ? 'activo' : 'offline'}</div>
                  </div>
                )}
                <button
                  type="button"
                  className="cp-btn cp-btn-primary"
                  onClick={() => onSetContext?.((c) => ({ ...c, node: selected.id }))}
                >
                  Fijar nodo
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
