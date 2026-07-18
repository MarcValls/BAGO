// src/lib/Modal.tsx
// Modal genérico. Cierra con Escape, click fuera, o botón ×.

import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { Icon } from '@/shared/Icon';

interface Props {
  open: boolean;
  title: string;
  subtitle?: string;
  width?: number;
  height?: CSSProperties['height'];
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
}

export function Modal(props: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!props.open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') props.onClose();
    };
    window.addEventListener('keydown', handler);
    // Foco al abrir.
    setTimeout(() => ref.current?.focus(), 30);
    return () => window.removeEventListener('keydown', handler);
  }, [props.open, props.onClose]);

  if (!props.open) return null;

  return (
    <div className="modal-backdrop" onClick={props.onClose}>
      <div
        ref={ref}
        tabIndex={-1}
        className="modal-shell"
        style={{
          width: props.width || 720,
          height: props.height || 'auto',
          maxHeight: '85vh'
        }}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-label={props.title}
      >
        <header className="modal-header">
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
        <div className="modal-body">{props.children}</div>
        {props.footer && <footer className="modal-footer">{props.footer}</footer>}
      </div>
    </div>
  );
}
