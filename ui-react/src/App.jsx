import { useState } from 'react'
import DesktopView from './components/DesktopView'
import SlashMenu from './components/SlashMenu'
import TerminalView from './components/TerminalView'
import { useBagoControl } from './useBagoControl'

export default function App() {
  const control = useBagoControl()
  const [showMenu, setShowMenu] = useState(true)

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>BAGO Control Dual</h1>
          <p>Mismo backend, mismo bus de control, dos superficies React.</p>
          <p className="topbar-note">{control.simulation?.mode_note || 'Shadow en modo observador: sin autoridad autónoma todavía.'}</p>
          <p className="topbar-note">RL bridge: {control.rl?.mode || 'unknown'} · ejecuta acciones: {control.rl?.can_execute ? 'sí' : 'no'}</p>
        </div>
        <div className="topbar-actions">
          <label>
            Vista
            <select value={control.mode} onChange={(event) => control.setMode(event.target.value)}>
              <option value="terminal">Terminal</option>
              <option value="desktop">Escritorio</option>
            </select>
          </label>
          <label>
            Simulación
            <select value={control.simulation?.mode || 'shadow'} onChange={(event) => control.setSimulationMode(event.target.value)}>
              <option value="shadow">shadow</option>
              <option value="off">off</option>
              <option value="canary">canary (future)</option>
              <option value="full">full (future)</option>
            </select>
          </label>
          <label>
            RL bridge
            <select value={control.rl?.mode || 'shadow'} onChange={(event) => control.setRlShadow(event.target.value === 'shadow')}>
              <option value="shadow">shadow</option>
              <option value="off">off</option>
            </select>
          </label>
          <label>
            Catálogo
            <select value={control.catalog?.mode || 'all'} onChange={(event) => control.setCatalogMode(event.target.value)}>
              <option value="all">all</option>
              <option value="available-only">available-only</option>
            </select>
          </label>
          <button onClick={() => setShowMenu((current) => !current)} disabled={control.busy}>
            {showMenu ? 'Ocultar menú /' : 'Mostrar menú /'}
          </button>
          <button onClick={control.refresh} disabled={control.busy}>Actualizar</button>
        </div>
      </header>

      {control.error ? <div className="error-banner">{control.error}</div> : null}

      {showMenu ? <SlashMenu control={control} menu={control.menu} /> : null}

      {control.mode === 'terminal' ? (
        <TerminalView control={control} />
      ) : (
        <DesktopView control={control} />
      )}
    </main>
  )
}
