import { useEffect, useState } from 'react'
import { useToast } from './Toast'
import { getUiConfig } from '../useUiConfig'

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
  const [view, setView] = useState(managerContext?.view || 'bago')
  const [iframeUrl, setIframeUrl] = useState(null)
  const [iframeReady, setIframeReady] = useState(false)
  const { push } = useToast()

  useEffect(() => {
    const api = typeof window !== 'undefined' ? window.bagoElectron : null
    if (api && typeof api.getManagerUrl === 'function') {
      api.getManagerUrl()
        .then((url) => {
          if (url) setIframeUrl(String(url))
          setIframeReady(true)
        })
        .catch(() => setIframeReady(true))
    } else {
      setIframeReady(true)
    }
  }, [])

  useEffect(() => {
    if (managerContext?.view) setView(managerContext.view)
  }, [managerContext?.view])

  const views = [
    { id: 'bago',          label: 'Chat',          hint: 'Volver a la conversación' },
    { id: 'installations', label: 'Instalaciones', hint: 'Versiones de BAGO activas' },
    { id: 'pieces',        label: 'Piezas',        hint: 'Componentes y parches' },
    { id: 'patch',         label: 'Patch Bay',     hint: 'Inyectar modificaciones' },
    { id: 'matrix',        label: 'Matriz',        hint: 'Compatibilidad cruzada' },
    { id: 'releases',      label: 'Releases',      hint: 'Versiones publicadas' },
    { id: 'jobs',          label: 'Trabajos',      hint: 'Tareas en curso' },
    { id: 'sessions',      label: 'Sesiones',      hint: 'Historial activo' },
    { id: 'system',        label: 'Sistema',       hint: 'Runtime y salud' },
    { id: 'health',        label: 'Salud',         hint: 'Diagnóstico' },
    { id: 'audit',         label: 'Auditoría',     hint: 'Trazas inmutables' },
  ]

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
            push('Gestor colapsado — chat como pieza central')
          }}
          aria-label="Cerrar gestor"
        >
          ✕
        </button>
      </header>

      <nav className="overlay-tabs" aria-label="Vistas del Gestor">
        {views.map((entry) => (
          <button
            key={entry.id}
            type="button"
            className={`overlay-tab ${entry.id === view ? 'is-active' : ''}`}
            onClick={() => {
              setView(entry.id)
              push(`Vista gestor: ${entry.label}`)
            }}
            aria-pressed={entry.id === view}
            title={entry.hint}
          >
            {entry.label}
          </button>
        ))}
      </nav>

      <div className="overlay-body">
        {iframeReady && iframeUrl ? (
          <iframe
            key={view}
            src={iframeUrl}
            title={`BAGO · ${VIEW_LABELS[view] || view}`}
            className="overlay-iframe"
            sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-popups"
          />
        ) : (
          <div className="overlay-placeholder">
            <div className="overlay-placeholder-mark">{VIEW_LABELS[view]?.[0] || 'B'}</div>
            <strong>{VIEW_LABELS[view] || view}</strong>
            <p>
              {kit.installation?.label || 'BAGO local'} ({kit.installation?.version || getUiConfig().version}) ·
              {' '}{kit.model?.label || 'llama3.2:3b'} ·
              {' '}pipeline {kit.pipeline?.label || 'Code Forge'}
            </p>
            <p>claims {inspectorSummary.claimsOk}/{inspectorSummary.claimsTotal} · {inspectorSummary.state}</p>
            <small>
              Lanzar el .exe para acceder al iframe del Gestor completo. Esta vista previa
              mantiene el chat como pieza central y resume el estado actual de la sesión.
            </small>
          </div>
        )}
      </div>
    </aside>
  )
}