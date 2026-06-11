const VIEW_COMMANDS = {
  patch:         ['/node status', '/node connectors', '/node validate', '/status'],
  installations: ['/node status', '/node pieces', '/status', '/session'],
  matrix:        ['/node matrix', '/node status', '/node validate'],
  pieces:        ['/node pieces', '/node status', '/node validate'],
  releases:      ['/version', '/status', '/help'],
  jobs:          ['/status', '/session', '/save'],
  sessions:      ['/session', '/session list', '/save', '/status'],
  system:        ['/status', '/health', '/help'],
  health:        ['/health', '/status', '/node validate'],
  audit:         ['/node evidence', '/node validate', '/status'],
}
const DEFAULT_COMMANDS = ['/status', '/session', '/save', '/help']

function run(control, command) {
  void control.submit(command, control.mode)
}

export default function SlashMenu({ control, menu, context }) {
  const sessions = menu?.sessions || []
  const view = context?.view
  const commands = (view && VIEW_COMMANDS[view]) || DEFAULT_COMMANDS

  return (
    <aside className="utility-popover" aria-label="Acciones rápidas">
      <div className="utility-head">
        <strong>Acciones rápidas</strong>
        <span>
          {context?.viewLabel ? `Gestor: ${context.viewLabel}` : `${sessions.length} sesiones`}
        </span>
      </div>
      <div className="utility-actions">
        {commands.map((command) => (
          <button key={command} type="button" onClick={() => run(control, command)} disabled={control.busy}>
            {command}
          </button>
        ))}
      </div>
      {context?.installations != null && (
        <p>{context.installations} instalaciones · {context.pieces ?? '?'} piezas en el gestor activo.</p>
      )}
    </aside>
  )
}
