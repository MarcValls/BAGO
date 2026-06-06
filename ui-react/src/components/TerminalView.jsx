import ComposeBar from './ComposeBar'

function commandLines(entry) {
  const message = entry.response?.message || entry.response?.action || '(sin salida)'
  return message.split('\n').filter(Boolean)
}

export default function TerminalView({ control }) {
  const commandLog = [...control.commandLog].reverse()

  return (
    <section className="terminal-shell">
      <div className="terminal-header">
        <span>bago@react-terminal</span>
        <span>{control.session?.provider}/{control.session?.model}</span>
      </div>
      <div className="terminal-status">
        <span>catalog={control.catalog?.mode || 'all'}</span>
        <span>shadow={control.simulation?.mode || 'shadow'}</span>
        <span>{control.simulation?.authority || 'observer-only'}</span>
      </div>
      <div className="terminal-log">
        {control.history.map((item, index) => (
          <div key={`${item.role}-${index}`} className={`line role-${item.role}`}>
            <span className="prompt">{item.role}&gt;</span>
            <span>{item.content}</span>
          </div>
        ))}

        {commandLog.map((entry) => (
          <div key={entry.id} className="terminal-command-block">
            <div className="line role-system">
              <span className="prompt">cmd&gt;</span>
              <span>{entry.command}</span>
            </div>
            {commandLines(entry).map((line, index) => (
              <div key={`${entry.id}-${index}`} className="line role-system">
                <span className="prompt">out&gt;</span>
                <span>{line}</span>
              </div>
            ))}
          </div>
        ))}

        {!control.history.length && !commandLog.length && <div className="line muted">Sin mensajes todavía.</div>}
      </div>
      <ComposeBar
        busy={control.busy}
        onSubmit={(value) => control.submit(value, 'terminal')}
        placeholder="Escribe mensaje o /comando"
      />
    </section>
  )
}
