// Barra inferior del pack. Una sola acción principal visible: Compilar.
// Enviar a chat aparece como acción secundaria cuando el pack está listo.
import { useState } from 'react';
import type { ContextPack, ContextPackStatus } from './contextTreeTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  pack: ContextPack | null;
  blockedReason: string | null;
  onCompile: () => void;
  onSendToChat: () => void;
  onSendToPipeline: () => void;
  onShowCompiled: () => void;
  onCopyPack: () => void;
}

function statusTone(status: ContextPackStatus): string {
  if (status === 'compiled' || status === 'valid') return 'confirmed';
  if (status === 'warning') return 'running';
  if (status === 'blocked') return 'error';
  return 'unknown';
}

function statusLabel(status: ContextPackStatus): string {
  switch (status) {
    case 'compiled': return 'compilado';
    case 'valid': return 'válido';
    case 'warning': return 'con avisos';
    case 'blocked': return 'bloqueado';
    case 'draft': return 'borrador';
    default: return status;
  }
}

export function ContextPackBar(props: Props) {
  const [actionsOpen, setActionsOpen] = useState(false);
  if (!props.pack) {
    return (
      <footer className="context-pack-bar empty">
        <span className="context-pack-bar-empty-text">Sin pack activo</span>
        <button type="button" className="primary-button compact" onClick={props.onCompile}>
          <Icon name="plus" size={12} /> Crear pack
        </button>
      </footer>
    );
  }
  const pack = props.pack;
  const canSend = pack.status === 'compiled' || pack.status === 'valid';
  return (
    <footer className={`context-pack-bar state-${statusTone(pack.status)}`} aria-label="Pack activo">
      <div className="context-pack-bar-summary">
        <span className="context-pack-bar-name">
          <Icon name="pack" size={13} /> {pack.name}
        </span>
        <span className="context-pack-bar-stats">
          <span>{pack.nodeIds.length} nodos</span>
          <span>{pack.weightTokens.toLocaleString()}t</span>
          {pack.conflicts > 0 && <span className="is-warn">{pack.conflicts} conflicto{pack.conflicts > 1 ? 's' : ''}</span>}
          {pack.staleCount > 0 && <span className="is-warn">{pack.staleCount} desactualizado{pack.staleCount > 1 ? 's' : ''}</span>}
        </span>
        <span className={`status-badge state-${statusTone(pack.status)}`}>{statusLabel(pack.status)}</span>
        {pack.nodeIds.length === 0 && (
          <span className="context-pack-bar-empty-text">Pack vacío: añade piezas desde Banco</span>
        )}
      </div>
      <div className="context-pack-bar-actions">
        {canSend ? (
          <button type="button" className="primary-button compact" onClick={props.onSendToChat}>
            <Icon name="send" size={12} /> Enviar a Chat
          </button>
        ) : (
          <button type="button" className="primary-button compact" onClick={props.onCompile}>
            <Icon name="refresh" size={12} /> Compilar
          </button>
        )}
        {props.blockedReason && (
          <span className="context-pack-bar-blocked" title={props.blockedReason}>
            <Icon name="warning" size={11} /> {props.blockedReason}
          </span>
        )}
        <details className="workspace-actions-menu" open={actionsOpen} onToggle={(event) => setActionsOpen((event.currentTarget as HTMLDetailsElement).open)}>
          <summary aria-label="Más acciones del pack">
            <Icon name="more" size={12} />
          </summary>
          <div className="workspace-actions-menu-popover" role="menu">
            <button type="button" onClick={() => { props.onShowCompiled(); setActionsOpen(false); }} disabled={!pack.markdown}>
              <Icon name="file" size={11} /> Ver compilado
            </button>
            <button type="button" onClick={() => { props.onCopyPack(); setActionsOpen(false); }} disabled={!pack.markdown}>
              <Icon name="copy" size={11} /> Copiar
            </button>
            <button type="button" onClick={() => { props.onSendToPipeline(); setActionsOpen(false); }} disabled={!canSend}>
              <Icon name="pipeline" size={11} /> Crear tarea en Pipeline
            </button>
          </div>
        </details>
      </div>
    </footer>
  );
}
