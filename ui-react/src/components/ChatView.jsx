import { useState } from 'react'
import SlashMenu from './SlashMenu'
import ContextChips from './ContextChips'
import SessionKit from './SessionKit'
import ChatBody from './ChatBody'
import ContextPane from './ContextPane'
import Dock from './Dock'
import ManagerInspector from './ManagerInspector'
import ManagerOverlay from './ManagerOverlay'
import { useManagerContext } from '../useManagerContext'
import { useSessionKit } from '../useSessionKit'
import { usePipelineNodes } from '../usePipelineNodes'
import { useInspector } from '../useInspector'
import { useToast } from './Toast'

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

function ManagerContextBar({ context, kit, inspectorSummary, panels, onTogglePanel, managerDrawerOpen, onToggleManagerDrawer }) {
  if (!context?.view || context.view === 'bago') {
    return (
      <div className="manager-context-bar">
        <span className="context-label">Sesión equipada</span>
        <span className="context-view">{kit.pipeline?.label || 'Code Forge'} · {kit.pipeline?.variant || 'staged'}</span>
        <span className="context-stat">{kit.installation?.version || '4.7.0'}</span>
        <span className="context-stat">claims {inspectorSummary.claimsOk}/{inspectorSummary.claimsTotal}</span>
        <button
          type="button"
          className={`context-stat context-stat-btn ${panels.has('manager') ? 'is-active' : ''}`}
          onClick={onToggleManagerDrawer}
          aria-pressed={managerDrawerOpen}
        >
          {managerDrawerOpen ? '▣ Gestor visible' : '▢ Gestor'}
        </button>
      </div>
    )
  }
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
      <span className="context-stat">claims {inspectorSummary.claimsOk}/{inspectorSummary.claimsTotal}</span>
      <button
        type="button"
        className="context-stat context-stat-btn"
        onClick={() => onTogglePanel('manager')}
      >
        {panels.has('manager') ? 'Ocultar panel gestor' : 'Mostrar panel gestor'}
      </button>
    </div>
  )
}

export default function ChatView({ control, center }) {
  const [showSlash, setShowSlash] = useState(false)
  const managerContext = useManagerContext()
  const kit = useSessionKit()
  const pipeline = usePipelineNodes()
  const inspector = useInspector()
  const { push } = useToast()
  const panels = center.state.panels
  const chatFocus = center.state.chatFocus
  const showKit = !chatFocus && panels.has('kit')
  const showDock = !chatFocus && panels.has('pipeline')
  const showInspector = !chatFocus && center.inspectorOpen && panels.has('evidence')
  const showManagerDrawer = !chatFocus && center.managerDrawerOpen && panels.has('manager')
  const showContextPane = !chatFocus && panels.has('context')

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
    showContextPane ? 'has-context-pane' : '',
  ].filter(Boolean).join(' ')

  return (
    <section className={layoutClass}>
      <header className="chat-centered-head">
        <div className="chat-centered-title">
          <span className="chat-centered-eyebrow">Conversación equipada</span>
          <h1>¿Qué quieres hacer?</h1>
          <p>
            {kit.kit.installation?.label || 'BAGO local'} ({kit.kit.installation?.version || '4.7.0'}) ·
            {' '}{kit.kit.model?.label || 'llama3.2:3b'} ·
            {' '}{kit.kit.pipeline?.label || 'Code Forge'} · {kit.kit.pipeline?.variant || 'staged'} ·
            {' '}política {kit.kit.policy?.label || 'Staged'}
          </p>
        </div>
        <div className="chat-centered-actions">
          <ChatFocusButton focused={chatFocus} onToggle={() => center.focusChat(!chatFocus)} />
        </div>
      </header>

      <ManagerContextBar
        context={managerContext}
        kit={kit.kit}
        inspectorSummary={inspector.summary}
        panels={panels}
        onTogglePanel={center.togglePanel}
        managerDrawerOpen={center.managerDrawerOpen}
        onToggleManagerDrawer={center.toggleManagerDrawer}
      />

      <div className="chat-centered-grid">
        <main className="chat-centered-main" role="main">
          {showSlash && (
            <SlashMenu control={control} menu={control.menu} context={managerContext} />
          )}

          <ContextChips />

          <ChatBody
            control={control}
            onSubmit={handleSubmit}
            onSlash={() => setShowSlash((v) => !v)}
            showSlash={showSlash}
            accessory={<ModelSelector control={control} kit={kit.kit} />}
            session={control.session}
            busy={control.busy}
          />
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

        {showContextPane ? (
          <ContextPane
            open={showContextPane}
            onClose={() => center.togglePanel('context')}
          />
        ) : null}
      </div>

      {showKit ? (
        <SessionKit
          kit={kit.kit}
          summary={kit.summary}
          dispatch={kit}
          onToggleInspector={() => center.toggleInspector()}
          inspectorOpen={center.inspectorOpen}
          onOpenFullManager={() => control.setMode('manager')}
          compact
        />
      ) : null}

      {showDock ? (
        <Dock
          pipeline={pipeline}
          models={control.models}
          onAssignStep={(stepId, provider, model) => {
            push(`Paso ${stepId}: ${provider || 'Auto'}/${model || 'Auto'}`)
          }}
          compact
        />
      ) : null}

      {control.history.length > 0 && !chatFocus ? (
        <button
          type="button"
          className="chat-recapture"
          onClick={() => {
            center.focusChat(true)
            push('Chat centrado de nuevo')
          }}
        >
          ◉ Centrar chat
        </button>
      ) : null}
    </section>
  )
}