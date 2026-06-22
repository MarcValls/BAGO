import { useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { useReleases } from '../useBagoData'

export default function ReleasesView({ onAction }) {
  const { data, loading, error } = useReleases()
  const [channel, setChannel] = useState('Stable')

  const releases = Array.isArray(data) ? data : []
  const filtered = channel === 'Stable' ? releases.filter((r) => !r.prerelease)
    : channel === 'Beta' ? releases.filter((r) => r.prerelease)
    : releases

  const CHANNELS = ['Stable', 'Beta', 'Todos']
  const CHANNEL_VARIANT = { Stable: 'ok', Beta: 'warn', Todos: 'neutral' }

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-seg">
          {CHANNELS.map((label) => (
            <button key={label} type="button" className={`cp-seg-btn ${channel === label ? 'is-active' : ''}`} onClick={() => setChannel(label)}>{label}</button>
          ))}
        </div>
        <button type="button" className="cp-btn" onClick={() => onAction?.('open-jobs')}>Jobs</button>
      </div>

      {loading ? <div className="cp-loading">Cargando releases desde GitHub…</div> :
       error ? <div className="cp-error">Error: {error}</div> :
       <ViewState empty={!filtered.length} emptyLabel={`Sin releases en canal ${channel}`}>
         <div className="cp-releases-grid">
           {filtered.map((rel) => (
             <div className="cp-card cp-release-card" key={rel.tag_name}>
               <div className="cp-section-head">
                 <div>
                   <div className="cp-piece-type">{rel.prerelease ? 'Beta' : 'Stable'}</div>
                   <div className="cp-piece-id">{rel.tag_name}</div>
                 </div>
                 <Badge variant={rel.prerelease ? 'warn' : 'ok'}>{rel.prerelease ? 'Preview' : 'Firmado'}</Badge>
               </div>
               <div className="cp-piece-desc">{rel.name || rel.tag_name}</div>
               <div className="cp-kv"><span>Assets</span><b>{rel.assets?.length || 0}</b></div>
               <div className="cp-kv"><span>Fecha</span><b>{rel.published_at ? new Date(rel.published_at).toLocaleDateString() : '—'}</b></div>
               <div className="cp-kv"><span>Descargas</span><b>{rel.assets?.reduce((s, a) => s + (a.download_count || 0), 0) || 0}</b></div>
               <div className="cp-card-foot">
                 <button type="button" className="cp-small-btn cp-install-release" onClick={() => onAction?.('install-release', rel.tag_name)}>Instalar</button>
                 <button type="button" className="cp-small-btn" onClick={() => onAction?.('shadow-release', rel.tag_name)}>Shadow</button>
               </div>
             </div>
           ))}
         </div>
       </ViewState>}
    </section>
  )
}