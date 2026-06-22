import { useState, useEffect } from 'react'
import { useInstallations, useNodeConnectors } from '../useBagoData'
import { CPIcons } from '../icons'

const MODE_CLASS = {
  connected: 'cp-patch-cell-connected',
  shadow: 'cp-patch-cell-shadow',
  readonly: 'cp-patch-cell-readonly',
  locked: 'cp-patch-cell-locked',
  detached: '',
}

function Icon({ name, size = 16 }) {
  const svg = CPIcons[name]
  return svg ? <span className="cp-icon" style={{ width: size, height: size }}>{svg}</span> : null
}

function Badge({ children, variant = 'neutral' }) {
  return <span className={`cp-badge cp-badge-${variant}`}>{children}</span>
}

export default function PatchbayView({ context, onSetContext }) {
  const { data: instData, loading: instLoad } = useInstallations()
  const { data: connData, loading: connLoad } = useNodeConnectors()
  const [selectedCell, setSelectedCell] = useState(null)

  const installations = (instData?.installations || []).filter((i) => i.exists)
  const connectors = connData?.ok ? (connData.data || connData.text || []) : []

  // Construir filas reales: una por instalacion, columnas = connectors unicos
  const allConnectorNames = Array.isArray(connectors)
    ? [...new Set(connectors.map((c) => c.name || c.id || c.piece || '').filter(Boolean))]
    : []
  const COLUMNS = allConnectorNames.length ? allConnectorNames : ['Codex CLI', 'Registry', 'Knowledge', 'GitHub']

  const rows = installations.map((inst) => {
    const label = inst.path.split(/[\\\/]/).pop() || inst.path
    const cells = {}
    for (const col of COLUMNS) {
      const conn = Array.isArray(connectors) ? connectors.find((c) => (c.installation === inst.path || c.installation === label) && (c.name === col || c.id === col)) : null
      cells[col] = conn ? (conn.mode || conn.status || 'connected') : 'detached'
    }
    return { installationId: label, installationSub: `${inst.mode} · ${inst.version || '—'}`, cells }
  })

  function cycleCell(rowIndex, col) {
    setSelectedCell(`${rowIndex}:${col}`)
    onSetContext((c) => ({
      ...c,
      install: installations[rowIndex]?.path || c.install,
      patch: `${rows[rowIndex]?.installationId}/${col}`,
    }))
  }

  if (instLoad && connLoad) return <section className="cp-view cp-view-active"><div className="cp-loading">Cargando conectores…</div></section>

  return (
    <section className="cp-view cp-view-active">
      <div className="cp-toolbar">
        <div className="cp-section-title">Patchbay</div>
        <Badge variant="neutral">{selectedCell ? '1' : '0'}</Badge>
      </div>

      <div className="cp-table-wrap">
        {rows.length === 0 ? (
          <div className="cp-loading">Sin instalaciones detectadas</div>
        ) : (
          <table className="cp-table cp-patch-table">
            <thead>
              <tr>
                <th>Instalación</th>
                {COLUMNS.map((col) => <th key={col}>{col}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={row.installationId}>
                  <td><b>{row.installationId}</b><div className="cp-path">{row.installationSub}</div></td>
                  {COLUMNS.map((col) => {
                    const mode = row.cells[col] || 'detached'
                    return (
                      <td key={col}>
                        <button type="button" className={`cp-patch-cell ${MODE_CLASS[mode] || ''} ${selectedCell === `${rowIndex}:${col}` ? 'is-selected' : ''}`} onClick={() => cycleCell(rowIndex, col)}>
                          {mode === 'readonly' ? 'read-only' : mode}
                        </button>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="cp-patch-legend">
        {[
          { label: 'Connected', cls: 'cp-swatch-ok' },
          { label: 'Shadow', cls: 'cp-swatch-warn' },
          { label: 'Read-only', cls: 'cp-swatch-cyan' },
          { label: 'Locked', cls: 'cp-swatch-danger' },
          { label: 'Detached', cls: '' },
        ].map((item) => (
          <span className="cp-legend" key={item.label}>
            <i className={`cp-swatch ${item.cls}`} />
            {item.label}
          </span>
        ))}
      </div>
    </section>
  )
}
