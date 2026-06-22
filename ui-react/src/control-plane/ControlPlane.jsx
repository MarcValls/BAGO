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
  const push = (message) => {
    setToast(message)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(() => setToast(null), 2200)
  }
  return { toast, push }
}

export default function ControlPlane() {
  const [room, setRoom] = useState('chat')
  const [context, setContext] = useState({ install: 'inst-A', node: null, patch: null })
  const [theme, setTheme] = useState(getInitialTheme)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [inspectorOpen, setInspectorOpen] = useState(true)
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

  useEffect(() => {
    window.localStorage.setItem('bago-theme', theme)
    document.documentElement.setAttribute('data-bago-theme', theme)
  }, [theme])

  const activeRoom = room

  function navigate(nextRoom) {
    setRoom(nextRoom)
  }

  function onOpenTerminal(installId) {
    setTerminalInstall(installId || context.install || null)
  }

  const handleFileSelect = async (node) => {
    if (node.type !== 'file') return
    setSelectedFile(node)
    navigate('file')
    setSelectedFileLoading(true)
    try {
      const content = await chatApi.readFile(node.path)
      setSelectedFileContent(content ?? '')
    } catch (e) {
      push('error', `Could not read ${node.name}: ${e.message}`)
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
      const context = `Contexto del archivo del proyecto ${node.path}:\n\`\`\`\n${text}\n\`\`\``
      chatControl.submit(context)
      push('info', `Enviado al chat: ${node.name}`)
    } catch (e) {
      push('error', `Could not send ${node.name}: ${e.message}`)
    }
  }

  function onAction(type, payload) {
    if (type === 'open-install') {
      setContext((c) => ({ ...c, install: payload }))
      navigate('installations')
    } else if (type === 'open-node') {
      setContext((c) => ({ ...c, node: payload }))
      navigate('nodes')
    } else if (type === 'open-terminal') {
      onOpenTerminal(payload)
    } else if (type === 'toast') {
      push(payload || 'Acción no disponible (SIMULADO)')
    } else {
      push(`Acción "${type}" no disponible (SIMULADO)`)
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
        if (value === 'theme') setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
        if (value === 'sidebar') setSidebarOpen((v) => !v)
        if (value === 'inspector') setInspectorOpen((v) => !v)
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
      case 'toast':
        push({
          snapshot: 'Snapshot guardado',
          export: 'Chat exportado',
          exit: 'Sesión cerrada',
          copy: 'Chat copiado',
          prefs: 'Preferencias abiertas',
          sync: 'Sincronización iniciada',
          index: 'Indexación knowledge iniciada',
          supervisor: 'Supervisor activo',
          runtime: 'Runtime activo',
          codex: 'Codex CLI con 18 claims',
          command: 'Comando listo para ejecutar',
          'recent-plan': 'Repetiendo último plan',
        }[value] || value)
        break
      default:
        break
    }
  }

  const paletteItems = useMemo(() => {
    const rooms = [
      { id: 'chat', label: 'Chat', section: 'Vista', action: 'room:chat' },
      ...ROOMS.map((r) => ({ id: r.id, label: r.label, section: 'Rooms', action: `room:${r.id}` })),
    ]
    const tools = [
      { id: 'sync', label: 'Sincronizar', section: 'Herramientas', action: 'toast:sync' },
      { id: 'patchbay-tool', label: 'Abrir Patchbay', section: 'Herramientas', action: 'room:patchbay' },
      { id: 'health-tool', label: 'Diagnóstico', section: 'Herramientas', action: 'room:health' },
      { id: 'index', label: 'Indexar knowledge', section: 'Herramientas', action: 'toast:index' },
    ]
    const agents = [
      { id: 'supervisor', label: 'Supervisor', section: 'Agentes', action: 'toast:supervisor' },
      { id: 'runtime', label: 'Runtime', section: 'Agentes', action: 'toast:runtime' },
      { id: 'codex', label: 'Codex CLI', section: 'Agentes', action: 'toast:codex' },
    ]
    return [...rooms, ...tools, ...agents].filter((it) =>
      it.label.toLowerCase().includes(paletteQuery.toLowerCase())
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
        setPaletteOpen((v) => !v)
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
        setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'b') {
        event.preventDefault()
        setSidebarOpen((v) => !v)
        return
      }
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'i') {
        event.preventDefault()
        setInspectorOpen((v) => !v)
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
        push('Comando rápido listo')
        return
      }
      if (event.ctrlKey && !event.altKey && !event.shiftKey && /^Digit[1-8]$/.test(event.code)) {
        event.preventDefault()
        const index = parseInt(event.code.replace('Digit', ''), 10) - 1
        if (ROOMS[index]) navigate(ROOMS[index].id)
        return
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [paletteOpen])

  useEffect(() => {
    if (paletteOpen && paletteInputRef.current) {
      paletteInputRef.current.focus()
    }
  }, [paletteOpen])

  return (
    <div className={`bago-cp bago-cp-${theme}`}>
      {toast ? <div className="cp-toast">{toast}</div> : null}

      {planOpen ? (
        <PlanSequencer
          onClose={() => setPlanOpen(false)}
          onToast={(msg) => push(msg)}
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
          push={push}
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