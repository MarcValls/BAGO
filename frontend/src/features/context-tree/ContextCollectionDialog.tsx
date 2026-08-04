import { useEffect, useState } from 'react';
import type { ContextPatchOp, ContextPatchRequest } from './contextTreeTypes';
import { Icon } from '@/shared/Icon';
import { useDialogAccessibility } from '@/lib/useDialogAccessibility';

interface Props {
  open: boolean;
  busy: boolean;
  proposal: ContextPatchRequest | null;
  sourceSummary: string;
  notice?: { tone: 'info' | 'warning' | 'error'; message: string } | null;
  onClose: () => void;
  onCollect: (question: string) => Promise<void>;
  onAccept: () => Promise<void>;
  onAcceptOperations?: (operations: ContextPatchOp[]) => Promise<void>;
  onReject: () => Promise<void>;
}

export function ContextCollectionDialog(props: Props) {
  const [question, setQuestion] = useState('');
  const [selectedOperations, setSelectedOperations] = useState<number[]>([]);
  const dialogRef = useDialogAccessibility<HTMLElement>(props.open, props.onClose, { closeDisabled: props.busy });
  useEffect(() => {
    setSelectedOperations(props.proposal?.patch.operations.map((_, index) => index) || []);
  }, [props.proposal?.id]);
  if (!props.open) return null;

  const hasProposal = Boolean(props.proposal);
  const operationCount = props.proposal?.patch.operations.length || 0;

  return (
    <div className="task-context-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !props.busy) props.onClose(); }}>
      <section ref={dialogRef} tabIndex={-1} className="task-context-dialog" role="dialog" aria-modal="true" aria-busy={props.busy} aria-labelledby="context-collection-title">
        <header className="task-context-dialog-header">
          <div>
            <span className="task-context-eyebrow">ASISTENTE DE CONTEXTO</span>
            <h3 id="context-collection-title"><Icon name="sparkle" size={14} /> Recopilar y ordenar</h3>
            <p>El modelo lee el chat, detecta la rama de trabajo y te pide aclaraciones si las necesita.</p>
          </div>
          <button type="button" className="task-context-close" onClick={props.onClose} aria-label="Cerrar recopilación" disabled={props.busy}>
            <Icon name="close" size={14} />
          </button>
        </header>

        {!hasProposal ? (
          <>
            <div className="task-context-dialog-source"><span>SE ANALIZARÁ</span><strong>{props.sourceSummary}</strong></div>
            {props.notice && <div className={`task-context-dialog-notice tone-${props.notice.tone}`} role="status">{props.notice.message}</div>}
            <label className="task-context-dialog-question">
              <span>Pregunta opcional para orientar la recopilación</span>
              <textarea
                data-autofocus
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ejemplo: separa las pantallas de UI y conserva las tareas abiertas como ramas."
                rows={4}
                disabled={props.busy}
              />
            </label>
            <footer className="task-context-dialog-actions">
              <button type="button" className="secondary-button" onClick={props.onClose} disabled={props.busy}>Cancelar</button>
              <button type="button" className="primary-button" onClick={() => void props.onCollect(question)} disabled={props.busy}>
                <Icon name="sparkle" size={12} /> {props.busy ? 'Analizando chat…' : 'Analizar conversación'}
              </button>
            </footer>
          </>
        ) : (
          <>
            <div className="task-context-dialog-review">
              <span className="task-context-review-badge"><Icon name="alert" size={11} /> Revisión necesaria</span>
              <h4>{props.proposal?.title}</h4>
              <p className="task-context-dialog-summary">{props.proposal?.reason}</p>
              <div className="task-context-dialog-block">
                <strong>Aclaración del modelo</strong>
                <p>{props.proposal?.metadata?.clarification || 'No quedan preguntas obligatorias.'}</p>
              </div>
              <div className="task-context-dialog-block">
                <strong>Fuente</strong>
                <p>{props.proposal?.metadata?.source === 'model_chat' ? 'Modelo + historial completo del chat' : 'Fallback local: historial del chat'}</p>
              </div>
              <div className="task-context-dialog-operations">
                <strong>{operationCount} elementos preparados para esta rama</strong>
                {props.proposal?.patch.operations.map((operation, index) => (
                  <label key={`${operation.op}-${index}`} className="task-context-operation-check">
                    <input type="checkbox" checked={selectedOperations.includes(index)} onChange={() => setSelectedOperations((current) => current.includes(index) ? current.filter((item) => item !== index) : [...current, index])} disabled={props.busy} />
                    <span><Icon name="check" size={10} /> {operation.op === 'create' ? operation.title : operation.op}</span>
                    <small>{operation.op === 'create' ? operation.summary || 'Sin resumen' : 'Operación contextual'}</small>
                  </label>
                ))}
              </div>
            </div>
            <footer className="task-context-dialog-actions">
              <button type="button" className="secondary-button" onClick={() => void props.onReject()} disabled={props.busy}>Descartar propuesta</button>
              <button type="button" className="primary-button" data-autofocus onClick={() => void (props.onAcceptOperations ? props.onAcceptOperations((props.proposal?.patch.operations || []).filter((_, index) => selectedOperations.includes(index))) : props.onAccept())} disabled={props.busy || selectedOperations.length === 0}>
                <Icon name="check" size={12} /> {props.busy ? 'Guardando…' : `Añadir seleccionados (${selectedOperations.length})`}
              </button>
            </footer>
          </>
        )}
      </section>
    </div>
  );
}
