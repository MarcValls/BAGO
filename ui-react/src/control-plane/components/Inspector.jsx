import { Icon } from './ui'

export default function Inspector({ inspectorOpen, setInspectorOpen, navigate, context, setContext, push }) {
  if (!inspectorOpen) return null

  return (
    <aside className="cp-inspector-vsc">
      <div className="cp-inspector-head">
        <span>Inspector</span>
        <button type="button" className="cp-inspector-close" onClick={() => setInspectorOpen(false)} title="Ocultar">›</button>
      </div>
      <div className="cp-inspector-body">
        <button type="button" className="cp-inspector-to-chat" onClick={() => navigate('chat')}>
          <Icon name="chat" size={16} /> Abrir en chat
        </button>
        <div className="cp-inspector-block cp-inspector-status">
          <div className="cp-kv">
            <span>Supervisor</span>
            <span className="cp-text-ok">Activo</span>
          </div>
          <div className="cp-kv">
            <span>Release</span>
            <b>4.6.0</b>
          </div>
        </div>
        <div className="cp-inspector-block">
          <div className="cp-mode-list">
            {[
              { label: 'Instalaciones', action: () => navigate('installations') },
              { label: 'Salud', action: () => navigate('health') },
              { label: 'Jobs', action: () => navigate('jobs') },
              { label: 'Nodos', action: () => navigate('nodes') },
            ].map((item) => (
              <button key={item.label} type="button" className="cp-mode-option" onClick={item.action}>{item.label}</button>
            ))}
          </div>
        </div>
        <div className="cp-inspector-block">
          <div className="cp-mode-list">
            {['connected', 'shadow', 'readonly', 'locked', 'detached'].map((mode) => (
              <button
                key={mode}
                type="button"
                className={`cp-mode-option cp-mode-${mode}`}
                onClick={() => setContext((c) => ({ ...c, patch: `${c.install}/${mode}` }))}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
        <div className="cp-inspector-block">
          <div className="cp-job">
            <div className="cp-job-title"><span>Index knowledge</span><span className="cp-text-cyan">72%</span></div>
          </div>
          <div className="cp-job">
            <div className="cp-job-title"><span>Verify 4.6.1</span><span className="cp-text-ok">ok</span></div>
          </div>
        </div>
      </div>
    </aside>
  )
}
