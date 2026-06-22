import { useEffect, useMemo, useRef, useState } from 'react'
import { useBagoChat } from '../useBagoChat'
import { useChatCenter } from '../useChatCenter'
import { chatApi } from '../api'
import PlanSequencer from './components/PlanSequencer'
import GlobalBar from './components/GlobalBar'
import ActivityBar from './components/ActivityBar'
import ProjectExplorer from './components/ProjectExplorer'
import EditorArea from './components/EditorArea'
import Inspector from './components/Inspector'
import CommandPalette from './components/CommandPalette'
import StatusBar from './components/StatusBar'
import TerminalOverlay from './components/TerminalOverlay'
import { ROOMS } from './components/constants'
import { useBagoActions } from './useBagoActions'
import './control-plane.css'
import './control-plane.codex.css'
import './rpg-views.css'

function getInitialTheme() {
  if (typeof window === 'undefined') return 'dark'
  const saved = window.localStorage.getItem('bago-theme')
  if (saved === 'light' || saved === 'dark') return saved
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

function useToast() {
  const [toast, setToast] = useState(null)
  const timerRef = useRef(null)
  const push = (first, second) => {
    const message = second || first
    setToast(message ? String(message) : null)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setToast(null), 3200)
  }
  return { toast, push }
}

export default function ControlPlane() {
  const [room, setRoom] = useState('chat')
  const [context, setContext] = useState({ install: null, node: null, patch: null })
  const [theme, setTheme] = useState(getInitialTheme)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [openMenu, setOpenMenu] = useState(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [paletteQuery, setPaletteQuery] = useState('')
  const [planOpen, setPlanOpen] = useState(false)
  const [terminalInstall, setTerminalInstall] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedFileContent, setSelectedFileContent] = useState('')
  const [selectedFileLoading, setSelectedFileLoading] = useState(false)
  const chatControl = useBagoChat()
  const chatCenter = useChatCenter()
  const { toast, push } = useToast()
  const searchRef = useRef(null)
  const paletteInputRef = useRef(null)

  function navigate(nextRoom) {
    setRoom(nextRoom)
  }

  function onOpenTerminal(installId) {
    setTerminalInstall(installId || context.install || null)
  }

  const actions = useBagoActions({
    context,
    setContext,
    navigate,
    onOpenTerminal,
    push,
  })

  useEffect(() => {
    window.localStorage.setItem('bago-theme', theme)
    document.documentElement.setAttribute('data-bago-theme', theme)
  }, [theme])

  const activeRoom = room

  const handleFileSelect = async (node) => {
    if (node.type !== 'file') return
    setSelectedFile(node)
    navigate('file')
    setSelectedFileLoading(true)
    try {
      const content = await chatApi.readFile(node.path)
      setSelectedFileContent(content ?? '')
    } catch (error) {
      push(`No se pudo leer ${node.name}: ${error.message}`)
      setSelectedFileContent('')
    } finally {
      setSelectedFileLoading(false)
    }
  }

  const handleCloseFile = () => {
    setSelectedFile(null)
    setSelectedFileContent('')
    navigate('chat')
  }

  const handleSendFileToChat = async (node) => {
    try {
      const content = await chatApi.readFile(node.path)
      const text = typeof content === 'string' ? content : JSON.stringify(content, null, 2)
      const fileContext = `Contexto del archivo del proyecto ${node.path}:\n\`\`\`\n${text}\n\`\`\``
      chatControl.submit(fileContext)
      push(`Enviado al chat: ${node.name}`)
    } catch (error) {
      push(`No se pudo enviar ${node.name}: ${error.message}`)
    }
  }

  async function onAction(type, payload) {
    try {
      return await actions.runAction(type, payload)
    } catch {
      return null
    }
  }

  function handleMenuAction(action) {
    setOpenMenu(null)
    const [kind, value] = action.split(':')
    switch (kind) {
      case 'room':
        navigate(value)
        break
      case 'toggle':
        if (value === 'theme') setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
        if (value === 'sidebar') setSidebarOpen((current) => !current)
        if (value === 'inspector') setInspectorOpen((current) => !current)
        break
      case 'focus':
        if (value === 'chat') navigate('chat')
        break
      case 'palette':
        setPaletteOpen(true)
        break
      case 'plan':
        if (value === 'open') setPlanOpen(true)
        break
      case 'action':
        onAction(value)
        break
      default:
        push(`La orden ${action} no tiene contrato operativo`)
        break
    }
  }

  const paletteItems = useMemo(() => {
    const rooms = [
      { id: 'chat', label: 'Chat', section: 'Vista', action: 'room:chat' },
      ...ROOMS.map((item) => ({ id: item.id, label: item.label, section: 'Vistas', action: `room:${item.id}` })),
    ]
    const tools = [
      { id: 'validate-nodes', label: 'Validar nodos', section: 'Operaciones', action: 'action:validate-nodes' },
      { id: 'cleanup-zombies', label: 'Limpiar procesos BAGO', section: 'Operaciones', action: 'action:cleanup-zombies' },
      { id: 'supervisor-status', label: 'Estado del supervisor', section: 'Supervisor', action: 'action:supervisor-status' },
      { id: 'supervisor-start', label: 'Iniciar supervisor', section: 'Supervisor', action: 'action:supervisor-start' },
      { id: 'supervisor-stop', label: 'Detener supervisor', section: 'Supervisor', action: 'action:supervisor-stop' },
    ]
    return [...rooms, ...tools].filter((item) =>
      item.label.toLowerCase().includes(paletteQuery.toLowerCase())
    )
  }, [paletteQuery])

  useEffect(() => {
    function onKey(event) {
      if (event.key === 'Escape') {
        setOpenMenu(null)
        setPaletteOpen(false)
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setPaletteOpen((current) => !current)
        return
      }
      if (paletteOpen) return

      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'c') {
        event.preventDefault()
        navigate('chat')
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'm') {
        event.preventDefault()
        navigate('dashboard')
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'l') {
        event.preventDefault()
        setTheme((current) => (current === 'dark' ? 'light' : 'dark'))
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'b') {
        event.preventDefault()
        setSidebarOpen((current) => !current)
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'i') {
        event.preventDefault()
        setInspectorOpen((current) => !current)
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'p') {
        event.preventDefault()
        navigate('patchbay')
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'e') {
        event.preventDefault()
        setPlanOpen(true)
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === 'x') {
        event.preventDefault()
        onAction('validate-nodes')
        return
      }
      if (event.ctrlKey && !event.altKey && !event.shiftKey && /^Digit[1-8]$/.test(event.code)) {
        event.preventDefault()
        const index = parseInt(event.code.replace('Digit', ''), 10) - 1
        if (ROOMS[index]) navigate(ROOMS[index].id)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [paletteOpen])

  useEffect(() => {
    if (paletteOpen && paletteInputRef.current) paletteInputRef.current.focus()
  }, [paletteOpen])

  return (
    <div className={`bago-cp bago-cp-${theme}`}>
      {toast ? <div className="cp-toast">{toast}</div> : null}
      {actions.busyAction ? <div className="cp-toast">Ejecutando: {actions.busyAction}</div> : null}

      {planOpen ? (
        <PlanSequencer
          onClose={() => setPlanOpen(false)}
          onToast={(message) => push(message)}
        />
      ) : null}

      <CommandPalette
        paletteOpen={paletteOpen}
        setPaletteOpen={setPaletteOpen}
        paletteQuery={paletteQuery}
        setPaletteQuery={setPaletteQuery}
        paletteInputRef={paletteInputRef}
        paletteItems={paletteItems}
        onMenuAction={handleMenuAction}
      />

      <GlobalBar
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        inspectorOpen={inspectorOpen}
        setInspectorOpen={setInspectorOpen}
        theme={theme}
        setTheme={setTheme}
        openMenu={openMenu}
        setOpenMenu={setOpenMenu}
        onMenuAction={handleMenuAction}
        contextInstall={context.install}
      />

      <div className="cp-workspace">
        <ActivityBar
          activeRoom={activeRoom}
          navigate={navigate}
          theme={theme}
          setTheme={setTheme}
        />

        {sidebarOpen && (
          <div className="cp-sidebar-vsc">
            <div className="cp-sidebar-head">
              <span>Proyecto</span>
              <button
                className="cp-sidebar-close"
                onClick={() => setSidebarOpen(false)}
                title="Cerrar sidebar"
              >
                ×
              </button>
            </div>
            <div className="cp-sidebar-body" style={{ padding: 0 }}>
              <ProjectExplorer
                selectedFile={selectedFile}
                onSelectFile={handleFileSelect}
                onSendToChat={handleSendFileToChat}
              />
            </div>
          </div>
        )}

        <EditorArea
          activeRoom={activeRoom}
          navigate={navigate}
          searchRef={searchRef}
          context={context}
          setContext={setContext}
          onAction={onAction}
          onOpenTerminal={onOpenTerminal}
          chatControl={chatControl}
          chatCenter={chatCenter}
          selectedFile={selectedFile}
          selectedFileContent={selectedFileContent}
          selectedFileLoading={selectedFileLoading}
          onCloseFile={handleCloseFile}
        />

        <Inspector
          inspectorOpen={inspectorOpen}
          setInspectorOpen={setInspectorOpen}
          navigate={navigate}
          context={context}
          setContext={setContext}
          onAction={onAction}
          busyAction={actions.busyAction}
          capabilities={actions.capabilities}
        />
      </div>

      <StatusBar
        context={context}
        setSidebarOpen={setSidebarOpen}
        setInspectorOpen={setInspectorOpen}
      />

      <TerminalOverlay
        terminalInstall={terminalInstall}
        setTerminalInstall={setTerminalInstall}
        chatControl={chatControl}
      />
    </div>
  )
}
