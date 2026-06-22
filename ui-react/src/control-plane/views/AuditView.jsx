import { useState } from 'react'
import { Badge, ViewState } from '../components/ui'
import { useEventLedger, useBagoAudit, useProjectAudit } from '../useBagoData'

const FILTERS = ['Todo', 'bago', 'project', 'release']
const STATUS_VARIANT = { info: 'ok', warn: 'warn', error: 'danger', high: 'danger', medium: 'warn', low: 'cyan' }

export default function AuditView({ onAction }) {
  const { data: events, loading: evLoad, error: evErr } = useEventLedger(60)
  const { data: bagoAuditData, loading: baLoad } = useBagoAudit()
  const { data: projAuditData, loading: paLoad } = useProjectAudit()
  const [filter, setFilter] = useState('Todo')
  const [open, setOpen] = useState(null)

  const eventList = Array.isArray(events) ? events : []
  const bagoFindings = bagoAuditData?.findings || []
  const projFindings = projAuditData?.findings || []
  const allFindings = [...bagoFindings, ...projFindings]

  const rows = filter === 'Todo' ? [...eventList, ...allFindings.map(f => ({ scope: f.scope, action: f.code, detail: f.message, source: f.file, severity: f.severity }))]
    : filter === 'project' ? projFindings.map(f => ({ scope: 'project', action: f.code, detail: f.message, source: f.file, severity: f.severity }))
    : filter === 'bago' ? bagoFindings.map(f => ({ scope: 'bago', action: f.code, detail: f.message, source: f.file, severity: f.severity }))
    : eventList.filter((e) => (e.scope || '').toLowerCase().includes(filter.toLowerCase()))

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-seg">
          {FILTERS.map((label) => (
            <button key={label} type="button" className={`cp-seg-btn ${filter === label ? 'is-active' : ''}`} onClick={() => setFilter(label)}>{label}</button>
          ))}
        </div>
        <button type="button" className="cp-btn" onClick={() => onAction?.('export-audit')}>Exportar</button>
      </div>

      {evLoad && baLoad && paLoad ? <div className="cp-loading">Cargando auditoria…</div> :
       evErr ? <div className="cp-error">Error: {evErr}</div> :
       <ViewState empty={!rows.length} emptyLabel="Sin entradas para este filtro">
         {rows.map((entry, i) => {
           const key = entry.action || entry.code || i
           const sev = entry.severity || 'info'
           return (
             <div key={key} className={`cp-audit-entry ${open === key ? 'is-open' : ''}`}>
               <button type="button" className="cp-audit-head" onClick={() => setOpen((c) => c === key ? null : key)}>
                 <span className={`cp-badge cp-badge-${STATUS_VARIANT[sev] || 'neutral'}`}>{sev.toUpperCase()}</span>
                 <b>{entry.action || entry.code}</b>
                 <span>{entry.detail || entry.message}</span>
                 <span className="cp-event-time">{entry.scope || entry.source || ''}</span>
               </button>
               <div className="cp-audit-body">
                 <p><b>Scope:</b> {entry.scope || '—'}</p>
                 <p><b>Detalle:</b> {entry.detail || entry.message || '—'}</p>
                 {entry.source && <p><b>Fuente:</b> {entry.source}</p>}
               </div>
             </div>
           )
         })}
       </ViewState>}
    </section>
  )
}