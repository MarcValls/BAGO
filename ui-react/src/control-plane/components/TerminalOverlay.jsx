import TerminalView from '../../components/TerminalView'

export default function TerminalOverlay({ terminalInstall, setTerminalInstall, chatControl }) {
  if (!terminalInstall) return null

  return (
    <div
      className="cp-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Terminal de ${terminalInstall}`}
      onClick={() => setTerminalInstall(null)}
      onKeyDown={(e) => { if (e.key === 'Escape') setTerminalInstall(null) }}
    >
      <div className="cp-overlay-panel" onClick={(e) => e.stopPropagation()}>
        <div className="cp-window-title">
          <span>Terminal — {terminalInstall}</span>
          <div className="cp-window-controls">
            <button type="button" className="cp-window-ctrl" aria-label="cerrar" onClick={() => setTerminalInstall(null)} title="Cerrar (Esc)">×</button>
          </div>
        </div>
        <div className="cp-window-body" style={{ minHeight: 360 }}>
          <TerminalView control={chatControl} installId={terminalInstall} />
        </div>
      </div>
    </div>
  )
}