import { useState, useEffect } from 'react'

export default function ManagerView() {
  const [src, setSrc] = useState(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const api = typeof window !== 'undefined' ? window.bagoElectron : null
    if (api && typeof api.getManagerUrl === 'function') {
      api.getManagerUrl()
        .then((url) => {
          if (url) setSrc(String(url))
          setReady(true)
        })
        .catch(() => setReady(true))
    } else {
      setReady(true)
    }
  }, [])

  if (!ready) {
    return (
      <section className="manager-view manager-state">
        <p>Cargando gestor...</p>
      </section>
    )
  }

  if (!src) {
    return (
      <section className="manager-view manager-state">
        <div className="manager-notice">
          <span className="manager-notice-icon">🖥️</span>
          <strong>Gestor de instalaciones</strong>
          <p>Disponible solo desde la aplicación Electron de BAGO.</p>
          <p className="manager-notice-hint">Lanza el .exe para acceder al Gestor, Patch Bay, Releases y más.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="manager-view">
      <iframe
        src={src}
        title="BAGO · Gestor de Instalaciones"
        className="manager-frame"
        sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-popups"
      />
    </section>
  )
}
