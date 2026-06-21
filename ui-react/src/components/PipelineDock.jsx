import { useState } from 'react'
import { useToast } from './Toast'

function PipelineNode({ node, active, completed, onSelect }) {
  return (
    <button
      type="button"
      className={`pipeline-node ${active ? 'is-active' : ''} ${completed ? 'is-completed' : ''}`}
      onClick={onSelect}
      aria-pressed={active}
    >
      <strong>{node.name}</strong>
      <span>{node.subtitle}</span>
    </button>
  )
}

export default function PipelineDock({ pipeline, inspectorOpen, onToggleInspector, compact }) {
  const [open, setOpen] = useState(true)
  const { push } = useToast()

  if (!pipeline) return null
  const { nodes, active, completed, select, advance } = pipeline

  return (
    <section className={`pipeline-dock ${open ? 'is-open' : 'is-closed'} ${compact ? 'is-compact' : ''}`} aria-label="Control Deck">
      <header className="dock-head">
        <div className="dock-title">
          <strong>Control Deck · Code Forge</strong>
          <span>{nodes.length} nodos · {completed.size} completados</span>
        </div>
        <div className="dock-actions">
          <button
            type="button"
            className="dock-btn"
            onClick={() => {
              advance()
              push('Avanzando al siguiente nodo del pipeline')
            }}
            disabled={completed.size === nodes.length}
          >
            ⇥ Avanzar
          </button>
          <button
            type="button"
            className="dock-btn"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
          >
            {open ? 'Ocultar' : 'Mostrar'}
          </button>
          <button
            type="button"
            className="dock-btn primary"
            onClick={() => {
              onToggleInspector()
              push(inspectorOpen ? 'Inspector ocultado' : 'Inspector abierto')
            }}
            aria-pressed={inspectorOpen}
          >
            ☷ Inspector
          </button>
        </div>
      </header>
      {open ? (
        <div className="dock-pipeline" role="list">
          {nodes.map((node, index) => (
            <div key={node.id} className="dock-pipeline-row" role="listitem">
              <PipelineNode
                node={node}
                active={node.id === active.id}
                completed={completed.has(node.id)}
                onSelect={() => {
                  select(node.id)
                  push(`Nodo activo: ${node.name}`)
                }}
              />
              {index < nodes.length - 1 ? <span className="dock-arrow" aria-hidden="true">→</span> : null}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  )
}
