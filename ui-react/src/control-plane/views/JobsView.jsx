import { useEffect, useState } from 'react'
import { Badge, ViewState } from '../components/ui'
import { useReleaseJobs, useReleaseJobChanges } from '../useBagoData'

const STATUS_VARIANT = {
  queued: 'neutral',
  pending: 'neutral',
  running: 'cyan',
  preparing: 'warn',
  downloading: 'cyan',
  verifying: 'warn',
  staging: 'warn',
  ready: 'ok',
  installing: 'warn',
  done: 'ok',
  completed: 'ok',
  failed: 'danger',
  cancelled: 'neutral',
  'rolling-back': 'warn',
  'rolled-back': 'ok',
}

const ACTIVE_STATES = new Set(['queued', 'pending', 'running', 'preparing', 'downloading-checksum', 'downloading-signature', 'downloading', 'verifying', 'staging', 'installing', 'rolling-back'])
const TERMINAL_STATES = new Set(['ready', 'completed', 'cancelled', 'failed', 'rolled-back'])

export default function JobsView({ onAction }) {
  const { data, loading, error, refresh } = useReleaseJobs()
  const changedJob = useReleaseJobChanges()
  const [selectedId, setSelectedId] = useState('')
  const [logs, setLogs] = useState([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [actionError, setActionError] = useState('')

  const jobs = Array.isArray(data) ? data : (data?.jobs || [])

  useEffect(() => {
    if (changedJob) refresh()
  }, [changedJob, refresh])

  async function perform(action, id) {
    setActionError('')
    const result = await onAction?.('job-action', { action, id })
    if (result !== null) await refresh()
  }

  async function loadLogs(id) {
    setSelectedId(id)
    setLogsLoading(true)
    setActionError('')
    try {
      const rows = await onAction?.('job-logs', { id, limit: 300 })
      setLogs(Array.isArray(rows) ? rows : [])
    } catch (cause) {
      setActionError(cause?.message || String(cause))
      setLogs([])
    } finally {
      setLogsLoading(false)
    }
  }

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-section-title">Jobs en segundo plano</div>
        <button type="button" className="cp-btn" onClick={refresh}>Refrescar</button>
      </div>

      {actionError ? <div className="cp-error">{actionError}</div> : null}

      {loading ? <div className="cp-loading">Cargando jobs…</div> :
       error ? <div className="cp-error">Error: {error}</div> :
       <ViewState empty={!jobs.length} emptyLabel="Sin jobs activos">
         <div className="cp-card">
           {jobs.map((job) => {
             const state = job.state || job.status || '—'
             const progress = Number(job.progress?.percent ?? job.progress ?? 0)
             const title = job.release?.tag_name || job.tag || job.id || 'Job'
             return (
               <div className={`cp-job ${selectedId === job.id ? 'is-selected' : ''}`} key={job.id || title}>
                 <div className="cp-job-title">
                   <span>{title}</span>
                   <Badge variant={STATUS_VARIANT[state] || 'neutral'}>{state}</Badge>
                 </div>
                 <div className="cp-piece-desc">{job.target || job.phase || job.detail || ''}</div>
                 <div className="cp-bar"><i style={{ width: `${Math.max(0, Math.min(100, progress))}%` }} /></div>
                 <div className="cp-card-foot">
                   {ACTIVE_STATES.has(state) ? (
                     <button type="button" className="cp-small-btn" onClick={() => perform('cancel', job.id)}>Cancelar</button>
                   ) : null}
                   {['cancelled', 'failed'].includes(state) ? (
                     <button type="button" className="cp-small-btn" onClick={() => perform('resume', job.id)}>Reanudar</button>
                   ) : null}
                   {state === 'ready' ? (
                     <button type="button" className="cp-small-btn cp-install-release" onClick={() => perform('install', job.id)}>Instalar verificado</button>
                   ) : null}
                   {job.rollback_available ? (
                     <button type="button" className="cp-small-btn" onClick={() => perform('rollback', job.id)}>Rollback</button>
                   ) : null}
                   <button type="button" className="cp-small-btn" onClick={() => loadLogs(job.id)}>Logs</button>
                   {TERMINAL_STATES.has(state) ? (
                     <button type="button" className="cp-small-btn" onClick={() => perform('delete', job.id)}>Archivar</button>
                   ) : null}
                 </div>
                 {job.error ? <div className="cp-error">{job.error}</div> : null}
               </div>
             )
           })}
         </div>
       </ViewState>}

      {selectedId ? (
        <div className="cp-card cp-node-stage">
          <div className="cp-section-head">
            <div className="cp-section-title">Log · {selectedId}</div>
            <button type="button" className="cp-small-btn" onClick={() => loadLogs(selectedId)}>Actualizar</button>
          </div>
          {logsLoading ? <div className="cp-loading">Cargando logs…</div> : (
            <pre className="cp-json-viewer">{logs.length ? logs.map((row) => `${row.timestamp || ''} ${row.level || 'info'} ${row.message || ''}`).join('\n') : 'Log vacío'}</pre>
          )}
        </div>
      ) : null}
    </section>
  )
}
