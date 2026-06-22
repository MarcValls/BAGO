import { useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { useInstallations } from '../useBagoData'

const SV_VARIANT = { alive: 'ok', dead: 'danger' }

export default function InstallationsView({ context, onSetContext, onOpenTerminal, onAction }) {
  const { data, loading, error } = useInstallations()
  const [selected, setSelected] = useState(null)
  const [filter, setFilter] = useState('Todas')

  const allInstalls = data?.installations || []
  const installations = allInstalls.filter((i) => i.exists)
  const FILTER_FN = {
    Todas: () => true,
    Activas: (i) => i.supervisor_alive,
    Inactivas: (i) => !i.supervisor_alive,
    Faltan: (i) => !i.exists,
  }
  const rows = filter === 'Faltan' ? allInstalls.filter(FILTER_FN.Faltan) : installations.filter(FILTER_FN[filter] || (() => true))
  const install = rows.find((i) => i.path === selected) || rows[0] || null

  function select(path) {
    setSelected(path)
    onSetContext((c) => ({ ...c, install: path }))
  }

  if (loading) return <section className="cp-view cp-view-active"><div className="cp-loading">Cargando instalaciones…</div></section>
  if (error) return <section className="cp-view cp-view-active"><div className="cp-error">Error: {error}</div></section>

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-seg">
          {['Todas', 'Activas', 'Inactivas', 'Faltan'].map((label) => (
            <button key={label} type="button" className={`cp-seg-btn ${filter === label ? 'is-active' : ''}`} onClick={() => setFilter(label)}>{label}</button>
          ))}
        </div>
        <button type="button" className="cp-btn cp-btn-primary" onClick={() => onAction?.('register')}>
          <Icon name="plus" /> Registrar
        </button>
      </div>

      <div className="cp-install-layout">
        <div className="cp-table-wrap">
          <ViewState empty={!rows.length} emptyLabel="Sin instalaciones para este filtro">
            <table className="cp-table">
              <thead>
                <tr><th>Instalacion</th><th>Version</th><th>Modo</th><th>Supervisor</th><th>Path</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((inst) => {
                  const label = inst.path.split(/[\\\/]/).pop() || inst.path
                  return (
                    <tr key={inst.path} className={selected === inst.path ? 'is-selected' : ''} onClick={() => select(inst.path)} style={{ cursor: 'pointer' }}>
                      <td><b>{label}</b><div className="cp-path">{inst.description}</div></td>
                      <td>{inst.version || '—'}</td>
                      <td><Badge variant="neutral">{inst.mode}</Badge></td>
                      <td><Badge variant={SV_VAR(inst)}>{inst.supervisor_alive ? 'alive' : 'dead'}</Badge></td>
                      <td><div className="cp-path">{inst.path}</div></td>
                      <td>
                        <button type="button" className="cp-small-btn" onClick={(e) => { e.stopPropagation(); onOpenTerminal?.(inst.path) }}>Terminal</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </ViewState>
        </div>

        {install && (
          <aside className="cp-card cp-detail-panel">
            <div className="cp-section-title">{install.path.split(/[\\\/]/).pop() || install.path}</div>
            <div className="cp-kv"><span>Path</span><b>{install.path}</b></div>
            <div className="cp-kv"><span>Version</span><b>{install.version || '—'}</b></div>
            <div className="cp-kv"><span>Modo</span><Badge variant="neutral">{install.mode}</Badge></div>
            <div className="cp-kv"><span>Supervisor</span><span style={{ color: install.supervisor_alive ? 'var(--ok)' : 'var(--danger)' }}>{install.supervisor_alive ? 'Activo' : 'Muerto'}</span></div>
            <div className="cp-kv"><span>Tag</span><span>{install.tag || '—'}</span></div>
            <div className="cp-kv"><span>Cli</span><span>{install.has_cli ? '✓' : '✗'}</span></div>
            <div className="cp-kv"><span>Supervisor script</span><span>{install.has_supervisor ? '✓' : '✗'}</span></div>
            {install.supervisor_state && (
              <div className="cp-kv"><span>PID</span><span>{install.supervisor_state.pid || '—'}</span></div>
            )}
            <div className="cp-card-foot">
              <button type="button" className="cp-small-btn" onClick={() => onAction?.('reload', install.path)}>Reload</button>
              <button type="button" className="cp-small-btn" onClick={() => onOpenTerminal?.(install.path)}>Abrir</button>
            </div>
          </aside>
        )}
      </div>
    </section>
  )
}

function SV_VAR(inst) {
  return inst.supervisor_alive ? 'ok' : 'danger'
}