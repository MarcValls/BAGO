import { useState } from 'react';
import type { ContextPatchRequest } from './contextTreeTypes';
import { Icon } from '@/shared/Icon';

interface Props {
  open: boolean;
  busy: boolean;
  proposal: ContextPatchRequest | null;
  sourceSummary: string;
  onClose: () => void;
  onCollect: (question: string) => Promise<void>;
  onAccept: () => Promise<void>;
  onReject: () => Promise<void>;
}

export function ContextCollectionDialog(props: Props) {
  const [question, setQuestion] = useState('');
  if (!props.open) return null;

  const hasProposal = Boolean(props.proposal);
  const operationCount = props.proposal?.patch.operations.length || 0;

  return (
    <div className="context-patch-preview-backdrop" role="presentation">
      <section className="context-patch-preview context-collection-dialog" role="dialog" aria-modal="true" aria-labelledby="context-collection-title">
        <header className="context-patch-preview-header">
          <div>
            <h3 id="context-collection-title"><Icon name="sparkle" size={14} /> Recopilar contexto</h3>
            <p className="context-collection-subtitle">El modelo prepara una propuesta. Nada se añade sin tu permiso.</p>
          </div>
          <button type="button" className="icon-button" onClick={props.onClose} aria-label="Cerrar" disabled={props.busy}>
            <Icon name="close" size={14} />
          </button>
        </header>

        {!hasProposal ? (
          <>
            <div className="context-collection-source">
              <strong>Origen</strong>
              <span>{props.sourceSummary}</span>
            </div>
            <label className="context-collection-question">
              <span>¿Qué debe aclarar o buscar el modelo?</span>
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Opcional. Ejemplo: identifica las pantallas de UI mencionadas y ordénalas como ramas."
                rows={4}
                disabled={props.busy}
              />
            </label>
            <footer className="context-patch-preview-actions">
              <button type="button" className="secondary-button" onClick={props.onClose} disabled={props.busy}>Cancelar</button>
              <button type="button" className="primary-button" onClick={() => void props.onCollect(question)} disabled={props.busy}>
                <Icon name="sparkle" size={12} /> {props.busy ? 'Analizando…' : 'Analizar chat'}
              </button>
            </footer>
          </>
        ) : (
          <>
            <div className="context-collection-review">
              <span className="context-collection-badge"><Icon name="alert" size={11} /> Propuesta pendiente</span>
              <h4>{props.proposal?.title}</h4>
              <p>{props.proposal?.reason}</p>
              <div className="context-collection-question-list">
                <strong>Preguntas / aclaraciones</strong>
                <p>{props.proposal?.metadata?.clarification || 'No quedan preguntas obligatorias.'}</p>
              </div>
              <div className="context-collection-operations">
                <strong>{operationCount} cambios preparados</strong>
                {props.proposal?.patch.operations.map((operation, index) => (
                  <div key={`${operation.op}-${index}`}>
                    <Icon name="chevron" size={10} /> {operation.op === 'create' ? `Crear rama: ${operation.title}` : operation.op}
                  </div>
                ))}
              </div>
            </div>
            <footer className="context-patch-preview-actions">
              <button type="button" className="secondary-button" onClick={() => void props.onReject()} disabled={props.busy}>Rechazar</button>
              <button type="button" className="primary-button" onClick={() => void props.onAccept()} disabled={props.busy}>
                <Icon name="check" size={12} /> {props.busy ? 'Guardando…' : 'Añadir con mi permiso'}
              </button>
            </footer>
          </>
        )}
      </section>
    </div>
  );
}
