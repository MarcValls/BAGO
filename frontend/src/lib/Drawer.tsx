// src/lib/Drawer.tsx
// Panel deslizante desde la derecha. Como el inspector del Workspace
// pero aplicable a cualquier contexto.

import { useEffect, type ReactNode } from 'react';
import { Icon } from '@/shared/Icon';

interface Props {
  open: boolean;
  title: string;
  subtitle?: string;
  width?: number;
  onClose: () => void;
  children: ReactNode;
}

export function Drawer(props: Props) {
  useEffect(() => {
    if (!props.open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') props.onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [props.open, props.onClose]);

  if (!props.open) return null;

  return (
    <div className="drawer-backdrop" onClick={props.onClose}>
      <aside
        className="drawer-shell"
        style={{ width: props.width || 420 }}
        onClick={(event) => event.stopPropagation()}
        role="complementary"
        aria-label={props.title}
      >
        <header className="drawer-header">
          <div>
            <strong>{props.title}</strong>
            {props.subtitle && <small>{props.subtitle}</small>}
          </div>
          <button
            type="button"
            className="icon-button"
            onClick={props.onClose}
            aria-label="Cerrar"
          >
            <Icon name="close" size={14} />
          </button>
        </header>
        <div className="drawer-body">{props.children}</div>
      </aside>
    </div>
  );
}
