import { Modal } from '@/lib/Modal';

interface Props {
  open: boolean;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog(props: Props) {
  return (
    <Modal
      open={props.open}
      title={props.title}
      subtitle={props.description}
      width={480}
      onClose={() => { if (!props.busy) props.onClose(); }}
      footer={(
        <>
          <button type="button" className="secondary-button" disabled={props.busy} onClick={props.onClose}>
            {props.cancelLabel || 'Cancelar'}
          </button>
          <button type="button" className="primary-button" data-autofocus disabled={props.busy} onClick={props.onConfirm}>
            {props.busy ? 'Aplicando…' : props.confirmLabel || 'Confirmar'}
          </button>
        </>
      )}
    >
      <p className="confirmation-copy">Revisa la acción antes de continuar.</p>
    </Modal>
  );
}
