import { useMemo, useState } from 'react'
import { Badge, Icon, ViewState } from '../components/ui'
import { useNodePieces } from '../useBagoData'
import { DEMO_PIECES } from '../data'
import { RPG_SLOTS, RARITIES, defaultEquipped, computeGearScore, toRpgPiece } from '../rpg-data'

function GearSlot({ slotKey, equipped, alternatives, onEquip, onOpenDetails }) {
  const slotMeta = RPG_SLOTS[slotKey]
  const item = equipped[slotKey]

  return (
    <div className={`cp-gear-slot ${item ? 'is-equipped' : 'is-empty'}`}>
      <div className="cp-gear-slot-frame">
        <div className="cp-gear-slot-icon">{slotMeta.label[0]}</div>
        {item ? (
          <button
            type="button"
            className="cp-gear-item"
            style={{ borderColor: item.rarityMeta.color, boxShadow: item.rarityMeta.glow }}
            onClick={() => onOpenDetails?.(item)}
            title={item.name}
          >
            <span className="cp-gear-item-name">{item.name}</span>
            <span className="cp-gear-item-type">{item.type}</span>
            <Badge variant={item.rarity}>{item.rarityMeta.label}</Badge>
          </button>
        ) : (
          <div className="cp-gear-empty">Vacío</div>
        )}
      </div>
      {alternatives.length > 0 && (
        <div className="cp-gear-alternatives">
          {alternatives.slice(0, 3).map((alt) => (
            <button
              key={alt.id}
              type="button"
              className="cp-gear-alt"
              style={{ borderColor: alt.rarityMeta.color }}
              onClick={() => onEquip(slotKey, alt)}
              title={alt.description}
            >
              {alt.name}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function StatRadar({ stats }) {
  const labels = ['vel', 'coste', 'contexto', 'estab', 'seg']
  const values = [stats.speed, stats.cost, stats.context, stats.stability, stats.security]
  const max = 5
  const size = 96
  const cx = size / 2
  const cy = size / 2
  const radius = size / 2 - 8
  const points = values.map((v, i) => {
    const angle = (Math.PI * 2 * i) / 5 - Math.PI / 2
    const r = (v / max) * radius
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
  }).join(' ')

  return (
    <svg className="cp-gear-radar" width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <circle key={n} cx={cx} cy={cy} r={(n / 5) * radius} fill="none" stroke="currentColor" opacity={0.2} />
      ))}
      <polygon points={points} fill="currentColor" opacity={0.25} stroke="currentColor" strokeWidth={1.5} />
      {values.map((v, i) => {
        const angle = (Math.PI * 2 * i) / 5 - Math.PI / 2
        const r = (v / max) * radius
        return <circle key={i} cx={cx + r * Math.cos(angle)} cy={cy + r * Math.sin(angle)} r={3} fill="currentColor" />
      })}
    </svg>
  )
}

export default function RpgGearView({ context, onAction }) {
  const { data, loading, error } = useNodePieces()
  const [selected, setSelected] = useState(null)
  const [customEquipped, setCustomEquipped] = useState(null)

  const raw = data?.ok ? (data.data || data.text || data.raw) : null
  const pieces = Array.isArray(raw) ? raw : DEMO_PIECES

  const bySlot = useMemo(() => {
    const map = {}
    Object.keys(RPG_SLOTS).forEach((k) => (map[k] = []))
    pieces.forEach((p) => {
      const rpg = toRpgPiece(p)
      map[rpg.slot].push(rpg)
    })
    return map
  }, [pieces])

  const equipped = customEquipped || defaultEquipped(pieces)
  const score = computeGearScore(equipped)

  function handleEquip(slotKey, item) {
    setCustomEquipped((prev) => ({ ...(prev || equipped), [slotKey]: item }))
    onAction?.('toast', `Equipado: ${item.name} en ${RPG_SLOTS[slotKey].label}`)
  }

  return (
    <section className="cp-view cp-view-active cp-gear-view">
      <div className="cp-toolbar">
        <div className="cp-gear-header">
          <Icon name="user" size={20} />
          <div>
            <div className="cp-gear-title">Equipo del chat</div>
            <div className="cp-gear-subtitle">
              Puntuación de equipo: <span className="cp-gear-score">{score}</span>
            </div>
          </div>
        </div>
        <button type="button" className="cp-btn" onClick={() => setCustomEquipped(null)}>
          Auto-equipar óptimo
        </button>
      </div>

      {loading ? <ViewState loading /> :
       error ? <ViewState error={error} /> :
       (
        <div className="cp-gear-body">
          <div className="cp-gear-slots">
            {Object.keys(RPG_SLOTS).map((slotKey) => (
              <GearSlot
                key={slotKey}
                slotKey={slotKey}
                equipped={equipped}
                alternatives={bySlot[slotKey]}
                onEquip={handleEquip}
                onOpenDetails={setSelected}
              />
            ))}
          </div>

          {selected && (
            <div className="cp-gear-detail">
              <div className="cp-gear-detail-head">
                <span style={{ color: selected.rarityMeta.color }}>{selected.name}</span>
                <button type="button" className="cp-gear-detail-close" onClick={() => setSelected(null)}>✕</button>
              </div>
              <div className="cp-gear-detail-body">
                <Badge variant={selected.rarity}>{selected.rarityMeta.label}</Badge>
                <span className="cp-gear-detail-type">{selected.type} · {RPG_SLOTS[selected.slot].label}</span>
                <p className="cp-gear-detail-desc">{selected.description}</p>
                <div className="cp-gear-detail-stats">
                  <StatRadar stats={selected.stats} />
                  <div className="cp-gear-stat-list">
                    {Object.entries(selected.stats).map(([k, v]) => (
                      <div key={k} className="cp-gear-stat-row">
                        <span className="cp-gear-stat-label">{k}</span>
                        <div className="cp-gear-stat-bar">
                          <div className="cp-gear-stat-fill" style={{ width: `${(v / 5) * 100}%` }} />
                        </div>
                        <span className="cp-gear-stat-value">{v}/5</span>
                      </div>
                    ))}
                  </div>
                </div>
                {selected.abilities.length > 0 && (
                  <div className="cp-gear-abilities">
                    {selected.abilities.map((a) => (
                      <span key={a} className="cp-gear-ability">{a}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
