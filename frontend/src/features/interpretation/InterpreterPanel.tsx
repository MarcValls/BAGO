import { useState, useCallback } from 'react';
import type { BagoClient } from '@/api/client';
import type { InterpretationResult, InterpretationStage } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';

interface Props {
  client: BagoClient;
  onClose: () => void;
}

type StageStatus = InterpretationStage['status'];

const STAGE_LABELS: Record<string, string> = {
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
  const statusIcon: Record<StageStatus, { name: string; color: string }> = {
    pending: { name: 'dot', color: 'var(--color-text-muted)' },
    running: { name: 'refresh', color: 'var(--color-accent)' },
    succeeded: { name: 'check', color: 'var(--color-success)' },
    failed: { name: 'alert', color: 'var(--color-error)' },
  };
  const icon = statusIcon[stage.status] || statusIcon.pending;

  return (
    <div className={`interpret-stage interpret-stage--${stage.status}`}>
      <button
        type="button"
        className="interpret-stage-header"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <Icon name={icon.name as Parameters<typeof Icon>[0]['name']} size={14} style={{ color: icon.color }} />
        <span className="interpret-stage-label">{stage.label || STAGE_LABELS[stage.stage] || stage.stage}</span>
        <Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={12} />
      </button>
      {expanded && (
        <div className="interpret-stage-body">
          {stage.input && (
            <div className="interpret-stage-io">
              <span className="interpret-io-label">Input</span>
              <pre className="interpret-io-text">{stage.input}</pre>
            </div>
          )}
          {stage.output && (
            <div className="interpret-stage-io">
              <span className="interpret-io-label">Output</span>
              <pre className="interpret-io-text">{stage.output}</pre>
            </div>
          )}
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
      const res = await client.createInterpretation({ input: input.trim() });
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }, [client, input]);

  const handleCancel = useCallback(async () => {
    if (!result?.id) return;
    try {
      await client.cancelInterpretation(result.id);
      setResult((r) => r ? { ...r, cancelledAt: new Date().toISOString() } : r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [client, result]);

  const confidenceColor = (confidence: number | null) => {
    if (confidence === null) return 'var(--color-text-muted)';
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
              {result.confidence !== null && (
                <span
                  className="interpreter-confidence"
                  style={{ color: confidenceColor(result.confidence) }}
                >
                  Confidence: {Math.round((result.confidence || 0) * 100)}%
                </span>
              )}
              <span className="interpreter-duration">{result.durationMs}ms</span>
            </div>

            <div className="interpreter-stages">
              {result.stages.map((stage) => (
                <StageRow key={stage.stage} stage={stage} />
              ))}
            </div>

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
