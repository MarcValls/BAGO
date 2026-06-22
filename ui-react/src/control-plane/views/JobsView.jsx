import { Badge, Icon, ViewState } from '../components/ui'
import { useReleaseJobs, useReleaseJobChanges } from '../useBagoData'

const STATUS_VARIANT = { pending: 'neutral', running: 'cyan', preparing: 'warn', done: 'ok', completed: 'ok', failed: 'danger', cancelled: 'neutral' }

export default function JobsView({ onAction }) {
  const { data, loading, error, refresh } = useReleaseJobs()

  const jobs = Array.isArray(data) ? data : (data?.jobs || [])

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-section-title">Jobs en segundo plano</div>
        <button type="button" className="cp-btn" onClick={refresh}>Refrescar</button>
      </div>

      {loading ? <div className="cp-loading">Cargando jobs…</div> :
       error ? <div className="cp-error">Error: {error}</div> :
       <ViewState empty={!jobs.length} emptyLabel="Sin jobs activos">
         <div className="cp-card">
           {jobs.map((job) => (
             <div className="cp-job" key={job.id || job.tag}>
               <div className="cp-job-title">
                 <span>{job.tag || job.id || 'Job'}</span>
                 <Badge variant={STATUS_VARIANT[job.status] || 'neutral'}>{job.status || '—'}</Badge>
               </div>
               <div className="cp-piece-desc">{job.phase || job.detail || ''}</div>
               {job.progress != null && <div className="cp-bar"><i style={{ width: `${job.progress}%` }} /></div>}
             </div>
           ))}
         </div>
       </ViewState>}
    </section>
  )
}