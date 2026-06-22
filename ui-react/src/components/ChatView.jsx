import { useState } from 'react'
import ComposeBar from './ComposeBar'
import SlashMenu from './SlashMenu'
import ContextChips from './ContextChips'
import SessionKit from './SessionKit'
import PipelineDock from './PipelineDock'
import ManagerInspector from './ManagerInspector'
import ManagerOverlay from './ManagerOverlay'
import CompactKitBar from './CompactKitBar'
import CompactPipelineBar from './CompactPipelineBar'
import { useManagerContext } from '../useManagerContext'
import { useSessionKit } from '../useSessionKit'
import { usePipelineNodes } from '../usePipelineNodes'
import { useInspector } from '../useInspector'
import { useToast } from './Toast'

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

function ModelSelector({ control, kit }) {
  return (
    <select
      className="model-select"
      value={kit.model?.id || control.session?.model || ''}
      onChange={(event) => control.switchProviderModel(kit.model?.provider, event.target.value, 'desktop')}
      disabled={control.busy || !kit.model?.provider || !control.models.length}
      aria-label="Modelo activo"
    >
      {!control.models.length ? <option value="">Sin modelo</option> : null}
      {control.models.map((model) => <option key={model.id} value={model.id}>{model.id}</option>)}
    </select>
  )
}

function ChatFocusButton({ focused, onToggle }) {
  return (
    <button
      type="button"
      className={`chat-focus-btn ${focused ? 'is-on' : ''}`}
      onClick={onToggle}
      title={focused ? 'Mostrar paneles laterales' : 'Céntrate solo en el chat'}
      aria-pressed={focused}
    >
      {focused ? '◉ Chat centrado' : '○ Mostrar paneles'}
    </button>
  )
}

export default function ChatView({ control, center }) {
  const [showSlash, setShowSlash] = useState(false)
  const managerContext = useManagerContext()
  const kit = useSessionKit()
  const pipeline = usePipelineNodes()
  const inspector = useInspector()
  const { push } = useToast()
  const history = [...control.history].slice(-40)
  const hasHistory = history.length > 0

  const panels = center.state.panels
  const chatFocus = center.state.chatFocus
  const showInspector = !chatFocus && center.inspectorOpen && panels.has('evidence')
  const showManagerDrawer = !chatFocus && center.managerDrawerOpen && panels.has('manager')

  function handleSubmit(value) {
    setShowSlash(false)
    pipeline.markCompleted('entrada')
    control.submit(value, 'desktop', {
      ...(managerContext || {}),
      kit: {
        installation: kit.kit.installation?.id,
        model: kit.kit.model?.id,
        provider: kit.kit.model?.provider,
        pipeline: kit.kit.pipeline?.id,
        variant: kit.kit.pipeline?.variant,
        policy: kit.kit.policy?.id,
      },
    })
  }

  const layoutClass = [
    'chat-centered',
    chatFocus ? 'is-focused' : 'is-expanded',
    showManagerDrawer ? 'has-manager-drawer' : '',
    showInspector ? 'has-inspector' : '',
    center.flowOpen ? 'has-flow-open' : '',
    center.contractOpen ? 'has-contract-open' : '',
  ].filter(Boolean).join(' ')

  return (
    <section className={layoutClass}>
      <header className="chat-centered-head">
        <div className="chat-head-main">
          <h1>¿Qué quieres hacer?</h1>
          <CompactKitBar
            kit={kit.kit}
            summary={kit.summary}
            onOpenDetails={() => center.toggleInspector(true)}
          />
        </div>
        <div className="chat-centered-actions">
          <button
            type="button"
            className={`chat-contract-btn ${center.contractOpen ? 'is-active' : ''}`}
            onClick={() => center.toggleContract()}
            aria-pressed={center.contractOpen}
            title="Ver contrato de ejecución"
          >
            Contrato seguro · 6 reglas
          </button>
          <ChatFocusButton focused={chatFocus} onToggle={() => center.focusChat(!chatFocus)} />
        </div>
      </header>

      <div className="chat-centered-grid">
        <main className="chat-centered-main" role="main">
          {center.contractOpen ? (
            <div className="contract-drawer">
              <ContextChips />
            </div>
          ) : null}

          {showSlash && (
            <SlashMenu control={control} menu={control.menu} context={managerContext} />
          )}

          <div className="conversation" aria-live="polite">
            {hasHistory ? (
              history.map((item, index) => <Message key={`${item.role}-${index}`} item={item} />)
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
              onSubmit={handleSubmit}
              placeholder="Escribe un mensaje…"
              onSlash={() => setShowSlash((v) => !v)}
              accessory={<ModelSelector control={control} kit={kit.kit} />}
            />
            <p className="composer-note">
              Enter envía · Shift+Enter nueva línea · / para acciones rápidas ·
              {' '}<kbd>Ctrl</kbd>+<kbd>.</kbd> para centrar el chat
            </p>
          </div>
        </main>

        {showManagerDrawer ? (
          <ManagerOverlay
            onClose={() => center.toggleManagerDrawer(false)}
            managerContext={managerContext}
            kit={kit.kit}
            inspectorSummary={inspector.summary}
          />
        ) : null}

        {showInspector ? (
          <ManagerInspector
            pipeline={pipeline}
            inspector={inspector}
            kit={kit.kit}
            onClose={() => center.toggleInspector(false)}
          />
        ) : null}
      </div>

      {panels.has('kit') && center.dockOpen ? (
        <div className="floating-panel">
          <header className="floating-panel-head">
            <span>Equipamiento de sesión</span>
            <button
              type="button"
              className="floating-panel-close"
              onClick={() => center.toggleDock(false)}
              aria-label="Cerrar equipamiento"
            >
              ✕
            </button>
          </header>
          <SessionKit
            kit={kit.kit}
            summary={kit.summary}
            dispatch={kit}
            onToggleInspector={() => center.toggleInspector()}
            inspectorOpen={center.inspectorOpen}
            onOpenFullManager={() => control.setMode('manager')}
            compact
          />
        </div>
      ) : null}

      {panels.has('pipeline') && center.flowOpen ? (
        <div className="floating-panel">
          <header className="floating-panel-head">
            <span>Control Deck · Code Forge</span>
            <button
              type="button"
              className="floating-panel-close"
              onClick={() => center.toggleFlow(false)}
              aria-label="Cerrar pipeline"
            >
              ✕
            </button>
          </header>
          <PipelineDock
            pipeline={pipeline}
            inspectorOpen={center.inspectorOpen}
            onToggleInspector={() => center.toggleInspector()}
            compact
          />
        </div>
      ) : panels.has('pipeline') ? (
        <CompactPipelineBar
          pipeline={pipeline}
          onOpenFlow={() => center.toggleFlow(true)}
          onAdvance={() => {
            pipeline.advance()
            push('Pipeline avanzado')
          }}
        />
      ) : null}
    </section>
  )
}

