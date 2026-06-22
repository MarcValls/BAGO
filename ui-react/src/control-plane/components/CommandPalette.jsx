import { Icon } from './ui'
import { ROOMS } from './constants'

export default function CommandPalette({
  paletteOpen, setPaletteOpen,
  paletteQuery, setPaletteQuery,
  paletteInputRef,
  paletteItems,
  onMenuAction,
}) {
  if (!paletteOpen) return null

  return (
    <div className="cp-palette-overlay" onClick={() => setPaletteOpen(false)}>
      <div className="cp-palette" onClick={(e) => e.stopPropagation()}>
        <div className="cp-palette-head">
          <Icon name="search" />
          <input
            ref={paletteInputRef}
            value={paletteQuery}
            onChange={(e) => setPaletteQuery(e.target.value)}
            placeholder="Ir a chat, rooms, tools, agents…"
          />
          <kbd>Esc</kbd>
        </div>
        <div className="cp-palette-body">
          {paletteItems.length === 0 ? (
            <div className="cp-palette-empty">Sin resultados</div>
          ) : (
            paletteItems.map((item, idx) => (
              <button
                key={item.id}
                type="button"
                className={`cp-palette-item ${idx === 0 ? 'is-highlighted' : ''}`}
                onClick={() => {
                  onMenuAction(item.action)
                  setPaletteOpen(false)
                  setPaletteQuery('')
                }}
              >
                <span className="cp-palette-label">{item.label}</span>
                <span className="cp-palette-section">{item.section}</span>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  )
}