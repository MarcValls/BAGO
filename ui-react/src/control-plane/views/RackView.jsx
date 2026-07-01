import { useMemo, useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { usePipelineNodes } from '../../usePipelineNodes'

const STATUS_LABEL = {
  idle: 'Pendiente',
  running: 'En curso',
  ok: 'Listo',
  error: 'Bloqueado',
}

const STATUS_VARIANT = {
  idle: 'neutral',
  running: 'warn',
  ok: 'ok',
  error: 'danger',
}

function RackModule({ mod, status, active, onClick }) {
  return (
    <button
      type="button"
      className={`cp-rack-module ${active ? 'is-active' : ''} status-${status}`}
      onClick={onClick}
    >
      <div className="cp-rack-module-top">
        <span className="cp-rack-module-type">{mod.id}</span>
        <Badge variant={STATUS_VARIANT[status] || 'neutral'}>{STATUS_LABEL[status] || status}</Badge>
      </div>
      <div className="cp-rack-module-label">{mod.name}</div>
      <div className="cp-rack-module-cmd">{mod.subtitle}</div>
    </button>
  )
}

export default function RackView({ onAction }) {
  const { nodes, activeId, active, select, advance } = usePipelineNodes()
  const [selected, setSelected] = useState(activeId)

  const progress = useMemo(() => {
    const index = nodes.findIndex((node) => node.id === activeId)
    return { done: index < 0 ? 0 : index + 1, total: nodes.length }
  }, [activeId, nodes])

  const selectedNode = nodes.find((node) => node.id === selected) || active

  return (
    <section className="cp-view cp-view-active cp-rack-view">
      <div className="cp-toolbar">
        <div className="cp-rack-title">
          <Icon name="grid" size={20} />
          <div>
            <div>Rack de ejecución</div>
            <div className="cp-rack-subtitle">Pipeline real · {progress.done}/{progress.total}</div>
          </div>
        </div>
        <div className="cp-rack-controls">
          <button type="button" className="cp-btn cp-btn-primary" onClick={() => { advance(); onAction?.('toast', 'Pipeline avanzado') }}>
            Avanzar
          </button>
          <button type="button" className="cp-btn" onClick={() => { select(nodes[0]?.id || activeId, 'toolbar'); setSelected(nodes[0]?.id || activeId) }}>
            Reiniciar
          </button>
        </div>
      </div>

      {nodes.length === 0 ? (
        <ViewState empty emptyLabel="Sin nodos de pipeline reales" />
      ) : (
        <div className="cp-rack-body">
          <div className="cp-rack-rail">
            {nodes.map((node) => {
              const status = node.id === activeId ? 'running' : 'idle'
              return (
                <div key={node.id} className="cp-rack-unit">
                  <RackModule
                    mod={node}
                    status={status}
                    active={selected === node.id}
                    onClick={() => { setSelected(node.id); select(node.id, 'rack') }}
                  />
                  <div className="cp-rack-arrows">
                    <button type="button" disabled={node.id === nodes[0]?.id} onClick={() => select(nodes[Math.max(0, nodes.findIndex((n) => n.id === node.id) - 1)]?.id || node.id, 'previous')}>
                      ‹
                    </button>
                    <button type="button" disabled={node.id === nodes[nodes.length - 1]?.id} onClick={() => select(nodes[Math.min(nodes.length - 1, nodes.findIndex((n) => n.id === node.id) + 1)]?.id || node.id, 'next')}>
                      ›
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          {selectedNode && (
            <div className="cp-rack-detail">
              <div className="cp-rack-detail-head">
                <span>{selectedNode.name}</span>
                <button type="button" onClick={() => setSelected(null)}>✕</button>
              </div>
              <div className="cp-rack-detail-body">
                <Badge>{selectedNode.id}</Badge>
                <div className="cp-rack-detail-cmd">{selectedNode.subtitle}</div>
                <div className="cp-rack-detail-deps">
                  Contrato: {selectedNode.contract?.in || '—'} → {selectedNode.contract?.out || '—'}
                </div>
                <div className="cp-rack-detail-deps">
                  Métrica: {selectedNode.metric?.riesgo || '—'} · {selectedNode.metric?.modo || '—'}
                </div>
                <button
                  type="button"
                  className="cp-btn cp-btn-primary"
                  onClick={() => onAction?.('toast', `Nodo fijado: ${selectedNode.id}`)}
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
