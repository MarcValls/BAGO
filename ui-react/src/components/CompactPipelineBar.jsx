export default function CompactPipelineBar({ pipeline, onOpenFlow, onAdvance }) {
  if (!pipeline) return null
  const { nodes, active, completed } = pipeline
  const index = nodes.findIndex((n) => n.id === active.id) + 1
  const total = nodes.length
  const state = completed.has(active.id) ? 'Validada' : (active.name || 'En curso')

  return (
    <div className="compact-pipeline-bar" aria-label="Progreso del pipeline">
      <span className="compact-pipeline-label">Proceso</span>
      <span className="compact-pipeline-value">{active.name || 'Entrada'}</span>
      <span className="compact-pipeline-dot" aria-hidden="true">·</span>
      <span className="compact-pipeline-count">{index} de {total}</span>
      <span className="compact-pipeline-dot" aria-hidden="true">·</span>
      <span className="compact-pipeline-state">{state}</span>
      <div className="compact-pipeline-actions">
        <button type="button" className="compact-pipeline-btn" onClick={onOpenFlow}>
          Abrir flujo
        </button>
        <button
          type="button"
          className="compact-pipeline-btn primary"
          onClick={onAdvance}
          disabled={completed.size === nodes.length}
        >
          Avanzar
        </button>
      </div>
    </div>
  )
}
