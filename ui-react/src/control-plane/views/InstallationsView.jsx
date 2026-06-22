import { useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { useInstallations } from '../useBagoData'

export default function InstallationsView({ context, onSetContext, onOpenTerminal, onAction }) {
  const { data, loading, error, refresh } = useInstallations()
  const [selected, setSelected] = useState(context?.install || null)
  const [filter, setFilter] = useState('Todas')

  const allInstalls = data?.installations || []
  const installations = allInstalls.filter((item) => item.exists)
  const filterFn = {
    Todas: () => true,
    Activas: (item) => item.supervisor_alive,
    Inactivas: (item) => !item.supervisor_alive,
    Faltan: (item) => !item.exists,
  }
  const rows = filter === 'Faltan'
    ? allInstalls.filter(filterFn.Faltan)
    : installations.filter(filterFn[filter] || (() => true))
  const install = rows.find((item) => item.path === selected)
    || rows.find((item) => item.path === context?.install)
    || rows[0]
    || null

  function select(path) {
    setSelected(path)
    onSetContext((current) => ({ ...current, install: path }))
  }

  async function perform(type, payload) {
    const result = await onAction?.(type, payload)
    if (result !== null) await refresh()
    return result
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
        <button type="button" className="cp-btn" onClick={refresh}>Escanear</button>
        <button type="button" className="cp-btn cp-btn-primary" onClick={() => perform('register')}>
          <Icon name="plus" /> Registrar por rol
        </button>
      </div>

      <div className="cp-install-layout">
        <div className="cp-table-wrap">
          <ViewState empty={!rows.length} emptyLabel="Sin instalaciones para este filtro">
            <table className="cp-table">
              <thead>
                <tr><th>Instalación</th><th>Versión</th><th>Modo</th><th>Supervisor</th><th>Roles</th><th /></tr>
              </thead>
              <tbody>
                {rows.map((item) => {
                  const label = item.path.split(/[\\/]/).pop() || item.path
                  const roles = item.selection_roles || []
                  return (
                    <tr key={item.path} className={install?.path === item.path ? 'is-selected' : ''} onClick={() => select(item.path)} style={{ cursor: 'pointer' }}>
                      <td><b>{label}</b><div className="cp-path">{item.path}</div></td>
                      <td>{item.version || '—'}</td>
                      <td><Badge variant="neutral">{item.mode}</Badge></td>
                      <td><Badge variant={item.supervisor_alive ? 'ok' : 'danger'}>{item.supervisor_alive ? 'alive' : 'dead'}</Badge></td>
                      <td><div className="cp-path">{roles.length ? roles.join(', ') : 'sin rol'}</div></td>
                      <td>
                        <button type="button" className="cp-small-btn" onClick={(event) => { event.stopPropagation(); onOpenTerminal?.(item.path) }}>Terminal</button>
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
            <div className="cp-section-title">{install.path.split(/[\\/]/).pop() || install.path}</div>
            <div className="cp-kv"><span>Path</span><b>{install.path}</b></div>
            <div className="cp-kv"><span>Versión</span><b>{install.version || '—'}</b></div>
            <div className="cp-kv"><span>Modo</span><Badge variant="neutral">{install.mode}</Badge></div>
            <div className="cp-kv"><span>Supervisor</span><span style={{ color: install.supervisor_alive ? 'var(--ok)' : 'var(--danger)' }}>{install.supervisor_alive ? 'Activo' : 'Detenido'}</span></div>
            <div className="cp-kv"><span>Tag</span><span>{install.tag || '—'}</span></div>
            <div className="cp-kv"><span>CLI</span><span>{install.has_cli ? '✓' : '✗'}</span></div>
            <div className="cp-kv"><span>Supervisor script</span><span>{install.has_supervisor ? '✓' : '✗'}</span></div>
            {install.supervisor_state ? <div className="cp-kv"><span>PID</span><span>{install.supervisor_state.pid || '—'}</span></div> : null}

            <div className="cp-section-title">Rol operativo</div>
            <div className="cp-card-foot">
              {['active', 'dev', 'launch'].map((role) => (
                <button
                  key={role}
                  type="button"
                  className={`cp-small-btn ${(install.selection_roles || []).includes(role) ? 'is-active' : ''}`}
                  onClick={() => perform('set-role', { role, path: install.path })}
                >
                  {role}
                </button>
              ))}
            </div>

            <div className="cp-section-title">Runtime activo</div>
            <div className="cp-card-foot">
              <button type="button" className="cp-small-btn" onClick={() => perform('supervisor-status')}>Estado</button>
              <button type="button" className="cp-small-btn" onClick={() => perform('supervisor-start')}>Iniciar</button>
              <button type="button" className="cp-small-btn" onClick={() => perform('supervisor-stop')}>Detener</button>
              <button type="button" className="cp-small-btn" onClick={() => onOpenTerminal?.(install.path)}>Terminal</button>
              <button type="button" className="cp-small-btn" onClick={() => perform('uninstall', { path: install.path })}>Archivar</button>
            </div>
          </aside>
        )}
      </div>
    </section>
  )
}
