import { useCallback, useEffect, useMemo, useState } from 'react'
import { recordInteraction } from './interactionLog'

export const SESSION_VIEWS = {
  chat: { id: 'chat', label: 'Chat', icon: 'chat', hint: 'Conversación activa' },
  manager: { id: 'manager', label: 'Gestor', icon: 'manager', hint: 'Vista de gestión' },
  terminal: { id: 'terminal', label: 'Terminal', icon: 'terminal', hint: 'Comandos y logs' },
}

const STORAGE_KEY = 'bago.centered-chat.v1'

function readPersisted() {
  if (typeof window === 'undefined') return null
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || 'null')
  } catch {
    return null
  }
}

function writePersisted(value) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
  } catch {}
}

const DEFAULT_PANELS = ['kit', 'pipeline', 'evidence', 'context']

export function useChatCenter() {
  const persisted = readPersisted()
  const [rightPanel, setRightPanel] = useState(persisted?.rightPanel || 'inspector')
  const [panels, setPanels] = useState(() => {
    if (Array.isArray(persisted?.panels) && persisted.panels.length) return new Set(persisted.panels)
    return new Set(DEFAULT_PANELS)
  })
  const [inspectorOpen, setInspectorOpen] = useState(persisted?.inspectorOpen ?? true)
  const [dockOpen, setDockOpen] = useState(persisted?.dockOpen ?? true)
  const [managerDrawerOpen, setManagerDrawerOpen] = useState(persisted?.managerDrawerOpen ?? false)
  const [chatFocus, setChatFocus] = useState(persisted?.chatFocus ?? true)

  useEffect(() => {
    writePersisted({
      rightPanel,
      panels: [...panels],
      inspectorOpen,
      dockOpen,
      managerDrawerOpen,
      chatFocus,
    })
  }, [rightPanel, panels, inspectorOpen, dockOpen, managerDrawerOpen, chatFocus])

  const togglePanel = useCallback((id) => {
    setPanels((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      recordInteraction('panel-toggle', { id, on: next.has(id) })
      return next
    })
  }, [])

  const toggleInspector = useCallback((force) => {
    setInspectorOpen((current) => {
      const next = typeof force === 'boolean' ? force : !current
      recordInteraction('inspector-toggle', { on: next })
      return next
    })
    if (force === true) setRightPanel('inspector')
  }, [])

  const toggleDock = useCallback((force) => {
    setDockOpen((current) => {
      const next = typeof force === 'boolean' ? force : !current
      recordInteraction('dock-toggle', { on: next })
      return next
    })
  }, [])

  const toggleManagerDrawer = useCallback((force) => {
    setManagerDrawerOpen((current) => {
      const next = typeof force === 'boolean' ? force : !current
      recordInteraction('manager-drawer-toggle', { on: next })
      return next
    })
  }, [])

  const focusChat = useCallback((force = true) => {
    setChatFocus(!!force)
    recordInteraction('chat-focus', { on: !!force })
  }, [])

  const state = useMemo(() => ({
    rightPanel,
    panels,
    inspectorOpen,
    dockOpen,
    managerDrawerOpen,
    chatFocus,
  }), [rightPanel, panels, inspectorOpen, dockOpen, managerDrawerOpen, chatFocus])

  return {
    state,
    rightPanel, setRightPanel,
    panels, togglePanel,
    inspectorOpen, toggleInspector,
    dockOpen, toggleDock,
    managerDrawerOpen, toggleManagerDrawer,
    chatFocus, focusChat,
  }
}