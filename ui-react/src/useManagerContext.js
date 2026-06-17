import { useEffect, useState } from 'react'
import { recordInteraction } from './interactionLog'

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

function parseMessage(event) {
  try {
    const { source, type, data } = event.data || {}
    if (source !== 'bago-manager') return null
    return { type, data }
  } catch {
    return null
  }
}

export function useManagerContext() {
  const [context, setContext] = useState(null)

  useEffect(() => {
    function handleMessage(event) {
      const msg = parseMessage(event)
      if (!msg) return
      recordInteraction('manager-postmessage', msg)

      if (msg.type === 'view-changed') {
        setContext(prev => ({
          ...prev,
          view: msg.data.view,
          viewLabel: VIEW_LABELS[msg.data.view] || msg.data.view,
        }))
      }

      if (msg.type === 'store-summary') {
        setContext(prev => ({
          ...prev,
          installations: msg.data.installations,
          pieces: msg.data.pieces,
        }))
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  return context
}
