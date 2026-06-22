import { useEffect, useMemo, useState } from 'react'
import { useToast } from './Toast'
import { DEFAULT_VERSION_LABEL } from '../version'

function Metric({ label, value, accent }) {
  return (
    <div className="inspector-metric">
      <span>{label}</span>
      <b className={accent ? `metric-${accent}` : ''}>{value}</b>
    </div>
  )
}

function ClaimsList({ claims, onToggle }) {
  if (!claims?.length) return null
  return (
    <ul className="inspector-claims">
      {claims.map((claim, index) => (
        <li key={`${claim.text}-${index}`} className={claim.ok ? 'is-ok' : 'is-ko'}>
          <button
            type="button"
            className="claim-toggle"
            onClick={() => onToggle(index, !claim.ok)}
            aria-pressed={claim.ok}
            title={claim.ok ? 'Marcar como no verificado' : 'Marcar como verificado'}
          >
            {claim.ok ? '✓' : '○'}
          </button>
          <div>
            <div className="claim-text">{claim.text}</div>
            <div className="claim-proof">prueba: {claim.proof || '—'}</div>
          </div>
        </li>
      ))}
    </ul>
  )
}

function RuntimePanel({ runtime }) {
  if (!runtime) return null
  const session = runtime.session || {}
  const simulation = runtime.simulation || {}
  const catalog = runtime.catalog || {}
  return (
    <div className="inspector-runtime">
      <strong>Runtime en vivo</strong>
      <Metric label="Provider" value={session.provider || '—'} />
      <Metric label="Modelo" value={session.model || '—'} />
      <Metric label="BAGO version" value={session.bago_version || DEFAULT_VERSION_LABEL} />
      <Metric label="Simulación" value={simulation.mode || 'off'} accent={simulation.mode && simulation.mode !== 'off' ? 'warn' : 'muted'} />
      <Metric label="Catálogo" value={catalog.mode || 'off'} />
    </div>
  )
}

export default function ManagerInspector({ pipeline, inspector, kit, onClose }) {
  const { push } = useToast()
  const [newClaim, setNewClaim] = useState('')

  useEffect(() => {
    inspector.refreshRuntime()
  }, [inspector])

  const { active, metrics, nodes } = pipeline
  const live = metrics[active.id] || {}
  const contract = active.contract || {}

  const risks = useMemo(() => {
    const map = { bajo: 'ok', medio: 'warn', mínimo: 'muted' }
    return map[live.riesgo || active.metric?.riesgo] || 'muted'
  }, [live, active])

  if (!inspector.open) return null

  function addClaim(event) {
    event.preventDefault()
    if (!newClaim.trim()) return
    inspector.addClaim(newClaim)
    setNewClaim('')
    push('Claim añadido al inspector')
  }

  return (
    <aside className="manager-inspector" aria-label="Inspector de conversación">
      <header className="inspector-head">
        <div>
          <strong>{active.name}</strong>
          <p>{active.subtitle}</p>
        </div>
        <button type="button" className="inspector-close" onClick={onClose} aria-label="Cerrar inspector">✕</button>
      </header>

      <section className="inspector-section">
        <h4>Estado de evidencia</h4>
        <Metric label="Validación" value={inspector.evidence.state} accent={inspector.evidence.state === 'VALIDADA' ? 'ok' : 'warn'} />
        <Metric label="Tests" value={`${inspector.evidence.tests?.passed || 0} ok · ${inspector.evidence.tests?.failed || 0} ko`} accent={(inspector.evidence.tests?.failed || 0) === 0 ? 'ok' : 'warn'} />
        <Metric label="Subtests" value={`${inspector.evidence.subtests?.passed || 0} ok`} />
        <Metric label="Duración" value={inspector.evidence.duration || '—'} />
      </section>

      <section className="inspector-section">
        <h4>Contrato del nodo</h4>
        <Metric label="Instalación" value={kit.installation?.label || 'BAGO local'} />
        <Metric label="Pipeline" value={kit.pipeline?.label || 'Code Forge'} />
        <Metric label="Modo" value={live.modo || active.metric?.modo || '—'} />
        <Metric label="Riesgo" value={live.riesgo || active.metric?.riesgo || 'bajo'} accent={risks} />
        <Metric label="Entrada" value={contract.in || '—'} />
        <Metric label="Salida" value={contract.out || '—'} />
      </section>

      <section className="inspector-section">
        <h4>Claims verificables</h4>
        <ClaimsList claims={inspector.evidence.claims} onToggle={inspector.setClaim} />
        <form className="claim-form" onSubmit={addClaim}>
          <input
            type="text"
            value={newClaim}
            onChange={(e) => setNewClaim(e.target.value)}
            placeholder="Añadir claim…"
            aria-label="Nuevo claim"
          />
          <button type="submit" className="inspector-btn">+</button>
        </form>
      </section>

      <section className="inspector-section inspector-rec">
        <strong>Recomendación</strong>
        <p>
          Mantén el chat como centro, usa la barra superior como equipamiento de la sesión y
          reserva el inspector para auditar cada nodo antes de aplicarlo. Esta conversación
          conserva instalación, modelo, pipeline yClaims; el inspector es la prueba de que
          todo encaja con la política {kit.policy?.label || 'Staged'}.
        </p>
      </section>

      <section className="inspector-section">
        <h4>Vista global</h4>
        <div className="inspector-nodes">
          {nodes.map((node) => (
            <span
              key={node.id}
              className={`inspector-node ${node.id === active.id ? 'is-active' : ''} ${pipeline.completed.has(node.id) ? 'is-done' : ''}`}
              onClick={() => pipeline.select(node.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter') pipeline.select(node.id) }}
            >
              {node.name}
            </span>
          ))}
        </div>
      </section>

      <RuntimePanel runtime={inspector.runtime} />
    </aside>
  )
}
