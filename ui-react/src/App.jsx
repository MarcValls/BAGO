import { useState } from 'react'
import DesktopView from './components/DesktopView'
import TerminalView from './components/TerminalView'
import { useBagoChat } from './useBagoChat'

function Icon({ name }) {
  const paths = {
    chat: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v7a2.5 2.5 0 0 1-2.5 2.5H10l-5 4v-4.5A2.5 2.5 0 0 1 4 12.5z" /><path d="M8 8h8M8 11h5" /></>,
    terminal: <><path d="m7 8 3 3-3 3M12 15h5" /><rect x="3" y="4" width="18" height="16" rx="3" /></>,
    manager: <><path d="M4 7h16M4 12h16M4 17h16" /><circle cx="7" cy="7" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="17" cy="17" r="1" /></>,
    refresh: <><path d="M20 7v5h-5" /><path d="M18.5 16a8 8 0 1 1 1-8l.5 4" /></>,
    sidebarOpen: <><path d="M8 5 3 12l5 7" /><path d="M12 5h9v14h-9" /></>,
    sidebarClosed: <><path d="M16 5 21 12l-5 7" /><path d="M3 5h9v14H3" /></>,
  }

  return <svg aria-hidden="true" viewBox="0 0 24 24">{paths[name]}</svg>
}

function compact(text, limit = 34) {
  const value = String(text || '').replace(/\s+/g, ' ').trim()
  return value.length > limit ? `${value.slice(0, limit - 1).trim()}…` : value
}

function resolveManagerUrl() {
  // P1-03 fix: do NOT hardcode a dev port. Resolve the URL dynamically:
  //   1) When running inside Electron, ask the main process for the URL of
  //      the local Manager window (which may not be on port 4174 at all in
  //      a packaged build).
  //   2) Otherwise, fall back to the relative path so the React app still
  //      works in a plain Vite dev server.
  const api = typeof window !== 'undefined' ? window.bagoElectron : null
  if (api && typeof api.getManagerUrl === 'function') {
    try {
      const resolved = api.getManagerUrl()
      if (resolved) return String(resolved)
    } catch {
      // ignore; we will fall back below
    }
  }
  return 'manager/index.html'
}

export default function App() {
  const control = useBagoChat()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const sessions = control.menu?.sessions || []
  const openManager = () => {
    const url = resolveManagerUrl()
    // file:// URLs must NOT be opened in a new window with noopener because
    // some browsers block the navigation silently. We open relative paths
    // in the same window and only use noopener for http(s) URLs.
    if (/^https?:\/\//i.test(url)) {
      const win = window.open(url, '_blank', 'noopener,noreferrer')
      if (!win) window.location.href = url
    } else {
      window.location.href = url
    }
  }

  return (
    <main className={`app-shell ${sidebarCollapsed ? 'is-sidebar-collapsed' : ''}`}>
      <aside className="app-sidebar">
        <div className="app-brand">
          <span className="brand-symbol">B</span>
          <span className="brand-name">BAGO</span>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() => setSidebarCollapsed((value) => !value)}
            aria-label={sidebarCollapsed ? 'Expandir barra lateral' : 'Colapsar barra lateral'}
            title={sidebarCollapsed ? 'Expandir barra lateral' : 'Colapsar barra lateral'}
          >
            <Icon name={sidebarCollapsed ? 'sidebarOpen' : 'sidebarClosed'} />
          </button>
        </div>

        <nav className="primary-nav" aria-label="Navegación principal">
          <button
            type="button"
            className={control.mode === 'desktop' ? 'active' : ''}
            onClick={() => {
              control.setMode('desktop')
            }}
          >
            <Icon name="chat" />
            Chat
          </button>
          <button
            type="button"
            className={control.mode === 'terminal' ? 'active' : ''}
            onClick={() => {
              control.setMode('terminal')
            }}
          >
            <Icon name="terminal" />
            Terminal
          </button>
          <button
            type="button"
            onClick={openManager}
          >
            <Icon name="manager" />
            Manager
          </button>
        </nav>

        <section className="recent-section">
          <div className="sidebar-label">Recientes</div>
          <div className="recent-list">
            {sessions.slice(0, 10).map((session) => (
              <button
                key={session.sid}
                type="button"
                onClick={() => control.submit(session.command, 'desktop')}
                title={session.command}
              >
                {compact(session.label || session.sid || 'Sesión')}
              </button>
            ))}
            {!sessions.length ? <span className="sidebar-empty">Sin conversaciones guardadas</span> : null}
          </div>
        </section>

        <div className="sidebar-footer">
          <button type="button" onClick={control.refresh} disabled={control.busy}>
            <Icon name="refresh" />
            Actualizar
          </button>
          <div className="runtime-caption">
            <strong>{control.session?.provider || 'BAGO local'}</strong>
            <span>{control.session?.model || 'Sin modelo activo'}</span>
          </div>
        </div>
      </aside>

      <section className="app-workspace">
        {control.error ? <div className="error-banner">{control.error}</div> : null}
        {control.mode === 'desktop' ? <DesktopView control={control} /> : <TerminalView control={control} />}
      </section>
    </main>
  )
}
