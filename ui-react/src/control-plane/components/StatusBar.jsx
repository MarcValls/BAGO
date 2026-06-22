import { Icon } from './ui'

export default function StatusBar({
  context, setSidebarOpen, setInspectorOpen,
}) {
  return (
    <footer className="cp-statusbar">
      <div className="cp-statusbar-left">
        <span className="cp-statusbar-badge cp-statusbar-ok">
          <Icon name="checkCircle" size={11} /> Sync
        </span>
        <span className="cp-statusbar-badge cp-statusbar-info">
          {context.install || 'inst-A'}
        </span>
        <span className="cp-statusbar-badge cp-statusbar-warn">
          {context.node || 'codex-cli'}
        </span>
        <span className="cp-statusbar-item cp-statusbar-muted">Release 4.6.0 · 18 claims</span>
      </div>
      <div className="cp-statusbar-right">
        <button type="button" className="cp-statusbar-badge cp-statusbar-action" onClick={() => setSidebarOpen((v) => !v)}>
          Sidebar
        </button>
        <button type="button" className="cp-statusbar-badge cp-statusbar-action" onClick={() => setInspectorOpen((v) => !v)}>
          Inspector
        </button>
      </div>
    </footer>
  )
}