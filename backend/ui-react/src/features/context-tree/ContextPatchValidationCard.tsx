// Tarjeta inline que aparece en el chat cuando el modelo emite un
// <<BAGO:CONTEXT_PATCH_REQUEST>>. Muestra título, motivo, riesgo y
// acciones. Crítico: NUNCA aplica el cambio sin validación del usuario.
import { useState } from 'react';
import type { ContextPatchRequest } from './contextTreeTypes';
import { Icon } from '@/shared/Icon';
import { summarizeText } from './utils';

interface Props {
  patch: ContextPatchRequest;
  status: 'pending' | 'accepted' | 'rejected' | 'edited' | 'failed' | 'reverted' | 'review_requested';
  errorMessage?: string;
  appliedAt?: string;
  receiptId?: string;
  onAccept: (patchId: string) => void;
  onReject: (patchId: string) => void;
  onEdit: (patchId: string) => void;
  onRevert: (patchId: string) => void;
  onOpenInTree: (patchId: string) => void;
  onReview: (patchId: string) => void;
}

function riskLabel(risk: ContextPatchRequest['riskLevel']): string {
  if (risk === 'critical') return 'CRIT';
  if (risk === 'high') return 'alto';
  if (risk === 'medium') return 'medio';
  return 'bajo';
}

function riskTone(risk: ContextPatchRequest['riskLevel']): string {
  if (risk === 'critical') return 'error';
  if (risk === 'high') return 'running';
  if (risk === 'medium') return 'running';
  return 'confirmed';
}

function summarizePatch(patch: ContextPatchRequest): string {
  return patch.patch.operations.map((op) => {
    switch (op.op) {
      case 'create': return `crear "${op.title}"`;
      case 'move': return `mover a ${op.newParentId}`;
      case 'update': return `editar ${Object.keys(op.patch).join(', ')}`;
      case 'exclude': return 'excluir del contexto';
      case 'restore': return 'restaurar al contexto';
      case 'canon': return op.value ? 'marcar como CANON' : 'quitar CANON';
      case 'link': return `vincular con ${op.targetId}`;
      case 'unlink': return `desvincular de ${op.targetId}`;
      case 'add_to_pack': return 'añadir al pack';
      case 'remove_from_pack': return 'quitar del pack';
      default: return op.op;
    }
  }).join(' · ');
}

export function ContextPatchValidationCard(props: Props) {
  const [expanded, setExpanded] = useState(false);
  const patch = props.patch;
  const summary = summarizePatch(patch);
  const tone = riskTone(patch.riskLevel);
  const isCritical = patch.riskLevel === 'critical';
  const isApplied = props.status === 'accepted' || props.status === 'edited';
  const isRejected = props.status === 'rejected';
  const isFailed = props.status === 'failed';
  const isReverted = props.status === 'reverted';

  return (
    <article className={`context-patch-card risk-${patch.riskLevel}`} data-status={props.status}>
      <header className="context-patch-card-header">
        <span className="context-patch-card-icon"><Icon name="proposed" size={14} /></span>
        <div>
          <strong>Cambio contextual sugerido</strong>
          <small>{patch.proposalType} · riesgo {riskLabel(patch.riskLevel)}</small>
        </div>
        <span className={`status-badge state-${tone}`}>Riesgo {riskLabel(patch.riskLevel)}</span>
      </header>
      <h4 className="context-patch-card-title">{patch.title}</h4>
      <p className="context-patch-card-summary">{summary}</p>
      {patch.reason && <p className="context-patch-card-reason">{summarizeText(patch.reason, 400)}</p>}

      {expanded && (
        <div className="context-patch-card-operations">
          <strong>Operaciones</strong>
          <ol>
            {patch.patch.operations.map((op, idx) => (
              <li key={idx}>
                <code>{op.op}</code>
                <span>{JSON.stringify(op, null, 0)}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <footer className="context-patch-card-actions">
        {props.status === 'pending' && !isCritical && (
          <>
            <button type="button" className="primary-button compact" onClick={() => props.onAccept(patch.id)}>
              <Icon name="check" size={12} /> Aceptar cambio
            </button>
            <button type="button" className="secondary-button compact" onClick={() => props.onEdit(patch.id)}>
              <Icon name="inspector" size={12} /> Editar
            </button>
            <button type="button" className="secondary-button compact" onClick={() => props.onReject(patch.id)}>
              <Icon name="close" size={12} /> Rechazar
            </button>
            <button type="button" className="text-button" onClick={() => props.onOpenInTree(patch.id)}>
              <Icon name="tree" size={12} /> Abrir en árbol
            </button>
            <button type="button" className="text-button" onClick={() => setExpanded((value) => !value)}>
              <Icon name={expanded ? 'close' : 'file'} size={12} /> {expanded ? 'Ocultar diff' : 'Ver diff'}
            </button>
          </>
        )}
        {props.status === 'pending' && isCritical && (
          <>
            <button type="button" className="primary-button compact" onClick={() => props.onReview(patch.id)}>
              <Icon name="lock" size={12} /> Solicitar revisión CRIT
            </button>
            <button type="button" className="secondary-button compact" onClick={() => props.onEdit(patch.id)}>
              <Icon name="inspector" size={12} /> Crear nueva versión
            </button>
            <button type="button" className="secondary-button compact" onClick={() => props.onReject(patch.id)}>
              <Icon name="close" size={12} /> Cancelar
            </button>
            <button type="button" className="text-button" onClick={() => props.onOpenInTree(patch.id)}>
              <Icon name="tree" size={12} /> Abrir en árbol
            </button>
            <button type="button" className="text-button" onClick={() => setExpanded((value) => !value)}>
              <Icon name={expanded ? 'close' : 'file'} size={12} /> {expanded ? 'Ocultar diff' : 'Ver diff'}
            </button>
          </>
        )}
        {isApplied && (
          <>
            <button type="button" className="text-button" onClick={() => props.onOpenInTree(patch.id)}>
              <Icon name="tree" size={12} /> Ver nodo
            </button>
            {props.receiptId && (
              <button type="button" className="text-button" onClick={() => navigator.clipboard?.writeText(props.receiptId || '')}>
                <Icon name="copy" size={12} /> Copiar receipt
              </button>
            )}
            <button type="button" className="text-button" onClick={() => props.onRevert(patch.id)}>
              <Icon name="retry" size={12} /> Revertir
            </button>
          </>
        )}
        {isRejected && <span className="context-patch-card-result">Rechazado por el usuario.</span>}
        {isReverted && <span className="context-patch-card-result">Cambio revertido.</span>}
        {isFailed && <span className="context-patch-card-result danger">{props.errorMessage || 'Falló la aplicación del patch.'}</span>}
      </footer>
    </article>
  );
}
