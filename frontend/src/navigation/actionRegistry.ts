import type { ActiveSection } from '@/contracts/backend';
import type { IconName } from '@/shared/Icon';

export interface NavigationItem {
  id: ActiveSection;
  label: string;
  icon: IconName;
  helper: string;
  shortcut: string;
}

export interface NavigationGroup {
  id: string;
  label: string;
  items: NavigationItem[];
}

export interface BagoAction {
  id: string;
  object: string;
  verb: string;
  label: string;
  group: string;
  icon: IconName;
  shortcut?: string;
  keywords?: string[];
  action: () => void;
}

export const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    id: 'main',
    label: 'Principal',
    items: [
      { id: 'home', label: 'Inicio', icon: 'home', helper: 'Conversación y punto de entrada', shortcut: 'Ctrl+1' },
      { id: 'workspace', label: 'Workspace', icon: 'workspace', helper: 'Archivos, fuentes y directorio de trabajo', shortcut: 'Ctrl+2' }
    ]
  },
  {
    id: 'work',
    label: 'Trabajo',
    items: [
      { id: 'context', label: 'Contexto', icon: 'context', helper: 'Recopilar y preparar el contexto de trabajo', shortcut: 'Ctrl+3' },
      { id: 'pipeline', label: 'Pipeline', icon: 'pipeline', helper: 'Plan, pasos y jobs', shortcut: 'Ctrl+4' },
      { id: 'evidence', label: 'Evidencia', icon: 'evidence', helper: 'Claims, recibos y trazas', shortcut: 'Ctrl+5' },
      { id: 'graph', label: 'Grafo', icon: 'graph', helper: 'Mapa operativo del workspace', shortcut: 'Ctrl+6' }
    ]
  },
  {
    id: 'system',
    label: 'Sistema',
    items: [
      { id: 'system', label: 'Operación', icon: 'system', helper: 'Router, proveedores y runtime', shortcut: 'Ctrl+7' }
    ]
  }
];

export const NAVIGATION_ORDER: ActiveSection[] = NAVIGATION_GROUPS.flatMap((group) => group.items.map((item) => item.id));

export const SECTION_LABELS: Record<ActiveSection, string> = {
  home: 'Inicio',
  workspace: 'Workspace',
  context: 'Contexto',
  pipeline: 'Pipeline',
  evidence: 'Evidencia',
  graph: 'Grafo',
  system: 'Operación',
  chat: 'Inicio'
};

interface ShellActionHandlers {
  navigate: (section: ActiveSection) => void;
  openWorkspace: () => void;
  toggleSidebar: () => void;
  toggleFocus: () => void;
  toggleReview: () => void;
  runCommand: (command: string) => void;
  runContextCommand: (command: string) => void;
  sidebarCollapsed: boolean;
  globalMode: 'normal' | 'focus' | 'review';
}

export function createShellActions(handlers: ShellActionHandlers): BagoAction[] {
  const navigation = NAVIGATION_GROUPS.flatMap((group) => group.items).map((item) => ({
    id: `nav-${item.id}`,
    object: item.label,
    verb: 'Abrir',
    label: `${item.label} · Abrir`,
    group: 'Navegación',
    icon: item.icon,
    shortcut: item.shortcut,
    keywords: [item.helper],
    action: () => handlers.navigate(item.id)
  } satisfies BagoAction));

  return [
    ...navigation,
    {
      id: 'workspace-change', object: 'Workspace', verb: 'Cambiar', label: 'Workspace · Cambiar',
      group: 'Workspace', icon: 'folder', keywords: ['directorio', 'carpeta', 'proyecto'], action: handlers.openWorkspace
    },
    {
      id: 'toggle-sidebar', object: 'Navegación', verb: handlers.sidebarCollapsed ? 'Mostrar' : 'Ocultar',
      label: `Navegación · ${handlers.sidebarCollapsed ? 'Mostrar' : 'Ocultar'}`, group: 'Vista', icon: 'menu', shortcut: 'Ctrl+B', action: handlers.toggleSidebar
    },
    {
      id: 'focus', object: 'Vista', verb: handlers.globalMode === 'focus' ? 'Salir de Focus' : 'Activar Focus',
      label: `Vista · ${handlers.globalMode === 'focus' ? 'Salir de Focus' : 'Activar Focus'}`, group: 'Vista', icon: 'focus', shortcut: 'F11', action: handlers.toggleFocus
    },
    {
      id: 'review', object: 'Vista', verb: handlers.globalMode === 'review' ? 'Salir de Lectura' : 'Activar Lectura',
      label: `Vista · ${handlers.globalMode === 'review' ? 'Salir de Lectura' : 'Activar Lectura'}`, group: 'Vista', icon: 'review', shortcut: 'F12', action: handlers.toggleReview
    },
    {
      id: 'cmd-status', object: 'Sistema', verb: 'Consultar estado', label: 'Sistema · Consultar estado',
      group: 'Comandos', icon: 'live', keywords: ['/status'], action: () => handlers.runCommand('/status')
    },
    {
      id: 'cmd-session', object: 'Sesión', verb: 'Inspeccionar', label: 'Sesión · Inspeccionar',
      group: 'Comandos', icon: 'session', keywords: ['/session'], action: () => handlers.runCommand('/session')
    },
    {
      id: 'ctx-attach', object: 'Contexto', verb: 'Adjuntar', label: 'Contexto · Adjuntar',
      group: 'Contexto', icon: 'attach', keywords: ['/context attach'], action: () => handlers.runContextCommand('/context attach')
    },
    {
      id: 'ctx-measure', object: 'Contexto', verb: 'Medir', label: 'Contexto · Medir',
      group: 'Contexto', icon: 'inspector', keywords: ['/context measure'], action: () => handlers.runContextCommand('/context measure')
    },
    {
      id: 'ctx-certify', object: 'Contexto', verb: 'Certificar', label: 'Contexto · Certificar',
      group: 'Contexto', icon: 'check', keywords: ['/context certify'], action: () => handlers.runContextCommand('/context certify')
    }
  ];
}
