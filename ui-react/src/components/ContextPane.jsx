import { useEffect, useState } from 'react'
import { chatApi } from '../api'

const VIEWS = [
  { id: 'routes', label: 'Rutas', icon: '⊕' },
  { id: 'memory', label: 'Memoria', icon: '◇' },
  { id: 'schedule', label: 'Agenda', icon: '◷' },
  { id: 'subagents', label: 'Agentes', icon: '◐' },
  { id: 'providers', label: 'Providers', icon: '▣' },
  { id: 'router', label: 'Router', icon: '↻' },
  { id: 'simulation', label: 'Simul', icon: '◌' },
]

function RoutesView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    chatApi.listRoutes().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="ctx-error">{error}</div>
  if (!data) return <div className="ctx-loading">Cargando rutas…</div>

  const routes = data.routes || data
  return (
    <div className="ctx-routes">
      <table className="ctx-table">
        <thead>
          <tr><th>Método</th><th>Ruta</th><th>Módulo</th><th>Handler</th></tr>
        </thead>
        <tbody>
          {Array.isArray(routes) ? routes.map((r, i) => (
            <tr key={i}>
              <td className={`ctx-method ctx-method-${(r.method || 'GET').toLowerCase()}`}>{r.method || 'GET'}</td>
              <td>{r.path}</td>
              <td>{r.module || '—'}</td>
              <td>{r.handler || '—'}</td>
            </tr>
          )) : Object.entries(routes).map(([path, info]) => (
            <tr key={path}>
              <td className="ctx-method ctx-method-get">GET</td>
              <td>{path}</td>
              <td>{info.module || '—'}</td>
              <td>{info.handler || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function MemoryView() {
  const [scope, setScope] = useState('user')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    chatApi.listMemory(scope).then(setData).catch((e) => setError(e.message))
  }, [scope])

  return (
    <div className="ctx-memory">
      <div className="ctx-scope-tabs">
        <button className={scope === 'user' ? 'active' : ''} onClick={() => setScope('user')}>Usuario</button>
        <button className={scope === 'project' ? 'active' : ''} onClick={() => setScope('project')}>Proyecto</button>
      </div>
      {error && <div className="ctx-error">{error}</div>}
      {!data && !error && <div className="ctx-loading">Cargando memoria…</div>}
      {data?.entries && (
        <ul className="ctx-memory-list">
          {data.entries.map((entry, i) => (
            <li key={i} className="ctx-memory-item">
              <span className="ctx-memory-name">{entry.name || entry.title || '—'}</span>
              <span className="ctx-memory-desc">{entry.description || ''}</span>
            </li>
          ))}
        </ul>
      )}
      {data?.entries?.length === 0 && <div className="ctx-empty">Sin memorias registradas</div>}
    </div>
  )
}

function ScheduleView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    chatApi.listSchedule().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="ctx-error">{error}</div>
  if (!data) return <div className="ctx-loading">Cargando agenda…</div>

  const jobs = data.jobs || data.schedule || []
  return (
    <div className="ctx-schedule">
      {jobs.length === 0 ? (
        <div className="ctx-empty">Sin tareas programadas</div>
      ) : (
        <ul className="ctx-schedule-list">
          {jobs.map((job, i) => (
            <li key={i} className="ctx-schedule-item">
              <span className="ctx-schedule-id">{job.id || job.name || `job-${i}`}</span>
              <span className="ctx-schedule-when">{job.cron || job.when || '—'}</span>
              <span className="ctx-schedule-prompt">{job.prompt || ''}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function SubagentsView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    chatApi.listSubagents().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="ctx-error">{error}</div>
  if (!data) return <div className="ctx-loading">Cargando agentes…</div>

  const agents = data.agents || data.catalogue || []
  return (
    <div className="ctx-subagents">
      {agents.length === 0 ? (
        <div className="ctx-empty">Sin subagentes registrados</div>
      ) : (
        <ul className="ctx-subagents-list">
          {agents.map((agent, i) => (
            <li key={i} className="ctx-subagent-item">
              <span className="ctx-subagent-name">{agent.name || agent.id || '—'}</span>
              <span className="ctx-subagent-desc">{agent.description || ''}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ProvidersView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    chatApi.listProviders().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="ctx-error">{error}</div>
  if (!data) return <div className="ctx-loading">Cargando providers…</div>

  const providers = data.providers || []
  return (
    <div className="ctx-providers">
      <div className="ctx-providers-mode">Modo catálogo: {data.mode || 'all'}</div>
      <ul className="ctx-providers-list">
        {providers.map((p, i) => (
          <li key={i} className="ctx-provider-item">
            <span className={`ctx-provider-dot ${p.available ? 'on' : 'off'}`}>●</span>
            <span className="ctx-provider-name">{p.name || p.id || '—'}</span>
            {p.model_count != null && (
              <span className="ctx-provider-count">{p.model_count} modelos</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

function RouterView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  async function load() {
    try {
      const d = await chatApi.listRouter()
      setData(d)
      setError('')
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function toggle(key) {
    try {
      await chatApi.toggleRouterModel(key)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function setAuto(enabled) {
    try {
      await chatApi.setRouterAuto(enabled)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  if (error) return <div className="ctx-error">{error}</div>
  if (!data) return <div className="ctx-loading">Cargando router…</div>

  const entries = data.entries || data.models || []
  const auto = data.auto_switch ?? data.auto

  return (
    <div className="ctx-router">
      <div className="ctx-router-header">
        <label className="ctx-router-auto">
          <input type="checkbox" checked={!!auto} onChange={(e) => setAuto(e.target.checked)} />
          Auto-switch
        </label>
        <button onClick={() => load()}>↻</button>
      </div>
      <ul className="ctx-router-list">
        {entries.map((entry, i) => (
          <li key={i} className={`ctx-router-item ${entry.available ? '' : 'unavailable'} ${entry.selected ? 'selected' : ''}`}>
            <button
              type="button"
              className="ctx-router-toggle"
              onClick={() => toggle(entry.key || entry.model_id || entry.id)}
            >
              {entry.selected ? '◉' : entry.available ? '○' : '✕'}
            </button>
            <span className="ctx-router-model">{entry.wire_name || entry.model_id || entry.model || '—'}</span>
            <span className="ctx-router-provider">{entry.provider}</span>
            {entry.best_for && <span className="ctx-router-best">{entry.best_for}</span>}
          </li>
        ))}
      </ul>
    </div>
  )
}

function SimulationView() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    chatApi.getSimulationStatus().then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="ctx-error">{error}</div>
  if (!data) return <div className="ctx-loading">Cargando simulación…</div>

  return (
    <div className="ctx-simulation">
      <div className="ctx-sim-mode">Modo: <strong>{data.mode || 'shadow'}</strong></div>
      {data.events_count != null && (
        <div className="ctx-sim-stat">{data.events_count} eventos registrados</div>
      )}
      {data.last_event && (
        <div className="ctx-sim-last">{data.last_event}</div>
      )}
    </div>
  )
}

const VIEW_COMPONENTS = {
  routes: RoutesView,
  memory: MemoryView,
  schedule: ScheduleView,
  subagents: SubagentsView,
  providers: ProvidersView,
  router: RouterView,
  simulation: SimulationView,
}

export default function ContextPane({ open, onClose }) {
  const [activeView, setActiveView] = useState('routes')
  const ActiveComponent = VIEW_COMPONENTS[activeView] || RoutesView

  if (!open) return null

  return (
    <aside className="context-pane" role="complementary" aria-label="Panel de contexto">
      <div className="context-pane-tabs">
        {VIEWS.map((view) => (
          <button
            key={view.id}
            type="button"
            className={`context-pane-tab ${activeView === view.id ? 'active' : ''}`}
            onClick={() => setActiveView(view.id)}
            title={view.label}
          >
            <span className="ctx-tab-icon">{view.icon}</span>
            <span className="ctx-tab-label">{view.label}</span>
          </button>
        ))}
        <button type="button" className="context-pane-close" onClick={onClose} title="Cerrar">
          ✕
        </button>
      </div>
      <div className="context-pane-body">
        <ActiveComponent />
      </div>
    </aside>
  )
}