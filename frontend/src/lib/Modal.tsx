// src/lib/Modal.tsx
// Modal genérico. Cierra con Escape, click fuera, o botón ×.

import { useId, type CSSProperties, type ReactNode } from 'react';
import { Icon } from '@/shared/Icon';
import { useDialogAccessibility } from '@/lib/useDialogAccessibility';

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
  const ref = useDialogAccessibility<HTMLDivElement>(props.open, props.onClose);
  const titleId = useId();
  const subtitleId = useId();

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
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={props.subtitle ? subtitleId : undefined}
      >
        <header className="modal-header">
          <div>
            <strong id={titleId}>{props.title}</strong>
            {props.subtitle && <small id={subtitleId}>{props.subtitle}</small>}
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
