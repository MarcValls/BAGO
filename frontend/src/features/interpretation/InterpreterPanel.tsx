import { useEffect, useState, useCallback } from 'react';
import type { BagoClient } from '@/api/client';
import type { InterpretationResult, InterpretationStage } from '@/contracts/backend';
import { Icon } from '@/shared/Icon';

interface Props {
  client: BagoClient;
  onClose: () => void;
}

type StageStatus = 'pending' | 'running' | 'succeeded' | 'failed';

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

function stageStatus(stage: InterpretationStage): StageStatus {
  if (stage.evidence && stage.evidence.length > 0) return 'succeeded';
  if (stage.durationMs !== undefined && stage.durationMs !== null) return 'succeeded';
  return 'pending';
}

function StageRow({ stage }: { stage: InterpretationStage }) {
  const [expanded, setExpanded] = useState(false);
  const status = stageStatus(stage);
  const statusIcon: Record<StageStatus, { name: Parameters<typeof Icon>[0]['name']; color: string }> = {
    pending: { name: 'dot', color: 'var(--color-text-muted)' },
    running: { name: 'refresh', color: 'var(--color-accent)' },
    succeeded: { name: 'check', color: 'var(--color-success)' },
    failed: { name: 'alert', color: 'var(--color-error)' },
  };
  const icon = statusIcon[status] || statusIcon.pending;

  return (
    <div className={`interpret-stage interpret-stage--${status}`}>
      <button
        type="button"
        className="interpret-stage-header"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
      >
        <Icon name={icon.name} size={14} style={{ color: icon.color }} />
        <span className="interpret-stage-label">{stage.label || STAGE_LABELS[stage.type] || stage.type}</span>
        <span className="interpret-stage-summary">{stage.summary}</span>
        <Icon name={expanded ? 'chevronUp' : 'chevronDown'} size={12} />
      </button>
      {expanded && (
        <div className="interpret-stage-body">
          {stage.evidence && stage.evidence.length > 0 && (
            <div className="interpret-stage-io">
              <span className="interpret-io-label">Evidencia</span>
              <pre className="interpret-io-text">{JSON.stringify(stage.evidence, null, 2)}</pre>
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
  const [history, setHistory] = useState<InterpretationResult[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    setError(null);
    try {
      const res = await client.listInterpretations();
      setHistory(res.interpretations || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingHistory(false);
    }
  }, [client]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const handleInterpret = useCallback(async () => {
    if (!input.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const res = await client.createInterpretation({ input: input.trim() });
      if (res.error) {
        setError(res.error);
      } else if (res.interpretation) {
        setResult(res.interpretation);
        setHistory((prev) => [res.interpretation!, ...prev]);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }, [client, input]);

  const handleCancel = useCallback(async () => {
    if (!result?.interpretationId) return;
    try {
      await client.cancelInterpretation(result.interpretationId);
      setResult((r) => (r ? { ...r, cancelledAt: new Date().toISOString() } : r));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [client, result]);

  const confidenceColor = (confidence: number | null | undefined) => {
    if (confidence === null || confidence === undefined) return 'var(--color-text-muted)';
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
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                handleInterpret();
              }
            }}
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
              <button type="button" className="btn btn--secondary" onClick={handleCancel}>
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

        <div className="interpretations-list">
          <div className="list-header">
            <span>Historial</span>
            <button type="button" className="btn-link" onClick={loadHistory} disabled={loadingHistory}>
              {loadingHistory ? 'Cargando...' : 'Actualizar'}
            </button>
          </div>
          {loadingHistory && history.length === 0 && <div className="panel-loading">Cargando...</div>}
          {!loadingHistory && history.length === 0 && <div className="panel-empty">Sin interpretaciones</div>}
          {history.map((interp) => (
            <button
              key={interp.interpretationId}
              type="button"
              className={`interpretation-item ${result?.interpretationId === interp.interpretationId ? 'is-selected' : ''}`}
              onClick={() => setResult(interp)}
            >
              <span className="interp-query">{interp.input}</span>
              <span className="interp-date">{new Date(interp.startedAt).toLocaleTimeString()}</span>
            </button>
          ))}
        </div>

        {result && (
          <div className="interpreter-result" role="region" aria-label="Resultado de interpretacion">
            <div className="interpreter-result-header">
              <span className="interpreter-result-title">Resultado</span>
              {result.confidence !== undefined && result.confidence !== null && (
                <span className="interpreter-confidence" style={{ color: confidenceColor(result.confidence) }}>
                  Confidence: {Math.round(result.confidence * 100)}%
                </span>
              )}
              <span className="interpreter-duration">{result.durationMs ?? 0}ms</span>
            </div>

            <div className="interpreter-stages">
              {result.stages.map((stage) => (
                <StageRow key={stage.id} stage={stage} />
              ))}
            </div>

            {result.finalOutput && (
              <div className="interpreter-final-output">
                <span className="interpreter-output-label">Salida final</span>
                <pre className="interpreter-output-text">{result.finalOutput}</pre>
              </div>
            )}

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
