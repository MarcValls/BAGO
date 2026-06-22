import { useToast } from './Toast'

const VIEW_LABELS = {
  patch: 'Patch Bay',
  installations: 'Instalaciones',
  matrix: 'Matriz',
  pieces: 'Piezas',
  releases: 'Releases',
  jobs: 'Trabajos',
  sessions: 'Sesiones',
  system: 'Sistema',
  health: 'Salud',
  audit: 'Auditoría',
  bago: 'BAGO Chat',
}

export default function ManagerOverlay({ onClose, managerContext, kit, inspectorSummary }) {
  const { push } = useToast()
  const view = managerContext?.view || 'bago'

  return (
    <aside className="manager-overlay" aria-label="Panel del Gestor">
      <header className="overlay-head">
        <div>
          <strong>Gestor</strong>
          <p>Vista activa: {VIEW_LABELS[view] || view}</p>
        </div>
        <button
          type="button"
          className="overlay-close"
          onClick={() => {
            onClose()
            push('Gestor colapsado — usa el Control Plane lateral')
          }}
          aria-label="Cerrar gestor"
        >
          ✕
        </button>
      </header>

      <div className="overlay-body">
        <div className="overlay-placeholder">
          <div className="overlay-placeholder-mark">{VIEW_LABELS[view]?.[0] || 'B'}</div>
          <strong>{VIEW_LABELS[view] || view}</strong>
          <p>
            {kit.installation?.label || 'BAGO local'} ({kit.installation?.version || '4.7.0'}) ·
            {' '}{kit.model?.label || 'llama3.2:3b'} ·
            {' '}pipeline {kit.pipeline?.label || 'Code Forge'}
          </p>
          <p>claims {inspectorSummary.claimsOk}/{inspectorSummary.claimsTotal} · {inspectorSummary.state}</p>
          <small>
            El Gestor legacy ha sido migrado al Control Plane. Usa la barra lateral
            (Activity Bar) para acceder a Instalaciones, Patch Bay, Nodos, Piezas,
            Releases, Salud y Auditoría.
          </small>
        </div>
      </div>
    </aside>
  )
}
