import { useEffect, useState } from 'react';
import { Icon } from '@/shared/Icon';

interface InterpretationStage {
  stage: string;
  status: 'pending' | 'active' | 'done' | 'error';
  evidence?: Record<string, unknown>;
  durationMs?: number;
}

interface Interpretation {
  id: string;
  query: string;
  stages: InterpretationStage[];
  result?: string;
  error?: string;
  createdAt: string;
}

interface InterpreterPanelProps {
  client?: ReturnType<typeof import('@/api/client').createBagoClient>;
  onClose?: () => void;
}

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

const STAGE_ORDER = ['input', 'normalization', 'intent', 'context', 'constraints', 'routing', 'decision', 'output'];

export function InterpreterPanel({ client, onClose }: InterpreterPanelProps) {
  const [interpretations, setInterpretations] = useState<Interpretation[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Interpretation | null>(null);
  const [query, setQuery] = useState('');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadHistory() {
    if (!client) return;
    setLoading(true);
    try {
      const res = await client.listInterpretations(20);
      if (res.interpretations) setInterpretations(res.interpretations as unknown as Interpretation[]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadHistory(); }, [client]);

  async function handleInterpret() {
    if (!client || !query.trim()) return;
    setRunning(true);
    setError(null);
    try {
      const res = await client.createInterpretation({ query: query.trim() });
      if (res.interpretation) {
        setInterpretations([res.interpretation as unknown as Interpretation, ...interpretations]);
        setSelected(res.interpretation as unknown as Interpretation);
      } else if (res.error) {
        setError(res.error);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  function renderStageIcon(status: InterpretationStage['status']) {
    if (status === 'done') return <Icon name="check-circle" className="stage-icon done" />;
    if (status === 'error') return <Icon name="alert-circle" className="stage-icon error" />;
    if (status === 'active') return <Icon name="loader" className="stage-icon active" />;
    return <Icon name="circle" className="stage-icon pending" />;
  }

  return (
    <div className="panel interpreter-panel">
      <div className="panel-header">
        <span className="panel-title">Intérprete</span>
        <button type="button" className="btn-icon" onClick={onClose} title="Cerrar"><Icon name="x" /></button>
      </div>

      <div className="panel-body">
        <div className="interpreter-input">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Escribe una consulta para interpretar..."
            rows={3}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleInterpret();
            }}
          />
          <button type="button" className="btn-primary" onClick={handleInterpret} disabled={running || !query.trim()}>
            {running ? 'Interpretando...' : 'Interpretar'}
          </button>
        </div>

        {error && <div className="form-error">{error}</div>}

        <div className="interpretations-list">
          <div className="list-header">
            <span>Historial</span>
            <button type="button" className="btn-link" onClick={loadHistory} disabled={loading}>Actualizar</button>
          </div>
          {loading && <div className="panel-loading">Cargando...</div>}
          {!loading && interpretations.length === 0 && <div className="panel-empty">Sin interpretaciones</div>}
          {interpretations.map((interp) => (
            <button
              key={interp.id}
              type="button"
              className={`interpretation-item ${selected?.id === interp.id ? 'is-selected' : ''}`}
              onClick={() => setSelected(interp)}
            >
              <span className="interp-query">{interp.query}</span>
              <span className="interp-date">{new Date(interp.createdAt).toLocaleTimeString()}</span>
            </button>
          ))}
        </div>

        {selected && (
          <div className="interpretation-detail">
            <h4>Detalle: {selected.query}</h4>
            <div className="stages-timeline">
              {STAGE_ORDER.map((stageKey) => {
                const stage = selected.stages.find((s) => s.stage === stageKey);
                const label = STAGE_LABELS[stageKey] || stageKey;
                return (
                  <div key={stageKey} className={`stage-row stage-${stage?.status || 'pending'}`}>
                    {renderStageIcon(stage?.status || 'pending')}
                    <span className="stage-label">{label}</span>
                    {stage?.durationMs !== undefined && (
                      <span className="stage-duration">{(stage.durationMs / 1000).toFixed(2)}s</span>
                    )}
                  </div>
                );
              })}
            </div>
            {selected.result && (
              <div className="interpretation-result">
                <h5>Resultado</h5>
                <pre>{selected.result}</pre>
              </div>
            )}
            {selected.error && (
              <div className="interpretation-error">
                <h5>Error</h5>
                <pre>{selected.error}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
