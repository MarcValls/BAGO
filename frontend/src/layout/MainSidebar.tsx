import type { ActiveSection, PanelId, UiBootstrapSnapshot } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { NAVIGATION_GROUPS } from '@/navigation/actionRegistry';
import { resolveWorkspaceAuthority } from '@/shared/workspaceAuthority';

function sectionStatus(section: ActiveSection | PanelId, snapshot: UiBootstrapSnapshot | null): 'ok' | 'warn' | 'error' | 'unknown' {
  if (!snapshot) return 'unknown';
  // Panels don't have status in the bootstrap snapshot
  if (section === 'agents' || section === 'interpreter' || section === 'github-auth' || section === 'tools' || section === 'capabilities') return 'unknown';
  if (section === 'home') return snapshot.workspace.linkedToSession ? 'ok' : 'warn';
  if (section === 'workspace') return snapshot.workspace.linkedToSession ? 'ok' : snapshot.workspace.manifestState === 'invalid' ? 'error' : 'warn';
  if (section === 'pipeline') return snapshot.jobs?.some((job) => String(job.status || '').toLowerCase().includes('running')) ? 'warn' : 'ok';
  if (section === 'evidence') return snapshot.permissions.canViewEvidence ? 'ok' : 'warn';
  if (section === 'context') return snapshot.context.state === 'blocked' ? 'error' : snapshot.context.state === 'confirmed' ? 'ok' : 'warn';
  if (section === 'system') return snapshot.model.state === 'confirmed' ? 'ok' : snapshot.model.state === 'error' ? 'error' : 'warn';
  return 'unknown';
}

interface Props {
  activeSection: ActiveSection;
  activePanel: PanelId | null;
  snapshot: UiBootstrapSnapshot | null;
  workspaceHint?: string;
  collapsed: boolean;
  onNavigate: (section: ActiveSection) => void;
  onOpenPanel: (panelId: PanelId) => void;
}

export function MainSidebar(props: Props) {
  const authority = resolveWorkspaceAuthority(props.snapshot);
  const workspaceState = authority.requiresAction ? authority.label : 'Vinculado';

  return (
    <aside className={`main-sidebar ${props.collapsed ? 'is-collapsed' : ''}`} aria-label="Navegación principal">
      <nav className="sidebar-nav" aria-label="Destinos">
        {NAVIGATION_GROUPS.map((group) => (
          <section key={group.id} className="sidebar-group" aria-label={group.label}>
            {!props.collapsed && <div className="sidebar-section-title">{group.label}</div>}
            {group.items.map((section) => {
              const isActive = section.isPanel
                ? props.activePanel === section.id
                : props.activeSection === section.id;
              return (
                <button
                  key={section.id}
                  type="button"
                  className={`sidebar-item ${isActive ? 'is-active' : ''}`}
                  aria-current={isActive ? 'page' : undefined}
                  title={props.collapsed ? `${section.label} · ${section.helper || ''}` : section.helper}
                  onClick={() => section.isPanel ? props.onOpenPanel(section.id as PanelId) : props.onNavigate(section.id as ActiveSection)}
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

      <div className="sidebar-status" title={workspaceState}>
        <span className={`status-orb state-${authority.state}`} />
        {!props.collapsed && (
          <div>
            <strong>{authority.projectLabel || props.workspaceHint || 'BAGO'}</strong>
            <span>{workspaceState}</span>
          </div>
        )}
      </div>
    </aside>
  );
}
