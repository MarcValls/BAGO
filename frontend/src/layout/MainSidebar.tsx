import type { ActiveSection, UiAction, UiBootstrapSnapshot } from '@/contracts/backend';
import type { OpeningDecision } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { NAVIGATION_GROUPS } from '@/navigation/actionRegistry';

function sectionStatus(section: ActiveSection, snapshot: UiBootstrapSnapshot | null): 'ok' | 'warn' | 'error' | 'unknown' {
  if (!snapshot) return 'unknown';
  if (section === 'home') return snapshot.workspace.linkedToSession ? 'ok' : 'warn';
  if (section === 'workspace') return snapshot.workspace.linkedToSession ? 'ok' : snapshot.workspace.manifestState === 'invalid' ? 'error' : 'warn';
  if (section === 'pipeline') return snapshot.jobs?.some((job) => String(job.status || '').toLowerCase().includes('running')) ? 'warn' : 'ok';
  if (section === 'evidence') return snapshot.permissions.canViewEvidence ? 'ok' : 'warn';
  if (section === 'context') return snapshot.context.state === 'blocked' ? 'error' : snapshot.context.state === 'confirmed' ? 'ok' : 'warn';
  if (section === 'graph') return snapshot.workspace.linkedToSession ? 'ok' : 'warn';
  if (section === 'system') return snapshot.model.state === 'confirmed' ? 'ok' : snapshot.model.state === 'error' ? 'error' : 'warn';
  return 'unknown';
}

function actionTextMatches(action: UiAction, text: string): boolean {
  const needle = text.trim().toLowerCase();
  if (!needle) return false;
  const id = action.id.toLowerCase();
  const label = action.label.toLowerCase();
  const contractAction = String(action.payload?.contractAction || '').toLowerCase();
  return id === needle || label === needle || contractAction === needle || id.includes(needle) || label.includes(needle) || needle.includes(id) || needle.includes(label);
}

interface Props {
  activeSection: ActiveSection;
  snapshot: UiBootstrapSnapshot | null;
  opening: OpeningDecision;
  actions: UiAction[];
  workspaceHint?: string;
  collapsed: boolean;
  onNavigate: (section: ActiveSection) => void;
  onRunAction: (action: UiAction) => void;
}

export function MainSidebar(props: Props) {
  const visibleActions = props.actions.filter((action) => action.visible).slice(0, 2);
  const guidedAction = props.snapshot?.menuState?.recommendedAction
    ? props.actions.find((action) => actionTextMatches(action, props.snapshot?.menuState?.recommendedAction || ''))
    : visibleActions[0];
  const workspaceState = props.snapshot?.workspace.linkedToSession
    ? 'Vinculado'
    : props.workspaceHint
      ? props.workspaceHint
      : props.opening.label;

  return (
    <aside className={`main-sidebar ${props.collapsed ? 'is-collapsed' : ''}`} aria-label="Navegación principal">
      <nav className="sidebar-nav" aria-label="Destinos">
        {NAVIGATION_GROUPS.map((group) => (
          <section key={group.id} className="sidebar-group" aria-label={group.label}>
            {!props.collapsed && <div className="sidebar-section-title">{group.label}</div>}
            {group.items.map((section) => {
              const isActive = props.activeSection === section.id;
              return (
                <button
                  key={section.id}
                  type="button"
                  className={`sidebar-item ${isActive ? 'is-active' : ''}`}
                  aria-current={isActive ? 'page' : undefined}
                  title={props.collapsed ? `${section.label} · ${section.helper || ''}` : section.helper}
                  onClick={() => props.onNavigate(section.id)}
                >
                  <Icon name={section.icon} />
                  {!props.collapsed && <span className="sidebar-item-label">{section.label}</span>}
                  {section.shortcut && !props.collapsed && (
                    <kbd className="sidebar-item-shortcut">{section.shortcut}</kbd>
                  )}
                  <span className={`sidebar-status-dot status-${sectionStatus(section.id, props.snapshot)}`} />
                  {isActive && <span className="sidebar-active-mark" />}
                </button>
              );
            })}
          </section>
        ))}
      </nav>

      <div className="sidebar-spacer" />

      {!props.collapsed && props.activeSection !== 'home' && props.activeSection !== 'context' && visibleActions.length > 0 && (
        <section className="sidebar-actions" aria-label="Acciones recomendadas">
          <div className="sidebar-section-title">Siguiente</div>
          {visibleActions.map((action) => (
            <button key={action.id} type="button" disabled={!action.enabled} title={action.reasonDisabled} className={guidedAction?.id === action.id ? 'is-guided-target' : ''} onClick={() => props.onRunAction(action)}>
              <span>{action.label}</span>
              <Icon name="chevron" size={15} />
            </button>
          ))}
        </section>
      )}

      <div className="sidebar-status" title={workspaceState}>
        <span className={`status-orb state-${props.snapshot?.system.state || 'unknown'}`} />
        {!props.collapsed && (
          <div>
            <strong>{props.snapshot?.workspace.id || props.workspaceHint || 'BAGO'}</strong>
            <span>{workspaceState}</span>
          </div>
        )}
      </div>
    </aside>
  );
}
