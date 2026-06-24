import { useRef, useEffect } from 'react'
import ComposeBar from './ComposeBar'
import ChatStatusMeters from './ChatStatusMeters'

function Message({ item }) {
  const role = item.role || 'system'
  const label = role === 'assistant' ? 'BAGO' : role === 'user' ? 'Tú' : 'Sistema'
  const content = String(item.content || '').trim().replace(/^\[BAGO_CTX:[^\]]*\]\n/, '')

  return (
    <article className={`message role-${role}`}>
      <div className="message-author">{label}</div>
      <div className="message-content">{content || '(sin contenido)'}</div>
    </article>
  )
}

export default function ChatBody({ control, onSubmit, onSlash, showSlash, accessory, session, busy }) {
  const scrollRef = useRef(null)

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [control.history.length])

  const history = [...control.history].slice(-60)
  const hasHistory = history.length > 0

  return (
    <div className="chat-body">
      <div className="chat-body-meters">
        <ChatStatusMeters session={session} busy={busy} />
      </div>

      <div className="conversation" ref={scrollRef} aria-live="polite">
        {hasHistory ? (
          history.map((item, index) => (
            <Message key={`${item.role}-${index}`} item={item} />
          ))
        ) : (
          <div className="conversation-empty">
            <div className="conversation-empty-mark">B</div>
            <div>
              <h2>El chat es el centro</h2>
              <p>Conversa, inspecciona o lanza una tarea. Los paneles laterales aparecen cuando los necesitas.</p>
            </div>
          </div>
        )}
      </div>

      <div className="composer-dock composer-dock-floating">
        <ComposeBar
          busy={control.busy}
          onSubmit={onSubmit}
          placeholder="Escribe un mensaje…  el chat es la pieza central"
          onSlash={onSlash}
          accessory={accessory}
        />
        <p className="composer-note">
          Enter envía · Shift+Enter nueva línea · / para acciones rápidas ·
          {' '}<kbd>Ctrl</kbd>+<kbd>.</kbd> para centrar el chat
        </p>
      </div>
    </div>
  )
}