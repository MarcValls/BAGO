import { useState } from 'react'
import { Badge, ViewState } from '../components/ui'
import { useReleases } from '../useBagoData'

export default function ReleasesView({ onAction }) {
  const { data, loading, error } = useReleases()
  const [channel, setChannel] = useState('Stable')

  const releases = Array.isArray(data) ? data : []
  const filtered = channel === 'Stable' ? releases.filter((release) => !release.prerelease)
    : channel === 'Beta' ? releases.filter((release) => release.prerelease)
    : releases

  const channels = ['Stable', 'Beta', 'Todos']

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-seg">
          {channels.map((label) => (
            <button
              key={label}
              type="button"
              className={`cp-seg-btn ${channel === label ? 'is-active' : ''}`}
              onClick={() => setChannel(label)}
            >
              {label}
            </button>
          ))}
        </div>
        <button type="button" className="cp-btn" onClick={() => onAction?.('open-jobs')}>Jobs</button>
      </div>

      {loading ? <div className="cp-loading">Cargando releases desde GitHub…</div> :
       error ? <div className="cp-error">Error: {error}</div> :
       <ViewState empty={!filtered.length} emptyLabel={`Sin releases en canal ${channel}`}>
         <div className="cp-releases-grid">
           {filtered.map((release) => (
             <div className="cp-card cp-release-card" key={release.tag_name}>
               <div className="cp-section-head">
                 <div>
                   <div className="cp-piece-type">{release.prerelease ? 'Beta' : 'Stable'}</div>
                   <div className="cp-piece-id">{release.tag_name}</div>
                 </div>
                 <Badge variant={release.prerelease ? 'warn' : 'ok'}>{release.prerelease ? 'Preview' : 'Publicada'}</Badge>
               </div>
               <div className="cp-piece-desc">{release.name || release.tag_name}</div>
               <div className="cp-kv"><span>Assets</span><b>{release.assets?.length || 0}</b></div>
               <div className="cp-kv"><span>Fecha</span><b>{release.published_at ? new Date(release.published_at).toLocaleDateString() : '—'}</b></div>
               <div className="cp-kv"><span>Descargas</span><b>{release.assets?.reduce((sum, asset) => sum + (asset.download_count || 0), 0) || 0}</b></div>
               <div className="cp-card-foot">
                 <button
                   type="button"
                   className="cp-small-btn cp-install-release"
                   onClick={() => onAction?.('install-release', release)}
                 >
                   Preflight e instalar
                 </button>
                 <button
                   type="button"
                   className="cp-small-btn"
                   onClick={() => onAction?.('shadow-release', release)}
                 >
                   Preparar separada
                 </button>
               </div>
             </div>
           ))}
         </div>
       </ViewState>}
    </section>
  )
}
