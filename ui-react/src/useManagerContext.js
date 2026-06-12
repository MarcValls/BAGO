import { useEffect, useState } from 'react'

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

function isTrustedManagerOrigin(origin) {
  if (origin === 'null') return true
  try {
    const url = new URL(origin)
    return ['http:', 'https:'].includes(url.protocol)
      && ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
  } catch {
    return false
  }
}

function normalizeCount(value) {
  const text = String(value ?? '').trim()
  return /^\d{1,7}$/.test(text) ? text : null
}

function parseMessage(event) {
  try {
    if (window.parent === window || event.source !== window.parent) return null
    if (!isTrustedManagerOrigin(event.origin)) return null
    const { source, type, data } = event.data || {}
    if (source !== 'bago-manager' || !data || typeof data !== 'object') return null
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

      if (msg.type === 'view-changed') {
        const view = String(msg.data.view || '')
        if (!Object.hasOwn(VIEW_LABELS, view)) return
        setContext(prev => ({
          ...prev,
          view,
          viewLabel: VIEW_LABELS[view],
        }))
      }

      if (msg.type === 'store-summary') {
        const installations = normalizeCount(msg.data.installations)
        const pieces = normalizeCount(msg.data.pieces)
        if (installations === null && pieces === null) return
        setContext(prev => ({
          ...prev,
          ...(installations !== null ? { installations } : {}),
          ...(pieces !== null ? { pieces } : {}),
        }))
      }
    }

    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [])

  return context
}
