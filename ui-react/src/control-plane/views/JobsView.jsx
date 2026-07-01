import { useEffect, useMemo, useState } from 'react'
import { Badge, ViewState } from '../components/ui'
import { useReleaseJobs, useReleaseJobChanges } from '../useBagoData'

const STATUS_VARIANT = {
  pending: 'neutral',
  running: 'warn',
  preparing: 'warn',
  ready: 'ok',
  done: 'ok',
  completed: 'ok',
  failed: 'danger',
  cancelled: 'neutral',
  'rolled-back': 'neutral',
}

function getBridge() {
  return typeof window !== 'undefined' ? window.bagoElectron : null
}

function jobKey(job) {
  return job?.id || job?.tag || job?.release?.tag_name || ''
}

function canCancel(job) {
  return !['ready', 'completed', 'cancelled', 'failed', 'rolled-back'].includes(job.status)
}

function canResume(job) {
  return ['cancelled', 'failed'].includes(job.status)
}

function canInstall(job) {
  return job.status === 'ready'
}

function canRollback(job) {
  return !!job.rollback_available
}

export default function JobsView({ onAction }) {
  const { data, loading, error, refresh } = useReleaseJobs()
  const changedJob = useReleaseJobChanges()
  const [selectedIds, setSelectedIds] = useState(() => new Set())
  const [selectedId, setSelectedId] = useState('')
  const [jobLogs, setJobLogs] = useState([])
  const [jobLogError, setJobLogError] = useState('')

  const jobs = Array.isArray(data) ? data : (data?.jobs || [])

  const selectedJobs = useMemo(
    () => jobs.filter((job) => selectedIds.has(jobKey(job))),
    [jobs, selectedIds]
  )

  const selectedJob = useMemo(() => {
    if (selectedId) return jobs.find((job) => jobKey(job) === selectedId) || null
    return selectedJobs[0] || jobs[0] || null
  }, [jobs, selectedId, selectedJobs])

  const actionGroups = useMemo(() => {
    const current = selectedJobs
    return {
      cancel: current.filter(canCancel),
      resume: current.filter(canResume),
      install: current.filter(canInstall),
      rollback: current.filter(canRollback),
    }
  }, [jobs, selectedJobs])

  useEffect(() => {
    if (!changedJob?.id) return
    refresh()
  }, [changedJob, refresh])

  useEffect(() => {
    if (!selectedJob) return
    setSelectedId(jobKey(selectedJob))
  }, [selectedJob])

  async function loadLogs(job) {
    const api = getBridge()
    if (!api?.releaseJobLogs) {
      setJobLogError('Logs no disponibles sin Electron')
      return
    }
    setSelectedId(jobKey(job))
    setJobLogError('')
    try {
      const rows = await api.releaseJobLogs(jobKey(job), 200)
      setJobLogs(Array.isArray(rows) ? rows : [])
    } catch (e) {
      setJobLogs([])
      setJobLogError(e.message)
    }
  }

  async function applyAction(action, items) {
    const api = getBridge()
    if (!api) {
      onAction?.('toast', 'Acción no disponible sin Electron')
      return
    }
    const list = Array.isArray(items) ? items : []
    if (!list.length) {
      onAction?.('toast', 'No hay jobs compatibles para esa acción')
      return
    }
    const runners = {
      cancel: api.cancelReleaseJob?.bind(api),
      resume: api.resumeReleaseJob?.bind(api),
      install: api.installReleaseJob?.bind(api),
      rollback: api.rollbackReleaseJob?.bind(api),
    }
    const runner = runners[action]
      if (!runner) return
    try {
      for (const job of list) {
        await runner(jobKey(job))
      }
      await refresh()
      setSelectedIds((prev) => {
        const next = new Set(prev)
        list.forEach((job) => next.delete(jobKey(job)))
        return next
      })
      onAction?.('toast', `${action} aplicado a ${list.length} job(s)`)
    } catch (e) {
      onAction?.('toast', `Job: ${e.message}`)
    }
  }

  function toggleSelection(jobId, checked) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      const key = String(jobId || '')
      if (checked) next.add(key)
      else next.delete(key)
      return next
    })
  }

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-section-title">Jobs en segundo plano</div>
        <div className="cp-toolbar-actions">
          <button type="button" className="cp-btn" onClick={refresh}>Refrescar</button>
          <button type="button" className="cp-btn" onClick={() => onAction?.('open-releases')}>Releases</button>
        </div>
      </div>

      {loading ? <div className="cp-loading">Cargando jobs…</div> :
       error ? <div className="cp-error">Error: {error}</div> :
       <ViewState empty={!jobs.length} emptyLabel="Sin jobs activos">
         <div className="cp-job-layout">
           <div className="cp-card">
             <div className="cp-job-bulkbar">
               <span className="cp-job-bulkcount">
                 {selectedJobs.length ? `${selectedJobs.length} seleccionados` : 'Selecciona jobs para actuar'}
               </span>
               <div className="cp-row-actions">
                 <button type="button" className="cp-small-btn" onClick={() => applyAction('cancel', actionGroups.cancel)} disabled={!selectedJobs.length || !actionGroups.cancel.length}>
                   Cancelar {selectedJobs.length ? `(${actionGroups.cancel.length})` : ''}
                 </button>
                 <button type="button" className="cp-small-btn" onClick={() => applyAction('resume', actionGroups.resume)} disabled={!selectedJobs.length || !actionGroups.resume.length}>
                   Reanudar {selectedJobs.length ? `(${actionGroups.resume.length})` : ''}
                 </button>
                 <button type="button" className="cp-small-btn" onClick={() => applyAction('install', actionGroups.install)} disabled={!selectedJobs.length || !actionGroups.install.length}>
                   Instalar {selectedJobs.length ? `(${actionGroups.install.length})` : ''}
                 </button>
                 <button type="button" className="cp-small-btn" onClick={() => applyAction('rollback', actionGroups.rollback)} disabled={!selectedJobs.length || !actionGroups.rollback.length}>
                   Rollback {selectedJobs.length ? `(${actionGroups.rollback.length})` : ''}
                 </button>
               </div>
             </div>

             {jobs.map((job) => (
               <article
                 key={jobKey(job)}
                 className={`cp-job ${selectedId === jobKey(job) ? 'is-selected' : ''}`}
               >
                 <div className="cp-job-title">
                   <label className="cp-job-check">
                     <input
                       type="checkbox"
                       checked={selectedIds.has(jobKey(job))}
                       onChange={(e) => toggleSelection(jobKey(job), e.target.checked)}
                     />
                     <span />
                   </label>
                   <button type="button" className="cp-job-head" onClick={() => loadLogs(job)}>
                     <span>{job.release?.tag_name || job.tag || job.id || 'Job'}</span>
                     <Badge variant={STATUS_VARIANT[job.status] || 'neutral'}>{job.status || '—'}</Badge>
                   </button>
                 </div>
                 <div className="cp-piece-desc">{job.phase || job.detail || job.target || ''}</div>
                 {job.progress != null && <div className="cp-bar"><i style={{ width: `${job.progress}%` }} /></div>}
               </article>
             ))}
           </div>

           <aside className="cp-card cp-detail-panel">
             <div className="cp-section-title">Detalle</div>
             {selectedJob ? (
               <>
                 <div className="cp-kv"><span>Job</span><b>{selectedJob.release?.tag_name || selectedJob.tag || selectedJob.id}</b></div>
                 <div className="cp-kv"><span>Estado</span><b>{selectedJob.status || '—'}</b></div>
                 <div className="cp-kv"><span>Destino</span><b>{selectedJob.target || '—'}</b></div>
                 <div className="cp-kv"><span>Fase</span><b>{selectedJob.phase || selectedJob.detail || '—'}</b></div>
                 <div className="cp-kv"><span>Progreso</span><b>{selectedJob.progress ?? '—'}</b></div>
                 <div className="cp-job-log">
                   {jobLogError ? <div className="cp-error">{jobLogError}</div> : null}
                   {jobLogs.map((row, index) => (
                     <div className="cp-job-log-row" key={`${row.timestamp || index}-${index}`}>
                       <time>{String(row.timestamp || '').slice(11, 19)}</time>
                       <strong>{row.level || 'info'}</strong>
                       <span>{row.message || ''}</span>
                     </div>
                   ))}
                 </div>
               </>
             ) : (
               <ViewState empty emptyLabel="Selecciona un job para ver su log" />
             )}
           </aside>
         </div>
       </ViewState>}
    </section>
  )
}
