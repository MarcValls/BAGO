// Bandeja de actividad contextual. Muestra los patches propuestos por
// el chat (pendientes, aplicados, rechazados, fallidos, revertidos)
// y los receipts recientes. Cada item es accionable.
import { useEffect, useMemo, useState } from 'react';
import type { ContextPatchRequest, ContextReceipt } from './contextTreeTypes';
import { Icon } from '@/shared/Icon';
import { formatRelativeTime, summarizeText } from './utils';

interface Props {
  proposals: ContextPatchRequest[];
  receipts: ContextReceipt[];
  defaultOpen?: boolean;
  height?: number;
  onAcceptPatch: (patchId: string) => void;
  onRejectPatch: (patchId: string) => void;
  onRevertPatch: (patchId: string) => void;
  onEditPatch: (patchId: string) => void;
  onOpenRelated: (nodeId: string) => void;
  onClear: () => void;
}

type Tab = 'pending' | 'applied' | 'rejected' | 'failed' | 'reverted' | 'receipts';

function statusTone(status: ContextPatchRequest['status']): string {
  switch (status) {
    case 'pending': return 'running';
    case 'accepted':
    case 'edited': return 'confirmed';
    case 'rejected': return 'blocked';
    case 'failed': return 'error';
    case 'reverted': return 'unknown';
    case 'review_requested': return 'running';
    default: return 'unknown';
  }
}

function statusLabel(status: ContextPatchRequest['status']): string {
  switch (status) {
    case 'pending': return 'Pendiente';
    case 'accepted': return 'Aplicado';
    case 'edited': return 'Aplicado (editado)';
    case 'rejected': return 'Rechazado';
    case 'failed': return 'Fallido';
    case 'reverted': return 'Revertido';
    case 'review_requested': return 'Revisión';
    default: return status;
  }
}

function riskLabel(risk: ContextPatchRequest['riskLevel']): string {
  switch (risk) {
    case 'low': return 'Riesgo bajo';
    case 'medium': return 'Riesgo medio';
    case 'high': return 'Riesgo alto';
    case 'critical': return 'CRIT';
    default: return risk;
  }
}

function riskTone(risk: ContextPatchRequest['riskLevel']): string {
  if (risk === 'critical') return 'error';
  if (risk === 'high') return 'running';
  if (risk === 'medium') return 'running';
  return 'confirmed';
}

export function ContextActivityTray(props: Props) {
  const [open, setOpen] = useState(Boolean(props.defaultOpen));
  const [tab, setTab] = useState<Tab>('pending');

  const groups = useMemo(() => {
    return {
      pending: props.proposals.filter((p) => p.status === 'pending'),
      applied: props.proposals.filter((p) => p.status === 'accepted' || p.status === 'edited'),
      rejected: props.proposals.filter((p) => p.status === 'rejected'),
      failed: props.proposals.filter((p) => p.status === 'failed'),
      reverted: props.proposals.filter((p) => p.status === 'reverted'),
      receipts: props.receipts
    };
  }, [props.proposals, props.receipts]);

  const totalActivity =
    groups.pending.length + groups.applied.length + groups.rejected.length +
    groups.failed.length + groups.reverted.length;

  useEffect(() => {
    if (props.defaultOpen) {
      setOpen(true);
      return;
    }
    if (totalActivity === 0 && groups.receipts.length === 0) {
      setOpen(false);
    }
  }, [props.defaultOpen, totalActivity, groups.receipts.length]);

  return (
    <section className={`context-activity-tray ${open ? 'is-open' : 'is-collapsed'} ${props.height ? 'is-resizable' : ''}`} style={props.height ? { flex: `0 0 ${props.height}px`, minHeight: 0 } : undefined} aria-label="Actividad contextual">
      <header className="context-activity-tray-header">
        <button
          type="button"
          className="context-activity-tray-toggle"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
        >
          <Icon name="tray" size={13} />
          <strong>Actividad contextual</strong>
          {groups.pending.length > 0 && <span className="context-activity-badge">{groups.pending.length} pendientes</span>}
          {totalActivity === 0 && <small>sin actividad</small>}
        </button>
        {open && (
          <nav className="context-activity-tray-tabs" role="tablist">
            <button type="button" role="tab" aria-selected={tab === 'pending'} className={tab === 'pending' ? 'is-active' : ''} onClick={() => setTab('pending')}>
              Pendientes <small>{groups.pending.length}</small>
            </button>
            <button type="button" role="tab" aria-selected={tab === 'applied'} className={tab === 'applied' ? 'is-active' : ''} onClick={() => setTab('applied')}>
              Aplicados <small>{groups.applied.length}</small>
            </button>
            <button type="button" role="tab" aria-selected={tab === 'rejected'} className={tab === 'rejected' ? 'is-active' : ''} onClick={() => setTab('rejected')}>
              Rechazados <small>{groups.rejected.length}</small>
            </button>
            <button type="button" role="tab" aria-selected={tab === 'failed'} className={tab === 'failed' ? 'is-active' : ''} onClick={() => setTab('failed')}>
              Fallidos <small>{groups.failed.length}</small>
            </button>
            <button type="button" role="tab" aria-selected={tab === 'reverted'} className={tab === 'reverted' ? 'is-active' : ''} onClick={() => setTab('reverted')}>
              Revertidos <small>{groups.reverted.length}</small>
            </button>
            <button type="button" role="tab" aria-selected={tab === 'receipts'} className={tab === 'receipts' ? 'is-active' : ''} onClick={() => setTab('receipts')}>
              Receipts <small>{groups.receipts.length}</small>
            </button>
            <button type="button" className="text-button" onClick={props.onClear}>
              <Icon name="close" size={11} /> Limpiar bandeja
            </button>
          </nav>
        )}
      </header>
      {open && (
        <div className="context-activity-tray-body">
          {tab === 'receipts' ? (
            <ul className="context-activity-list">
              {groups.receipts.length === 0 && <li className="context-activity-empty">Sin receipts todavía.</li>}
              {groups.receipts.map((receipt) => (
                <li key={receipt.id} className="context-activity-item">
                  <span className="context-activity-icon"><Icon name="evidence" size={11} /></span>
                  <div>
                    <strong>{receipt.summary}</strong>
                    <small>{receipt.kind} · {formatRelativeTime(receipt.createdAt)}</small>
                  </div>
                  {receipt.riskLevel && <span className={`status-badge state-${riskTone(receipt.riskLevel)}`}>{riskLabel(receipt.riskLevel)}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <ul className="context-activity-list">
              {groups[tab].length === 0 && <li className="context-activity-empty">Sin cambios en esta categoría.</li>}
              {groups[tab].map((patch) => (
                <li key={patch.id} className={`context-activity-item status-${patch.status}`}>
                  <span className="context-activity-icon">
                    <Icon name={patch.status === 'pending' ? 'proposed' : patch.status === 'rejected' ? 'close' : patch.status === 'failed' ? 'warning' : 'verified'} size={11} />
                  </span>
                  <div>
                    <strong>{patch.title}</strong>
                    <small>{statusLabel(patch.status)} · {formatRelativeTime(patch.appliedAt || patch.rejectedAt || patch.createdAt)} · {riskLabel(patch.riskLevel)}</small>
                    {patch.errorMessage && <p className="context-activity-error">{patch.errorMessage}</p>}
                    {patch.reason && <p className="context-activity-reason">{summarizeText(patch.reason, 200)}</p>}
                  </div>
                  <div className="context-activity-actions">
                    {patch.status === 'pending' && (
                      <>
                        <button type="button" className="primary-button compact" onClick={() => props.onAcceptPatch(patch.id)}>
                          <Icon name="check" size={11} /> Aceptar
                        </button>
                        <button type="button" className="secondary-button compact" onClick={() => props.onEditPatch(patch.id)}>
                          <Icon name="inspector" size={11} /> Editar
                        </button>
                        <button type="button" className="secondary-button compact" onClick={() => props.onRejectPatch(patch.id)}>
                          <Icon name="close" size={11} /> Rechazar
                        </button>
                      </>
                    )}
                    {patch.status === 'accepted' || patch.status === 'edited' ? (
                      <>
                        {patch.targetNodeId && (
                          <button type="button" className="text-button" onClick={() => props.onOpenRelated(patch.targetNodeId as string)}>
                            <Icon name="node" size={11} /> Ver nodo
                          </button>
                        )}
                        {patch.receiptId && (
                          <button type="button" className="text-button" onClick={() => navigator.clipboard?.writeText(patch.receiptId || '')}>
                            <Icon name="copy" size={11} /> Copiar receipt
                          </button>
                        )}
                        <button type="button" className="text-button" onClick={() => props.onRevertPatch(patch.id)}>
                          <Icon name="retry" size={11} /> Revertir
                        </button>
                      </>
                    ) : null}
                    {patch.status === 'failed' && (
                      <span className="context-activity-error-tag">
                        <Icon name="warning" size={11} /> Reintentar requiere abrir el patch en edición.
                      </span>
                    )}
                    {patch.status === 'rejected' && (
                      <span className="context-activity-hint">Sin árbol modificado.</span>
                    )}
                    {patch.status === 'reverted' && (
                      <span className="context-activity-hint">Reversión aplicada.</span>
                    )}
                  </div>
                  <span className={`status-badge state-${statusTone(patch.status)}`}>{statusLabel(patch.status)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}
