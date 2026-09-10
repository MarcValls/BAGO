import { useState, useCallback } from 'react';
import type { BagoClient } from '@/api/client';
import type { InterpretationResult, InterpretationStage, InterpretationStageType } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { friendlyErrorMessage } from '@/shared/friendly-error';

interface Props {
  client: BagoClient;
  onClose: () => void;
}

type StageStatus = 'pending' | 'running' | 'succeeded' | 'failed';

const STAGE_TYPE_LABELS: Record<InterpretationStageType, string> = {
  input: 'Entrada',
  normalization: 'Normalización',
  intent: 'Intención',
  context: 'Contexto',
  constraints: 'Restricciones',
  routing: 'Enrutamiento',
  decision: 'Decisión',
  output: 'Salida',
};

function StageRow({ stage }: { stage: InterpretationStage }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="interpret-stage">
      <button
        type="button"
        className="interpret-stage-header"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <span className="interpret-stage-label">{stage.label || STAGE_TYPE_LABELS[stage.type]}</span>
        <Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={12} />
      </button>
      {expanded && stage.summary && (
        <div className="interpret-stage-body">
          <div className="interpret-stage-io">
            <span className="interpret-io-label">Resumen</span>
            <pre className="interpret-io-text">{stage.summary}</pre>
          </div>
          {stage.metadata && Object.keys(stage.metadata).length > 0 && (
            <div className="interpret-stage-io">
              <span className="interpret-io-label">Metadata</span>
              <pre className="interpret-io-text">{JSON.stringify(stage.metadata, null, 2)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function InterpreterPanel({ client, onClose }: Props) {
  const [input, setInput] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<InterpretationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleInterpret = useCallback(async () => {
    if (!input.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const text = input.trim();
      const res = await client.createInterpretation({ input: text, question: text });
      setResult(res);
    } catch (e: unknown) {
      setError(friendlyErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }, [client, input]);

  // El backend no expone cancelacion de interpretaciones: se marca en cliente
  // para no dejar el boton en un error permanente.
  const handleCancel = useCallback(() => {
    if (!result?.interpretationId) return;
    setSubmitting(false);
    setResult((r) => r ? { ...r, cancelledAt: new Date().toISOString() } : r);
  }, [result]);

  const confidenceColor = (confidence: number | undefined | null) => {
    if (confidence == null) return 'var(--color-text-muted)';
    if (confidence >= 0.8) return 'var(--color-success)';
    if (confidence >= 0.5) return 'var(--color-warning)';
    return 'var(--color-error)';
  };

  return (
    <div className="interpreter-panel" role="region" aria-label="Interprete">
      <div className="panel-header">
        <h3>Interprete</h3>
        <button type="button" className="panel-close-btn" onClick={onClose} aria-label="Cerrar">
          <Icon name="close" size={16} />
        </button>
      </div>

      <div className="interpreter-body">
        {/* Input area */}
        <div className="interpreter-input-area">
          <label htmlFor="interpret-input" className="interpreter-input-label">
            Texto a interpretar
          </label>
          <textarea
            id="interpret-input"
            className="interpreter-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribe el texto que quieres que BAGO interprete..."
            rows={4}
            disabled={submitting}
          />
          <div className="interpreter-input-actions">
            <button
              type="button"
              className="btn btn--primary"
              onClick={handleInterpret}
              disabled={submitting || !input.trim()}
            >
              <Icon name="interpret" size={14} />
              {submitting ? 'Interpretando...' : 'Interpretar'}
            </button>
            {result && !result.cancelledAt && (
              <button
                type="button"
                className="btn btn--secondary"
                onClick={handleCancel}
              >
                <Icon name="stop" size={14} />
                Cancelar
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="form-error" role="alert">
            <Icon name="alert" size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="interpreter-result" role="region" aria-label="Resultado de interpretacion">
            <div className="interpreter-result-header">
              <span className="interpreter-result-title">Resultado</span>
              {result.confidence != null && (
                <span
                  className="interpreter-confidence"
                  style={{ color: confidenceColor(result.confidence) }}
                >
                  Confidence: {Math.round(result.confidence * 100)}%
                </span>
              )}
              <span className="interpreter-duration">{result.durationMs}ms</span>
            </div>

            <div className="interpreter-stages">
              {result.stages.map((stage, idx) => (
                <StageRow key={`${stage.type}-${idx}`} stage={stage} />
              ))}
            </div>

            {result.operationalSpec && (
              <div className="interpreter-operational-spec">
                <span className="interpreter-output-label">Especificación operacional</span>
                <div className="interpreter-spec-grid">
                  <div><span>Intención</span><strong>{result.operationalSpec.intent}</strong></div>
                  <div><span>Operación</span><strong>{result.operationalSpec.operation}</strong></div>
                  <div><span>Producto</span><strong>{result.operationalSpec.product || 'No especificado'}</strong></div>
                  <div><span>Estado</span><strong>{result.operationalSpec.lifecycle_state}</strong></div>
                </div>
                {(result.operationalSpec.constraints.length > 0 || result.operationalSpec.acceptance.length > 0) && (
                  <div className="interpreter-spec-lists">
                    {result.operationalSpec.constraints.length > 0 && (
                      <div><span>Restricciones</span><ul>{result.operationalSpec.constraints.map((item) => <li key={item}>{item}</li>)}</ul></div>
                    )}
                    {result.operationalSpec.acceptance.length > 0 && (
                      <div><span>Aceptación</span><ul>{result.operationalSpec.acceptance.map((item) => <li key={item}>{item}</li>)}</ul></div>
                    )}
                  </div>
                )}
              </div>
            )}

            <div className="interpreter-final-output">
              <span className="interpreter-output-label">Salida final</span>
              <pre className="interpreter-output-text">{result.finalOutput}</pre>
            </div>

            {result.error && (
              <div className="form-error" role="alert">
                <Icon name="alert" size={14} />
                <span>{result.error}</span>
              </div>
            )}

            {result.cancelledAt && (
              <div className="form-warning" role="status">
                <Icon name="warning" size={14} />
                <span>Interpretación cancelada</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
