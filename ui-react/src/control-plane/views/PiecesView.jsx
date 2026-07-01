import { useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { useNodePieces } from '../useBagoData'
import { toRpgPiece, RARITIES } from '../rpg-data'

function PieceCard({ piece, onAttach, onConfig, onInspect }) {
  const rpg = toRpgPiece(piece)
  return (
    <div
      className="cp-card cp-piece-card-rpg"
      style={{ borderColor: rpg.rarityMeta.color, boxShadow: rpg.rarityMeta.glow }}
    >
      <div className="cp-piece-card-header">
        <span className="cp-piece-card-icon" style={{ background: rpg.rarityMeta.color }}>
          {rpg.slot[0].toUpperCase()}
        </span>
        <div className="cp-piece-card-meta">
          <div className="cp-piece-card-name">{rpg.name}</div>
          <div className="cp-piece-card-sub">{rpg.type} · {rpg.slot}</div>
        </div>
        <Badge variant={rpg.rarity}>{rpg.rarityMeta.label}</Badge>
      </div>

      <div className="cp-piece-card-desc">{rpg.description}</div>

      <div className="cp-piece-card-stats">
        {Object.entries(rpg.stats).map(([k, v]) => (
          <div key={k} className="cp-piece-card-stat">
            <span className="cp-piece-card-stat-label">{k.slice(0, 3)}</span>
            <div className="cp-piece-card-stat-dots">
              {Array.from({ length: 5 }).map((_, i) => (
                <span key={i} className={`cp-piece-card-dot ${i < v ? 'is-on' : ''}`} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {rpg.abilities.length > 0 && (
        <div className="cp-piece-card-abilities">
          {rpg.abilities.map((a) => (
            <span key={a} className="cp-piece-card-ability">{a}</span>
          ))}
        </div>
      )}

      <div className="cp-card-foot">
        <button type="button" className="cp-small-btn" onClick={() => onAttach?.(rpg.id)}>Equipar</button>
        <button type="button" className="cp-small-btn" onClick={() => onInspect?.(rpg)}>Inspeccionar</button>
        <button type="button" className="cp-small-btn" onClick={() => onConfig?.(rpg.id)}>Config</button>
      </div>
    </div>
  )
}

export default function PiecesView({ context, onAction }) {
  const { data, loading, error, refresh } = useNodePieces()
  const [filter, setFilter] = useState('Todas')
  const [selected, setSelected] = useState(null)

  const raw = data?.ok ? (data.data || data.text || data.raw) : null
  const pieces = Array.isArray(raw) ? raw : []

  const filtered = filter === 'Todas' ? pieces : pieces.filter((p) => {
    const type = (p.type || p.kind || '').toLowerCase()
    return type.includes(filter.toLowerCase())
  })

  const FILTERS = ['Todas', 'tool', 'agent', 'skill', 'knowledge', 'connector', 'model', 'translator']

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
        <div className="cp-toolbar-actions">
          <button type="button" className="cp-btn" onClick={() => { refresh(); onAction?.('toast', 'Piezas recargadas') }}>
            Releer
          </button>
          <button type="button" className="cp-btn cp-btn-primary" onClick={() => onAction?.('open-nodes')}>
            <Icon name="nodes" /> Nodos
          </button>
        </div>
      </div>

      {loading ? <ViewState loading /> :
       error ? <ViewState error={error} /> :
       !pieces.length ? <ViewState empty emptyLabel="Sin piezas reales disponibles" /> :
       (
         <ViewState empty={!filtered.length} emptyLabel="Sin piezas para este filtro">
           <div className="cp-pieces-grid-rpg">
             {filtered.map((piece, i) => (
               <PieceCard
                 key={piece.id || piece.name || i}
                 piece={piece}
                 onAttach={(id) => onAction?.('attach-piece', id)}
                 onConfig={(id) => onAction?.('config-piece', id)}
                 onInspect={(rpg) => setSelected(rpg)}
               />
             ))}
           </div>
         </ViewState>
       )}

      {selected && (
        <div className="cp-piece-inspector">
          <div className="cp-piece-inspector-head">
            <span style={{ color: selected.rarityMeta.color }}>{selected.name}</span>
            <button type="button" onClick={() => setSelected(null)}>✕</button>
          </div>
          <pre className="cp-piece-inspector-json">{JSON.stringify(selected.raw, null, 2)}</pre>
        </div>
      )}
    </section>
  )
}
