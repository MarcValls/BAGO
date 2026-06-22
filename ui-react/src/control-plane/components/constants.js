export const ROOMS = [
  { id: 'dashboard', label: 'Dashboard', icon: 'dashboard', color: '#3b82f6' },
  { id: 'installations', label: 'Instalaciones', icon: 'grid', color: '#10b981' },
  { id: 'patchbay', label: 'Patchbay', icon: 'patchbay', color: '#8b5cf6' },
  { id: 'nodes', label: 'Nodos', icon: 'nodes', color: '#f59e0b' },
  { id: 'pieces', label: 'Piezas', icon: 'pieces', color: '#ec4899' },
  { id: 'gear', label: 'Equipo', icon: 'user', color: '#f59e0b' },
  { id: 'rack', label: 'Rack', icon: 'grid', color: '#ef4444' },
  { id: 'releases', label: 'Releases', icon: 'releases', color: '#06b6d4' },
  { id: 'audit', label: 'Auditoría', icon: 'audit', color: '#ef4444' },
  { id: 'health', label: 'Salud', icon: 'health', color: '#22c55e' },
]

export const EXTRA_ROOMS = {
  chat: { label: 'Chat', icon: 'chat', color: '#6366f1' },
  jobs: { label: 'Jobs', icon: 'bell', color: '#f97316' },
}

export const TITLES = {
  dashboard: 'Dashboard',
  installations: 'Instalaciones',
  patchbay: 'Patchbay',
  nodes: 'Nodos',
  pieces: 'Piezas',
  gear: 'Equipo RPG',
  rack: 'Rack de ejecución',
  releases: 'Releases',
  audit: 'Auditoría',
  health: 'Salud',
  jobs: 'Jobs',
  chat: 'Chat central',
}

export const MENUS = [
  {
    id: 'file',
    label: 'Archivo',
    color: '#3b82f6', // azul
    icon: 'file',
    items: [
      { id: 'new-install', label: 'Nueva instalación', shortcut: 'Ctrl+N', action: 'room:installations', section: 'Crear' },
      { id: 'save-snapshot', label: 'Guardar snapshot', shortcut: 'Ctrl+S', action: 'toast:snapshot', section: 'Crear' },
      { id: 'export-chat', label: 'Exportar chat', action: 'toast:export', section: 'Exportar' },
      { id: 'sep1', label: '', action: 'separator' },
      { id: 'exit', label: 'Salir', action: 'toast:exit', section: 'Sesión' },
    ],
  },
  {
    id: 'edit',
    label: 'Edición',
    color: '#8b5cf6', // violeta
    icon: 'edit',
    items: [
      { id: 'copy', label: 'Copiar chat', shortcut: 'Ctrl+C', action: 'toast:copy', section: 'Portapapeles' },
      { id: 'paste', label: 'Pegar en chat', shortcut: 'Ctrl+V', action: 'focus:chat', section: 'Portapapeles' },
      { id: 'sep2', label: '', action: 'separator' },
      { id: 'prefs', label: 'Preferencias', action: 'toast:prefs', section: 'Ajustes' },
      { id: 'theme', label: 'Cambiar tema', shortcut: 'Ctrl+Shift+L', action: 'toggle:theme', section: 'Ajustes' },
    ],
  },
  {
    id: 'view',
    label: 'Vista',
    color: '#10b981', // verde
    icon: 'view',
    items: [
      { id: 'toggle-sidebar', label: 'Sidebar', shortcut: 'Ctrl+B', action: 'toggle:sidebar', section: 'Paneles' },
      { id: 'toggle-inspector', label: 'Inspector', shortcut: 'Ctrl+I', action: 'toggle:inspector', section: 'Paneles' },
      { id: 'sep3', label: '', action: 'separator' },
      { id: 'theme', label: 'Cambiar tema', shortcut: 'Ctrl+Shift+L', action: 'toggle:theme', section: 'Apariencia' },
    ],
  },
  {
    id: 'tools',
    label: 'Herramientas',
    color: '#f59e0b', // ámbar
    icon: 'tools',
    items: [
      { id: 'sync', label: 'Sincronizar', shortcut: 'Ctrl+R', action: 'toast:sync', section: 'Acciones' },
      { id: 'sep4', label: '', action: 'separator' },
      { id: 'index', label: 'Indexar knowledge', action: 'toast:index', section: 'Knowledge' },
    ],
  },
  {
    id: 'agents',
    label: 'Agentes',
    color: '#ec4899', // rosa
    icon: 'agents',
    items: [
      { id: 'supervisor', label: 'Supervisor', status: 'ok', action: 'toast:supervisor', section: 'Activos' },
      { id: 'runtime', label: 'Runtime', status: 'ok', action: 'toast:runtime', section: 'Activos' },
      { id: 'codex-cli', label: 'Codex CLI', status: 'warn', action: 'toast:codex', section: 'Activos' },
      { id: 'sep5', label: '', action: 'separator' },
      { id: 'launch-agent', label: 'Lanzar agente…', shortcut: 'Ctrl+Shift+A', action: 'palette:agents', section: 'Lanzar' },
    ],
  },
  {
    id: 'run',
    label: 'Ejecutar',
    color: '#ef4444', // rojo
    icon: 'run',
    items: [
      { id: 'run-plan', label: 'Ejecutar plan…', shortcut: 'Ctrl+Shift+E', action: 'plan:open', section: 'Plan' },
      { id: 'run-command', label: 'Comando rápido', shortcut: 'Ctrl+Shift+X', action: 'toast:command', section: 'Plan' },
      { id: 'sep6', label: '', action: 'separator' },
      { id: 'recent-plan', label: 'Repetir último plan', action: 'toast:recent-plan', section: 'Histórico' },
    ],
  },
]