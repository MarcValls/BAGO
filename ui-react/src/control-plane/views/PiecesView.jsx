import { useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { useNodePieces } from '../useBagoData'

export default function PiecesView({ context, onAction }) {
  const { data, loading, error } = useNodePieces()
  const [filter, setFilter] = useState('Todas')

  const raw = data?.ok ? (data.data || data.text || data.raw) : null
  const pieces = Array.isArray(raw) ? raw : (raw?.pieces || raw?.items || [])
  const filtered = filter === 'Todas' ? pieces : pieces.filter((p) => {
    const type = (p.type || p.kind || '').toLowerCase()
    return type.includes(filter.toLowerCase())
  })

  const FILTERS = ['Todas', 'tool', 'agent', 'skill', 'knowledge', 'connector']

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-seg">
          {FILTERS.map((label) => (
            <button key={label} type="button" className={`cp-seg-btn ${filter === label ? 'is-active' : ''}`} onClick={() => setFilter(label)}>
              {label.charAt(0).toUpperCase() + label.slice(1)}
            </button>
          ))}
        </div>
        <button type="button" className="cp-btn cp-btn-primary" onClick={() => onAction?.('register-piece')}>
          <Icon name="plus" /> Registrar
        </button>
      </div>

      {loading ? <div className="cp-loading">Cargando piezas…</div> :
       error ? <div className="cp-error">Error: {error}</div> :
       !pieces.length ? <div className="cp-loading">Sin piezas — ejecuta <code>bago node pieces</code> para ver datos</div> :
       <ViewState empty={!filtered.length} emptyLabel="Sin piezas para este filtro">
         <div className="cp-pieces-grid">
           {filtered.map((piece, i) => (
             <div className="cp-card cp-piece-card" key={piece.id || piece.name || i}>
               <div className="cp-piece-type">{piece.type || piece.kind || '—'}</div>
               <div className="cp-piece-id">{piece.id || piece.name || '—'}</div>
               <div className="cp-piece-desc">{piece.desc || piece.description || piece.status || ''}</div>
               <div className="cp-card-foot">
                 <button type="button" className="cp-small-btn" onClick={() => onAction?.('attach-piece', piece.id || piece.name)}>Attach</button>
                 <button type="button" className="cp-small-btn" onClick={() => onAction?.('config-piece', piece.id || piece.name)}>Config</button>
               </div>
             </div>
           ))}
         </div>
       </ViewState>}
    </section>
  )
}