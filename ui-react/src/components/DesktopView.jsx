import ComposeBar from './ComposeBar'

function Message({ item }) {
  const role = item.role || 'system'
  const label = role === 'assistant' ? 'BAGO' : role === 'user' ? 'Tú' : 'Sistema'

  return (
    <article className={`message role-${role}`}>
      <div className="message-author">{label}</div>
      <div className="message-content">{String(item.content || '').trim() || '(sin contenido)'}</div>
    </article>
  )
}

function ModelSelector({ control }) {
  return (
    <select
      className="model-select"
      value={control.session?.model || ''}
      onChange={(event) => control.switchProviderModel(control.session?.provider, event.target.value, 'desktop')}
      disabled={control.busy || !control.session?.provider || !control.models.length}
      aria-label="Modelo activo"
    >
      {!control.models.length ? <option value="">Sin modelo</option> : null}
      {control.models.map((model) => <option key={model.id} value={model.id}>{model.id}</option>)}
    </select>
  )
}

export default function DesktopView({ control }) {
  const history = [...control.history].slice(-40)
  const hasHistory = history.length > 0

  return (
    <section className={`chat-view ${hasHistory ? 'has-history' : 'is-empty'}`}>
      {hasHistory ? (
        <>
          <div className="conversation">
            {history.map((item, index) => <Message key={`${item.role}-${index}`} item={item} />)}
          </div>
          <div className="composer-dock">
            <ComposeBar
              busy={control.busy}
              onSubmit={(value) => control.submit(value, 'desktop')}
              placeholder="Escribe un mensaje"
              accessory={<ModelSelector control={control} />}
            />
            <p className="composer-note">BAGO conserva la sesión y el contexto. Enter envía, Shift+Enter añade una línea.</p>
          </div>
        </>
      ) : (
        <div className="empty-stage">
          <div className="welcome">
            <div className="welcome-mark">B</div>
            <h1>¿Qué quieres hacer?</h1>
            <p>Conversa, analiza o ejecuta una tarea con tu sesión BAGO.</p>
          </div>
          <div className="composer-dock">
            <ComposeBar
              busy={control.busy}
              onSubmit={(value) => control.submit(value, 'desktop')}
              placeholder="Escribe un mensaje"
              accessory={<ModelSelector control={control} />}
            />
            <p className="composer-note">BAGO conserva la sesión y el contexto. Enter envía, Shift+Enter añade una línea.</p>
          </div>
        </div>
      )}
    </section>
  )
}
