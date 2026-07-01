import { Badge, ViewState } from '../components/ui'
import { useInstallations, useReleases, useEventLedger } from '../useBagoData'

export default function DashboardView({ context, onSetContext, onAction }) {
  const { data: instData, loading: instLoading, error: instError, refresh: refreshInstallations } = useInstallations()
  const { data: releases, loading: relLoading, refresh: refreshReleases } = useReleases()
  const { data: events, refresh: refreshEvents } = useEventLedger(20)

  const installations = instData?.installations?.filter((i) => i.exists) || []
  const summary = instData?.summary || {}
  const releasesList = Array.isArray(releases) ? releases.slice(0, 5) : []
  const eventList = Array.isArray(events) ? events.slice(0, 8) : []

  function select(installPath) {
    onSetContext((c) => ({ ...c, install: installPath }))
  }

  function refreshAll() {
    refreshInstallations?.()
    refreshReleases?.()
    refreshEvents?.()
  }

  const kpi = [
    { label: 'Instalaciones', value: summary.existing ?? '—', sub: `${summary.with_supervisor_alive ?? 0} con supervisor` },
    { label: 'Releases', value: releasesList.length || '—', sub: releasesList[0]?.tag_name || 'Sin releases' },
    { label: 'Eventos', value: eventList.length, sub: 'ledger reciente' },
    { label: 'Runtime', value: instData?.selection?.roles?.active ? 'Activo' : '—', sub: instData?.selection?.roles?.active || 'No seleccionado' },
  ]

  if (instLoading) return <section className="cp-view cp-view-active"><div className="cp-loading">Cargando datos reales…</div></section>
  if (instError) return <section className="cp-view cp-view-active"><div className="cp-error">Error: {instError}</div></section>

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-section-title">Dashboard operativo</div>
        <div className="cp-toolbar-actions">
          <button type="button" className="cp-btn" onClick={refreshAll}>Refrescar</button>
          <button type="button" className="cp-btn" onClick={() => onAction?.('open-installations')}>Instalaciones</button>
          <button type="button" className="cp-btn" onClick={() => onAction?.('open-health')}>Salud</button>
          <button type="button" className="cp-btn" onClick={() => onAction?.('open-releases')}>Releases</button>
          <button type="button" className="cp-btn" onClick={() => onAction?.('open-nodes')}>Nodos</button>
        </div>
      </div>

      <div className="cp-grid4">
        {kpi.map((item) => (
          <div className="cp-card cp-kpi" key={item.label}>
            <div className="cp-kpi-label">{item.label}</div>
            <div className="cp-kpi-value">{item.value}</div>
            <div className="cp-kpi-sub">{item.sub}</div>
          </div>
        ))}
      </div>

      <div className="cp-dashboard-grid">
        <div className="cp-card">
          <div className="cp-section-head">
            <div><div className="cp-section-title">Instalaciones</div></div>
            <Badge variant="ok">{summary.with_supervisor_alive ?? 0} vivas</Badge>
          </div>
          <ViewState empty={!installations.length} emptyLabel="Sin instalaciones detectadas">
            <div className="cp-install-list">
              {installations.map((inst) => {
                const label = inst.path.split(/[\\\/]/).pop() || inst.path
                return (
                  <div
                    key={inst.path}
                    className={`cp-install-row ${context.install === inst.path ? 'is-selected' : ''}`}
                    onClick={() => select(inst.path)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        select(inst.path)
                      }
                    }}
                  >
                    <div className="cp-install-row-main">
                      <div className="cp-install-name">{label}</div>
                      <div className="cp-path">{inst.path}</div>
                    </div>
                    <div className="cp-install-row-meta">
                      <Badge variant={inst.supervisor_alive ? 'ok' : 'danger'}>{inst.supervisor_alive ? 'alive' : 'dead'}</Badge>
                      <Badge variant="cyan">{inst.version || '—'}</Badge>
                      <button
                        type="button"
                        className="cp-small-btn"
                        onClick={(e) => { e.stopPropagation(); onAction?.('set-active-install', inst.path) }}
                      >
                        Activa
                      </button>
                      <button
                        type="button"
                        className="cp-small-btn"
                        onClick={(e) => { e.stopPropagation(); onAction?.('open-install-terminal', inst.path) }}
                      >
                        Terminal
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </ViewState>
        </div>

        <div className="cp-card cp-quick-graph">
          <div className="cp-section-title">Topologia</div>
          <div className="cp-section-note">{context.install ? context.install.split(/[\\\/]/).pop() : 'Sin selección'}</div>
          <div className="cp-graph-line cp-graph-line-1" />
          <div className="cp-graph-line cp-graph-line-2" />
          <div className="cp-graph-line cp-graph-line-3" />
          <div className="cp-graph-line cp-graph-line-4" />
          <div className="cp-graph-node cp-graph-node-core">
            {context.install ? context.install.split(/[\\\/]/).pop() : '—'}
            <br />
            <small style={{ color: 'var(--cp-muted)' }}>{installations.find((i) => i.path === context.install)?.version || '—'}</small>
          </div>
          <div className="cp-graph-node cp-graph-node-1">{summary.with_supervisor ?? 0} Supervisors</div>
          <div className="cp-graph-node cp-graph-node-2">{summary.total_paths ?? 0} Paths</div>
          <div className="cp-graph-node cp-graph-node-3">{eventList.length} Events</div>
          <div className="cp-graph-node cp-graph-node-4">{releasesList.length} Releases</div>
        </div>
      </div>

      <div className="cp-lower-grid">
        <div className="cp-card">
          <div className="cp-section-head"><div className="cp-section-title">Releases</div></div>
          <ViewState empty={!releasesList.length} emptyLabel="Sin releases disponibles">
            {releasesList.map((rel) => (
              <div className="cp-release-row" key={rel.tag_name}>
                <div className="cp-release-main">
                  <div className="cp-release-ver">{rel.tag_name}</div>
                  <div className="cp-release-meta">{rel.name || ''} · {rel.assets?.length || 0} assets</div>
                </div>
                <Badge variant={rel.prerelease ? 'warn' : 'ok'}>{rel.prerelease ? 'Beta' : 'Stable'}</Badge>
              </div>
            ))}
          </ViewState>
        </div>

        <div className="cp-card">
          <div className="cp-section-head"><div className="cp-section-title">Auditoria</div></div>
          <ViewState empty={!eventList.length} emptyLabel="Sin eventos recientes">
            <div className="cp-timeline">
              {eventList.map((event, index) => (
                <div className="cp-event" key={index}>
                  <span className="cp-event-dot" style={{ background: `var(--cp-${event.severity === 'warn' ? 'warn' : 'brand'})` }} />
                  <div className="cp-event-main">
                    <div className="cp-event-title">{event.action}</div>
                    <div className="cp-event-sub">{event.detail}</div>
                  </div>
                  <span className="cp-event-time">{event.scope}</span>
                </div>
              ))}
            </div>
          </ViewState>
        </div>
      </div>
    </section>
  )
}
