import { useState, useEffect } from 'react'
import { chatApi } from '../api'

function PipelineStep({ node, isActive, isCompleted, onSelect, onAdvance }) {
  return (
    <div className={`dock-step ${isActive ? 'is-active' : ''} ${isCompleted ? 'is-completed' : ''}`}>
      <button type="button" className="dock-step-node" onClick={onSelect}>
        <span className="dock-step-num">{node.name}</span>
        <span className="dock-step-sub">{node.subtitle}</span>
      </button>
      {isActive && (
        <button type="button" className="dock-step-advance" onClick={onAdvance} title="Avanzar">
          →
        </button>
      )}
    </div>
  )
}

function StepConfig({ node, models, onAssign }) {
  const [provider, setProvider] = useState(node.assignedProvider || '')
  const [model, setModel] = useState(node.assignedModel || '')

  useEffect(() => {
    setProvider(node.assignedProvider || '')
    setModel(node.assignedModel || '')
  }, [node.id])

  const availableModels = models.filter((m) => !provider || m.provider === provider)

  function handleChange(field, value) {
    if (field === 'provider') {
      setProvider(value)
      setModel('')
      onAssign(node.id, value, '')
    } else {
      setModel(value)
      onAssign(node.id, provider, value)
    }
  }

  return (
    <div className="dock-step-config">
      <div className="dock-config-row">
        <label className="dock-config-label">Provider</label>
        <select
          className="dock-config-select"
          value={provider}
          onChange={(e) => handleChange('provider', e.target.value)}
        >
          <option value="">Auto</option>
          {[...new Set(models.map((m) => m.provider))].map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </div>
      <div className="dock-config-row">
        <label className="dock-config-label">Modelo</label>
        <select
          className="dock-config-select"
          value={model}
          onChange={(e) => handleChange('model', e.target.value)}
          disabled={!provider}
        >
          <option value="">Auto</option>
          {availableModels.map((m) => (
            <option key={m.id} value={m.id}>{m.id}</option>
          ))}
        </select>
      </div>
    </div>
  )
}

export default function Dock({ pipeline, models, onAssignStep, compact }) {
  const [open, setOpen] = useState(true)
  const [activeStepId, setActiveStepId] = useState(pipeline?.active?.id || null)
  const [allModels, setAllModels] = useState(models || [])

  useEffect(() => {
    if (!models || models.length) {
      setAllModels(models || [])
    } else {
      chatApi.getModels('ollama-local').then((d) => setAllModels(d.items || [])).catch(() => {})
    }
  }, [models])

  if (!pipeline) return null
  const { nodes, active, completed, select, advance } = pipeline

  return (
    <section className={`dock ${open ? 'is-open' : 'is-closed'} ${compact ? 'is-compact' : ''}`} aria-label="Pipeline Dock">
      <header className="dock-head">
        <div className="dock-title">
          <strong>Pipeline · Code Forge</strong>
          <span>{nodes.length} pasos · {completed.size} completados</span>
        </div>
        <div className="dock-actions">
          <button
            type="button"
            className="dock-btn"
            onClick={() => { advance(); setOpen(true) }}
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
        </div>
      </header>

      {open && (
        <div className="dock-body">
          <div className="dock-steps" role="list">
            {nodes.map((node, index) => (
              <div key={node.id} className="dock-step-row" role="listitem">
                <PipelineStep
                  node={node}
                  isActive={node.id === active.id}
                  isCompleted={completed.has(node.id)}
                  onSelect={() => {
                    select(node.id)
                    setActiveStepId(node.id)
                  }}
                  onAdvance={() => advance()}
                />
                {index < nodes.length - 1 && <span className="dock-arrow" aria-hidden="true">↓</span>}
              </div>
            ))}
          </div>

          {activeStepId && (
            <div className="dock-sequencer">
              <div className="dock-sequencer-title">
                Configurar paso: <strong>{nodes.find((n) => n.id === activeStepId)?.name}</strong>
              </div>
              <StepConfig
                node={{ ...nodes.find((n) => n.id === activeStepId), assignedProvider: nodes.find((n) => n.id === activeStepId)?.assignedProvider }}
                models={allModels}
                onAssign={(stepId, prov, mdl) => {
                  onAssignStep?.(stepId, prov, mdl)
                }}
              />
            </div>
          )}
        </div>
      )}
    </section>
  )
}