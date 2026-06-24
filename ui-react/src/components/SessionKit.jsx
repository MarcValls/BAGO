import { useState } from 'react'
import { useToast } from './Toast'
import { getUiConfig } from '../useUiConfig'

const PIPELINES = [
  { id: 'code-forge-3b',    label: 'Code Forge 3B',   variant: 'staged' },
  { id: 'auditoria',        label: 'Auditoría',        variant: 'safe' },
  { id: 'patch-nodular',    label: 'Patch nodular',    variant: 'manual' },
  { id: 'release-pipeline', label: 'Release pipeline', variant: 'gated' },
]

const POLICIES = [
  { id: 'staged',    label: 'Staged',                 risk: 'bajo' },
  { id: 'safe',      label: 'Safe',                   risk: 'bajo' },
  { id: 'confirm',   label: 'Apply con confirmación', risk: 'medio' },
  { id: 'dry-run',   label: 'Dry-run primero',        risk: 'mínimo' },
]

function KitButton({ id, title, subtitle, active, onClick, accent }) {
  return (
    <button
      type="button"
      className={`kit ${active ? 'is-active' : ''} ${accent ? `kit-${accent}` : ''}`}
      data-kit={id}
      onClick={onClick}
      aria-pressed={active}
    >
      <b>{title}</b>
      <span>{subtitle}</span>
    </button>
  )
}

function Picker({ label, options, currentId, onPick, renderOption }) {
  return (
    <div className="kit-picker" role="listbox" aria-label={label}>
      <span className="kit-picker-label">{label}</span>
      <div className="kit-picker-options">
        {options.map((opt) => {
          const value = typeof opt === 'string' ? opt : opt.id
          const labelOpt = typeof opt === 'string' ? opt : opt.label
          const active = value === currentId
          return (
            <button
              key={value}
              type="button"
              className={`kit-picker-option ${active ? 'is-active' : ''}`}
              role="option"
              aria-selected={active}
              onClick={() => onPick(opt)}
            >
              {renderOption ? renderOption(opt) : labelOpt}
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default function SessionKit({ kit, summary, dispatch, onToggleInspector, inspectorOpen, onOpenFullManager, compact }) {
  const { push } = useToast()
  const [picker, setPicker] = useState(null)

  function pickPipeline(opt) {
    dispatch.setPipeline(typeof opt === 'string' ? { id: opt, label: opt, variant: 'staged' } : opt)
    push(`Pipeline activo: ${opt.label || opt}`)
    setPicker(null)
  }

  function pickPolicy(opt) {
    dispatch.setPolicy(typeof opt === 'string' ? { id: opt, label: opt, risk: 'bajo' } : opt)
    push(`Política aplicada: ${opt.label || opt}`)
    setPicker(null)
  }

  function pickSimulation(mode) {
    dispatch.setSimulation(mode)
    push(`Simulación: ${mode}`)
    setPicker(null)
  }

  function pickCatalog(mode) {
    dispatch.setCatalog(mode)
    push(`Catálogo: ${mode}`)
    setPicker(null)
  }

  return (
      <section className={`session-kit ${compact ? 'is-compact' : ''}`} aria-label="Equipamiento de la sesión">
      <div className="session-kit-title">
        <span>Sesión equipada</span>
        <small>{summary.installationLabel} · {summary.modelLabel}</small>
      </div>

      <div className="session-kit-row">
        <KitButton
          id="installation"
          title={kit.installation?.label || 'BAGO local'}
          subtitle={`${kit.installation?.version || getUiConfig().version} · ${kit.installation?.status || 'ready'}`}
          active
          onClick={() => push(`Instalación fija: BAGO local ${getUiConfig().version}`)}
        />
        <KitButton
          id="model"
          title={kit.model?.label || kit.model?.id || 'llama3.2:3b'}
          subtitle={kit.model?.provider || 'ollama · local'}
          active
          onClick={() => push('Modelo activo: ' + (kit.model?.label || kit.model?.id))}
        />
        <KitButton
          id="pipeline"
          title={kit.pipeline?.label || 'Code Forge'}
          subtitle={kit.pipeline?.variant || 'staged'}
          active={picker === 'pipeline'}
          onClick={() => setPicker(picker === 'pipeline' ? null : 'pipeline')}
        />
        <KitButton
          id="policy"
          title={kit.policy?.label || 'Staged'}
          subtitle={`riesgo: ${kit.policy?.risk || 'bajo'}`}
          active={picker === 'policy'}
          onClick={() => setPicker(picker === 'policy' ? null : 'policy')}
        />
        <KitButton
          id="pieces"
          title={summary.piecesLabel}
          subtitle="registradas"
          onClick={() => push('Ver lista de piezas en la conversación con /node pieces')}
        />
        <KitButton
          id="simulation"
          title={`Simulación: ${kit.simulation?.mode || 'off'}`}
          subtitle="estado runtime"
          active={picker === 'simulation'}
          onClick={() => setPicker(picker === 'simulation' ? null : 'simulation')}
        />
        <KitButton
          id="catalog"
          title={`Catálogo: ${kit.catalog?.mode || 'off'}`}
          subtitle="scripts permitidos"
          active={picker === 'catalog'}
          onClick={() => setPicker(picker === 'catalog' ? null : 'catalog')}
        />
        <KitButton
          id="inspector"
          title={inspectorOpen ? 'Inspector visible' : 'Inspector oculto'}
          subtitle="detalle del nodo"
          accent={inspectorOpen ? 'primary' : ''}
          onClick={onToggleInspector}
        />
        <KitButton
          id="manager"
          title="Gestor completo"
          subtitle="iframe"
          onClick={onOpenFullManager}
        />
      </div>

      {picker === 'pipeline' ? (
        <Picker
          label="Pipeline activa"
          options={PIPELINES}
          currentId={kit.pipeline?.id}
          onPick={pickPipeline}
        />
      ) : null}

      {picker === 'policy' ? (
        <Picker
          label="Política de ejecución"
          options={POLICIES}
          currentId={kit.policy?.id}
          onPick={pickPolicy}
          renderOption={(opt) => <>{opt.label} <em>· {opt.risk}</em></>}
        />
      ) : null}

      {picker === 'simulation' ? (
        <Picker
          label="Modo de simulación"
          options={['off', 'shadow', 'replay']}
          currentId={kit.simulation?.mode || 'off'}
          onPick={pickSimulation}
        />
      ) : null}

      {picker === 'catalog' ? (
        <Picker
          label="Modo de catálogo"
          options={['off', 'allow', 'strict']}
          currentId={kit.catalog?.mode || 'off'}
          onPick={pickCatalog}
        />
      ) : null}
    </section>
  )
}
