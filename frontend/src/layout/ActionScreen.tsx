import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent } from 'react';
import { Icon, type IconName } from '@/shared/Icon';

export interface ActionScreenAction {
  id: string;
  label: string;
  icon?: IconName;
  emphasis?: 'primary' | 'normal' | 'danger';
  disabled?: boolean;
  separatorBefore?: boolean;
  group?: string;
  shortcut?: string;
  onClick: () => void;
}

interface ActionScreenProps {
  title: string;
  kind?: string;
  summary?: string;
  actions: ActionScreenAction[];
  onClose: () => void;
}

export function ActionScreen({ title, kind, summary, actions, onClose }: ActionScreenProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        onClose();
      }
    };
    const onDocClick = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('keydown', onKeyDown, true);
    document.addEventListener('mousedown', onDocClick, true);
    return () => {
      document.removeEventListener('keydown', onKeyDown, true);
      document.removeEventListener('mousedown', onDocClick, true);
    };
  }, [onClose]);

  useEffect(() => {
    const firstEnabled = itemRefs.current.find((item) => item && !item.disabled);
    firstEnabled?.focus();
  }, [actions]);

  const run = (action: ActionScreenAction) => {
    if (action.disabled) return;
    action.onClick();
    onClose();
  };

  const focusByDelta = (currentIndex: number, delta: number) => {
    const enabled = actions
      .map((action, index) => ({ action, index }))
      .filter(({ action }) => !action.disabled);
    if (!enabled.length) return;
    const currentEnabledIndex = enabled.findIndex(({ index }) => index === currentIndex);
    const next = enabled[(currentEnabledIndex + delta + enabled.length) % enabled.length] || enabled[0];
    itemRefs.current[next.index]?.focus();
  };

  const onItemKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, action: ActionScreenAction, index: number) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      focusByDelta(index, 1);
      return;
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      focusByDelta(index, -1);
      return;
    }
    if (event.key === 'Home') {
      event.preventDefault();
      itemRefs.current.find((item) => item && !item.disabled)?.focus();
      return;
    }
    if (event.key === 'End') {
      event.preventDefault();
      [...itemRefs.current].reverse().find((item) => item && !item.disabled)?.focus();
      return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      run(action);
    }
  };

  return (
    <div className="action-screen-overlay" role="dialog" aria-modal="true" aria-label={`Acciones para ${title}`}>
      <div className="action-screen-backdrop" onClick={onClose} aria-hidden="true" />
      <div ref={ref} className="action-screen">
        <header className="action-screen-header">
          <div className="action-screen-title-row">
            {kind && <span className="action-screen-kind">{kind}</span>}
            <h3>{title}</h3>
          </div>
          <button
            type="button"
            className="icon-button"
            title="Cerrar"
            aria-label="Cerrar acciones"
            onClick={onClose}
          >
            <Icon name="close" size={16} />
          </button>
        </header>
        {summary && <p className="action-screen-summary">{summary}</p>}
        <section className="action-screen-body" role="menu">
          {actions.map((action, index) => {
            const previous = index > 0 ? actions[index - 1] : null;
            const showGroup = action.group && action.group !== previous?.group;
            return (
              <div key={action.id} className="action-screen-row">
                {showGroup && <div className="action-screen-group" role="presentation">{action.group}</div>}
                <button
                  ref={(node) => { itemRefs.current[index] = node; }}
                  type="button"
                  role="menuitem"
                  tabIndex={action.disabled ? -1 : 0}
                  className={`action-screen-item ${action.emphasis === 'primary' ? 'is-primary' : ''} ${action.emphasis === 'danger' ? 'is-danger' : ''} ${action.separatorBefore ? 'has-separator' : ''}`}
                  onClick={() => run(action)}
                  onKeyDown={(event) => onItemKeyDown(event, action, index)}
                  disabled={action.disabled}
                >
                  {action.icon && <Icon name={action.icon} size={16} />}
                  <span>{action.label}</span>
                  {action.shortcut && <kbd>{action.shortcut}</kbd>}
                </button>
              </div>
            );
          })}
        </section>
      </div>
    </div>
  );
}
