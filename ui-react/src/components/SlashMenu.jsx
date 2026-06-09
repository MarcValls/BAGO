function run(control, command) {
  void control.submit(command, control.mode)
}

export default function SlashMenu({ control, menu }) {
  const sessions = menu?.sessions || []

  return (
    <aside className="utility-popover" aria-label="Acciones adicionales">
      <div className="utility-head">
        <strong>Acciones rápidas</strong>
        <span>{sessions.length} sesiones</span>
      </div>
      <div className="utility-actions">
        {['/status', '/session', '/save', '/help'].map((command) => (
          <button key={command} type="button" onClick={() => run(control, command)} disabled={control.busy}>
            {command}
          </button>
        ))}
      </div>
      <p>Providers, credenciales, RL, instalaciones y diagnósticos pertenecen a BAGO Manager.</p>
    </aside>
  )
}
