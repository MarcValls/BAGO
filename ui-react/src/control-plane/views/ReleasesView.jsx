import { useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { useManagerHealth, useReleases } from '../useBagoData'

export default function ReleasesView({ context, onAction }) {
  const { data, loading, error, refresh } = useReleases()
  const { data: health } = useManagerHealth()
  const [channel, setChannel] = useState('Stable')
  const [busyTag, setBusyTag] = useState('')

  const releases = Array.isArray(data) ? data : []
  const filtered = channel === 'Stable' ? releases.filter((r) => !r.prerelease)
    : channel === 'Beta' ? releases.filter((r) => r.prerelease)
    : releases

  const CHANNELS = ['Stable', 'Beta', 'Todos']
  const CHANNEL_VARIANT = { Stable: 'ok', Beta: 'warn', Todos: 'neutral' }

  const target = context?.install || health?.runtime_root || ''

  async function prepareRelease(rel) {
    const api = typeof window !== 'undefined' ? window.bagoElectron : null
    if (!api?.preflightRelease || !api?.startReleaseJob) {
      onAction?.('toast', 'Preparación de release no disponible sin Electron')
      return
    }
    if (!target) {
      onAction?.('toast', 'Selecciona una instalación objetivo antes de preparar la release')
      return
    }
    setBusyTag(rel.tag_name)
    try {
      const preflight = await api.preflightRelease({
        release: rel,
        target,
        action: 'install',
        mode: 'Express',
        require_signature: false,
      })
      const blockers = preflight?.prepare_blockers || preflight?.blockers || []
      if (!preflight?.prepare_ready && blockers.length) {
        onAction?.('toast', blockers[0] || 'Preflight bloqueado')
        return
      }
      const job = await api.startReleaseJob({
        release: rel,
        target,
        action: 'install',
        mode: 'Express',
        require_signature: false,
      })
      onAction?.('toast', `Job creado: ${job?.id || rel.tag_name}`)
      onAction?.('open-jobs')
      refresh?.()
    } catch (e) {
      onAction?.('toast', `Release: ${e.message}`)
    } finally {
      setBusyTag('')
    }
  }

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-seg">
          {CHANNELS.map((label) => (
            <button key={label} type="button" className={`cp-seg-btn ${channel === label ? 'is-active' : ''}`} onClick={() => setChannel(label)}>{label}</button>
          ))}
        </div>
        <div className="cp-toolbar-actions">
          <button type="button" className="cp-btn" onClick={() => { refresh(); onAction?.('toast', 'Releases recargadas') }}>Refrescar</button>
          <button type="button" className="cp-btn" onClick={() => onAction?.('open-jobs')}>Jobs</button>
          <button type="button" className="cp-btn" onClick={() => onAction?.('open-health')}>Salud</button>
        </div>
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
                 <button type="button" className="cp-small-btn cp-install-release" onClick={() => prepareRelease(rel)} disabled={busyTag === rel.tag_name}>
                   {busyTag === rel.tag_name ? 'Preparando…' : 'Preparar'}
                 </button>
               </div>
             </div>
           ))}
         </div>
       </ViewState>}
    </section>
  )
}
