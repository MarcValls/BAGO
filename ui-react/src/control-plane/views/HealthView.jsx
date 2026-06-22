import { Badge, ViewState } from '../components/ui'
import { useManagerHealth } from '../useBagoData'

function StatusRing({ percent }) {
  return (
    <div className="cp-status-ring" style={{ background: `conic-gradient(var(--cp-ok) 0 ${percent}%, var(--cp-line) ${percent}% 100%)` }}>
      <b>{percent}%</b>
    </div>
  )
}

export default function HealthView({ onAction }) {
  const { data, loading, error, refresh } = useManagerHealth()

  const checks = data?.checks || []
  const cards = checks.map((check) => ({
    label: check.name,
    value: check.ok ? 'OK' : 'Fallo',
    percent: check.ok ? 100 : 0,
    note: check.detail || '',
    badge: check.ok ? { text: 'OK', variant: 'ok' } : { text: 'Error', variant: 'danger' },
  }))

  if (data?.runtime_root) {
    cards.unshift({
      label: 'Runtime',
      value: data.runtime_version || '—',
      percent: 100,
      note: data.runtime_root,
      badge: { text: 'Detectado', variant: 'ok' },
    })
  }

  if (data?.manager_version) {
    cards.push({
      label: 'Manager',
      value: data.manager_version,
      percent: 100,
      note: `Release jobs: ${data.release_jobs || 0}`,
      badge: { text: 'Activo', variant: 'cyan' },
    })
  }

  async function perform(type) {
    const result = await onAction?.(type)
    if (result !== null) await refresh()
  }

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-section-title">Salud y supervisor</div>
        <button type="button" className="cp-btn" onClick={refresh}>Diagnosticar</button>
        <button type="button" className="cp-btn" onClick={() => perform('supervisor-status')}>Estado</button>
        <button type="button" className="cp-btn" onClick={() => perform('supervisor-start')}>Iniciar</button>
        <button type="button" className="cp-btn" onClick={() => perform('supervisor-stop')}>Detener</button>
        <button type="button" className="cp-btn" onClick={() => perform('cleanup-zombies')}>Limpiar procesos</button>
      </div>

      {loading ? <div className="cp-loading">Diagnosticando…</div> :
       error ? <div className="cp-error">Error: {error}</div> :
       <ViewState empty={!cards.length} emptyLabel="Sin métricas de salud">
         <div className="cp-health-grid">
           {cards.map((item) => (
             <div className="cp-card cp-health-card" key={item.label}>
               <div className="cp-health-top">
                 <div>
                   <div className="cp-kpi-label">{item.label}</div>
                   <div className="cp-piece-id">{item.value}</div>
                 </div>
                 {item.badge ? <Badge variant={item.badge.variant}>{item.badge.text}</Badge> : <StatusRing percent={item.percent} />}
               </div>
               <div className="cp-piece-desc">{item.note}</div>
               <div className="cp-bar"><i style={{ width: `${item.percent}%` }} /></div>
             </div>
           ))}
         </div>
       </ViewState>}
    </section>
  )
}
