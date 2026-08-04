import type { ActiveSection, UiBootstrapSnapshot } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';

interface Props {
  snapshot: UiBootstrapSnapshot | null;
  workspaceHint?: string;
  apiBase: string;
  apiToken: string;
  activeSection: ActiveSection;
  busy?: boolean;
  onApiConfigChange: (patch: { apiBase?: string; apiToken?: string }) => void;
  onOpenPalette: () => void;
  onToggleSidebar: () => void;
  onRefresh: () => void;
  onSetMode: (mode: 'normal' | 'focus' | 'review') => void;
  onSetAppearanceTheme: (theme: 'dark' | 'light') => void;
  onRunCommand: (command: string) => void;
  onChooseWorkspace: () => void;
  onOpenHelp?: () => void;
  globalMode: 'normal' | 'focus' | 'review';
  appearanceTheme: 'dark' | 'light';
  sidebarCollapsed: boolean;
}

const sectionLabels: Record<ActiveSection, string> = {
  home: 'Inicio',
  chat: 'Chat',
  workspace: 'Workspace',
  graph: 'Grafo',
  pipeline: 'Pipeline',
  evidence: 'Evidencia',
  context: 'Contexto',
  system: 'Operación'
};

function StatePill({ state, busy }: { state: string; busy?: boolean }) {
  return (
    <span className={`header-state state-${busy ? 'loading' : state}`}>
      <span className="status-dot" />
      {busy ? 'cargando' : state}
    </span>
  );
}

export function GlobalHeader(props: Props) {
  const workspace = props.snapshot?.workspace.id || props.workspaceHint || 'Sin workspace';
  const state = props.snapshot?.system.state || 'unknown';
  const menuState = props.snapshot?.menuState;
  const guidance = [
    menuState?.activeCenter,
    menuState?.currentScreen,
    menuState?.operationState || menuState?.recommendedAction
  ].filter(Boolean).join(' · ');

  if (props.globalMode === 'focus') {
    return (
      <header className="global-header focus-header">
        <div className="header-brand compact">
          <div className="brand-mark">B</div>
          <div>
            <strong>Focus</strong>
            <span>{sectionLabels[props.activeSection]} · {workspace}</span>
          </div>
        </div>
        <div className="focus-header-actions">
          <label className="header-theme-picker" title="Opciones de apariencia">
            <span>Tema</span>
            <select
              value={props.appearanceTheme}
              onChange={(event) => props.onSetAppearanceTheme(event.target.value === 'light' ? 'light' : 'dark')}
            >
              <option value="dark">Oscuro</option>
              <option value="light">Claro</option>
            </select>
          </label>
          <button className="header-button" type="button" onClick={props.onOpenPalette} title="Abrir comandos con Ctrl K">
            <Icon name="search" /> Comandos <kbd>Ctrl K</kbd>
          </button>
          <button className="header-button" type="button" onClick={props.onChooseWorkspace} title="Elegir workspace">
            <Icon name="workspace" /> Workspace
          </button>
          <button className="primary-button compact" type="button" onClick={() => props.onSetMode('normal')}>
            Salir de Focus
          </button>
        </div>
      </header>
    );
  }

  return (
    <header className={`global-header mode-${props.globalMode}`}>
      <div className="header-leading">
        <button className="icon-button" type="button" onClick={props.onToggleSidebar} title={props.sidebarCollapsed ? 'Mostrar navegación (Ctrl B)' : 'Ocultar navegación (Ctrl B)'}>
          <Icon name="menu" />
        </button>
        <div className="header-brand">
          <div className="brand-mark">B</div>
          <div>
            <strong>BAGO</strong>
            <span>{workspace}</span>
          </div>
        </div>
        <div className="header-divider" />
        <div className="header-location">
          <span>{sectionLabels[props.activeSection]}</span>
          {props.snapshot?.system.objective && <small>{props.snapshot.system.objective}</small>}
          {guidance && <small title={menuState?.version ? `Contrato ${menuState.version}` : undefined}>{guidance}</small>}
        </div>
      </div>

      <div className="header-actions">
        <label className="header-theme-picker" title="Opciones de apariencia">
          <span>Tema</span>
          <select
            value={props.appearanceTheme}
            onChange={(event) => props.onSetAppearanceTheme(event.target.value === 'light' ? 'light' : 'dark')}
          >
            <option value="dark">Oscuro</option>
            <option value="light">Claro</option>
          </select>
        </label>
        <StatePill state={state} busy={props.busy} />
        <button className="header-button command-entry" type="button" onClick={props.onOpenPalette} title="Comandos y búsqueda">
          <Icon name="search" />
          <span>Comandos</span>
          <kbd>Ctrl K</kbd>
        </button>
        <button className="header-button" type="button" onClick={props.onChooseWorkspace} title="Cambiar workspace activo">
          <Icon name="folder" />
          <span>Cambiar workspace</span>
        </button>
        <button className="icon-button" type="button" onClick={props.onOpenHelp} title="Atajos y ayuda (?)">
          <Icon name="prompt" />
        </button>
      </div>
    </header>
  );
}
