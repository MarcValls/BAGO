export default function CompactKitBar({ kit, summary, onOpenDetails }) {
  return (
    <div className="compact-kit-bar" aria-label="Contexto de sesión">
      <span className="compact-kit-item">
        {kit.installation?.label || 'BAGO local'}
      </span>
      <span className="compact-kit-dot" aria-hidden="true">·</span>
      <span className="compact-kit-item">
        {kit.model?.label || kit.model?.id || 'llama3.2:3b'}
      </span>
      <span className="compact-kit-dot" aria-hidden="true">·</span>
      <span className="compact-kit-item">
        {kit.pipeline?.label || 'Code Forge'} · {kit.pipeline?.variant || 'staged'}
      </span>
      <span className="compact-kit-dot" aria-hidden="true">·</span>
      <span className="compact-kit-item">
        claims {summary.claimsOk}/{summary.claimsTotal}
      </span>
      <button
        type="button"
        className="compact-kit-details-btn"
        onClick={onOpenDetails}
        aria-label="Detalles de sesión"
      >
        Detalles
      </button>
    </div>
  )
}
