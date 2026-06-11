import { useState } from 'react'
import ComposeBar from './ComposeBar'
import SlashMenu from './SlashMenu'
import { useManagerContext } from '../useManagerContext'

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

function ManagerContextBar({ context }) {
  if (!context?.view || context.view === 'bago') return null
  return (
    <div className="manager-context-bar">
      <span className="context-label">Gestor activo</span>
      <span className="context-view">{context.viewLabel || context.view}</span>
      {context.installations != null && (
        <span className="context-stat">{context.installations} instalaciones</span>
      )}
      {context.pieces != null && (
        <span className="context-stat">{context.pieces} piezas</span>
      )}
    </div>
  )
}

export default function DesktopView({ control }) {
  const [showSlash, setShowSlash] = useState(false)
  const managerContext = useManagerContext()
  const history = [...control.history].slice(-40)
  const hasHistory = history.length > 0

  return (
    <section className={`chat-view ${hasHistory ? 'has-history' : 'is-empty'}`}>
      <ManagerContextBar context={managerContext} />

      {showSlash && (
        <SlashMenu control={control} menu={control.menu} context={managerContext} />
      )}

      {hasHistory ? (
        <>
          <div className="conversation">
            {history.map((item, index) => <Message key={`${item.role}-${index}`} item={item} />)}
          </div>
          <div className="composer-dock">
            <ComposeBar
              busy={control.busy}
              onSubmit={(value) => { setShowSlash(false); control.submit(value, 'desktop') }}
              placeholder="Escribe un mensaje"
              onSlash={() => setShowSlash(v => !v)}
              accessory={<ModelSelector control={control} />}
            />
            <p className="composer-note">Enter envía · Shift+Enter nueva línea · / para acciones rápidas</p>
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
              onSubmit={(value) => { setShowSlash(false); control.submit(value, 'desktop') }}
              placeholder="Escribe un mensaje"
              onSlash={() => setShowSlash(v => !v)}
              accessory={<ModelSelector control={control} />}
            />
            <p className="composer-note">Enter envía · Shift+Enter nueva línea · / para acciones rápidas</p>
          </div>
        </div>
      )}
    </section>
  )
}
