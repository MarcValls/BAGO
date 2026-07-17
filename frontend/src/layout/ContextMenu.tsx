import { useEffect, useRef, type KeyboardEvent } from 'react';
import type { SelectionRecord } from '@/contracts/backend';
import { Icon, type IconName } from '@/shared/Icon';

export interface ContextMenuAction {
  id: string;
  label: string;
  icon: IconName;
  onClick: () => void;
  emphasis?: 'primary' | 'normal' | 'danger';
  disabled?: boolean;
  separatorBefore?: boolean;
  shortcut?: string;
  group?: string;
}

interface ContextMenuProps {
  selection: SelectionRecord;
  position: { x: number; y: number };
  actions: ContextMenuAction[];
  onClose: () => void;
}

export function ContextMenu({ selection, position, actions, onClose }: ContextMenuProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onScroll = () => onClose();
    document.addEventListener('mousedown', onDocClick);
    window.addEventListener('scroll', onScroll, true);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      window.removeEventListener('scroll', onScroll, true);
    };
  }, [onClose]);

  useEffect(() => {
    const firstEnabled = itemRefs.current.find((item) => item && !item.disabled);
    firstEnabled?.focus();
  }, [actions]);

  const adjustedPos = (() => {
    const w = 300;
    const h = Math.min(520, 96 + actions.length * 34);
    let x = position.x;
    let y = position.y;
    if (typeof window !== 'undefined') {
      if (x + w > window.innerWidth) x = window.innerWidth - w - 8;
      if (y + h > window.innerHeight) y = window.innerHeight - h - 8;
      x = Math.max(8, x);
      y = Math.max(8, y);
    }
    return { x, y };
  })();

  const run = (action: ContextMenuAction) => {
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

  const onItemKeyDown = (event: KeyboardEvent<HTMLButtonElement>, action: ContextMenuAction, index: number) => {
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
    <div
      ref={ref}
      className="context-menu"
      style={{ left: adjustedPos.x, top: adjustedPos.y }}
      role="menu"
      aria-label={`Acciones para ${selection.title}`}
    >
      <header className="context-menu-header">
        <span className="context-menu-kind">{selection.kind}</span>
        <strong>{selection.title}</strong>
      </header>
      <p className="context-menu-summary">{selection.summary}</p>
      <div className="context-menu-separator" />
      {actions.map((action, index) => {
        const previous = index > 0 ? actions[index - 1] : null;
        const showGroup = action.group && action.group !== previous?.group;
        return (
          <div key={action.id} className="context-menu-row">
            {showGroup && <div className="context-menu-group">{action.group}</div>}
            <button
              ref={(node) => { itemRefs.current[index] = node; }}
              type="button"
              role="menuitem"
              tabIndex={action.disabled ? -1 : 0}
              className={`context-menu-item ${action.emphasis === 'primary' ? 'is-primary' : ''} ${action.emphasis === 'danger' ? 'is-danger' : ''} ${action.separatorBefore ? 'has-separator' : ''}`}
              onClick={() => run(action)}
              onKeyDown={(event) => onItemKeyDown(event, action, index)}
              disabled={action.disabled}
            >
              <Icon name={action.icon} size={14} />
              <span>{action.label}</span>
              {action.shortcut && <kbd>{action.shortcut}</kbd>}
            </button>
          </div>
        );
      })}
    </div>
  );
}
