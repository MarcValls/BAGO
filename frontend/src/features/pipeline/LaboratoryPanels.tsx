import { useCallback, useEffect, useMemo, useState } from 'react';
import type { BagoClient } from '@/api/client';
import { Icon } from '@/shared/Icon';
import { friendlyErrorMessage } from '@/shared/friendly-error';

type RecordValue = Record<string, unknown>;
type EventFilter = 'all' | 'success' | 'failure';

function record(value: unknown): RecordValue {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : {};
}

function records(value: unknown): RecordValue[] {
  return Array.isArray(value) ? value.filter((item): item is RecordValue => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : [];
}

function errorMessage(cause: unknown): string {
  return friendlyErrorMessage(cause);
}

function formatTime(value: unknown): string {
  const numeric = Number(value || 0);
  if (!numeric) return 'Sin hora';
  return new Date(numeric * 1000).toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function actionLabel(value: unknown): string {
  const labels: Record<string, string> = { chat: 'Conversación', command: 'Comando', work: 'Trabajo', review: 'Revisión', execute: 'Ejecución', project: 'Proyecto' };
  const key = String(value || 'evento');
  return labels[key] || key;
}

function recommendationLabel(event: RecordValue): string {
  const recommendation = record(event.recommended);
  if (recommendation.kind === 'provider-model') return `${String(recommendation.provider || 'Proveedor')} · ${String(recommendation.model || 'modelo')}`;
  if (recommendation.command) return String(recommendation.command);
  return String(recommendation.reason || recommendation.kind || 'Solo observación');
}

function actualLabel(event: RecordValue): string {
  const actual = record(event.actual);
  return [actual.provider, actual.model].filter(Boolean).map(String).join(' · ') || String(actual.command || 'Sin cambio');
}

export function SimulationLaboratory({ client }: { client: BagoClient }) {
  const [status, setStatus] = useState<RecordValue | null>(null);
  const [events, setEvents] = useState<RecordValue[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [filter, setFilter] = useState<EventFilter>('all');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setError('');
    try {
      const [nextStatus, nextEvents] = await Promise.all([client.getSimulationStatus(), client.getSimulationEvents()]);
      const list = records(nextEvents.events).reverse();
      setStatus(nextStatus);
      setEvents(list);
      setSelectedId((current) => current && list.some((item) => String(item.id) === current) ? current : String(list[0]?.id || ''));
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }, [client]);

  useEffect(() => { void load(); }, [load]);

  const enabled = Boolean(status?.enabled) && status?.mode !== 'off';
  const visibleEvents = useMemo(() => events.filter((event) => filter === 'all' || (filter === 'success' ? event.result_ok !== false : event.result_ok === false)), [events, filter]);
  const selected = visibleEvents.find((event) => String(event.id) === selectedId) || visibleEvents[0] || null;
  const successful = events.filter((event) => event.result_ok !== false).length;
  const averageLatency = events.length ? Math.round(events.reduce((total, event) => total + Number(event.elapsed_ms || 0), 0) / events.length) : 0;

  const configure = async (nextEnabled: boolean) => {
    setBusy('configure'); setError(''); setNotice('');
    try {
      const next = await client.setSimulationConfig({ enabled: nextEnabled, mode: nextEnabled ? 'shadow' : 'off' });
      setStatus(next);
      setNotice(nextEnabled ? 'Observación activada. BAGO registrará recomendaciones sin intervenir.' : 'Observación pausada. No se registrarán eventos nuevos.');
      await load();
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(''); }
  };

  return <section className="laboratory-panel simulation-laboratory" role="tabpanel">
    <header className="laboratory-header">
      <div><h3>Simulación</h3><p>Observa cómo habría actuado BAGO y compáralo con lo que ocurrió realmente.</p></div>
      <button className={`laboratory-switch ${enabled ? 'is-active' : ''}`} type="button" role="switch" aria-checked={enabled} disabled={Boolean(busy)} onClick={() => void configure(!enabled)}><span /><strong>{busy ? 'Guardando…' : enabled ? 'Observando' : 'Pausada'}</strong></button>
    </header>

    <div className="laboratory-safety"><Icon name="check" size={15} /><span><strong>Sin autoridad de ejecución</strong><small>La simulación registra recomendaciones; nunca cambia proveedores, modelos ni comandos.</small></span></div>
    {(error || notice) && <div className={`laboratory-message ${error ? 'is-error' : ''}`} role={error ? 'alert' : 'status'}>{error || notice}</div>}
    {!status ? <div className="system-tab-loading">Cargando simulación…</div> : <>
      <div className="laboratory-metrics">
        <article><span>Eventos observados</span><strong>{Number(status.events_logged || events.length).toLocaleString()}</strong><small>{events.length} recientes en pantalla</small></article>
        <article><span>Resultados correctos</span><strong>{events.length ? `${Math.round(successful * 100 / events.length)}%` : '—'}</strong><small>{successful} de {events.length}</small></article>
        <article><span>Latencia media</span><strong>{events.length ? `${averageLatency} ms` : '—'}</strong><small>Últimos eventos</small></article>
      </div>

      <div className="simulation-workspace">
        <section className="simulation-events">
          <header><div><strong>Actividad reciente</strong><small>Recomendación frente a resultado real</small></div><button className="icon-button" type="button" aria-label="Actualizar eventos" disabled={Boolean(busy)} onClick={() => void load()}><Icon name="refresh" size={13} /></button></header>
          <div className="laboratory-filter" role="group" aria-label="Filtrar eventos">{([['all', 'Todos'], ['success', 'Correctos'], ['failure', 'Fallidos']] as const).map(([id, label]) => <button key={id} type="button" className={filter === id ? 'is-active' : ''} onClick={() => setFilter(id)}>{label}</button>)}</div>
          <div className="simulation-event-list">
            {visibleEvents.length === 0 ? <div className="laboratory-empty"><Icon name="history" size={20} /><strong>Sin eventos para este filtro</strong><span>{enabled ? 'Usa BAGO normalmente y las observaciones aparecerán aquí.' : 'Activa la observación para registrar nuevos eventos.'}</span></div> : visibleEvents.map((event) => <button key={String(event.id)} type="button" className={String(event.id) === String(selected?.id) ? 'is-selected' : ''} onClick={() => setSelectedId(String(event.id))}><span className={`laboratory-event-dot ${event.result_ok === false ? 'is-error' : ''}`} /><span><strong>{actionLabel(event.action_kind)}</strong><small>{formatTime(event.timestamp)} · {Math.round(Number(event.elapsed_ms || 0))} ms</small></span><Icon name="chevron" size={12} /></button>)}
          </div>
        </section>

        <section className="simulation-comparison">
          {selected ? <>
            <header><div><strong>{actionLabel(selected.action_kind)}</strong><small>Evento #{String(selected.id)}</small></div><span className={`provider-status ${selected.result_ok === false ? 'is-off' : 'is-on'}`}>{selected.result_ok === false ? 'fallido' : 'correcto'}</span></header>
            <div className="simulation-compare-row"><span>Recomendación</span><strong>{recommendationLabel(selected)}</strong><small>{String(record(selected.recommended).reason || 'Sin explicación adicional')}</small></div>
            <div className="simulation-compare-row"><span>Resultado real</span><strong>{actualLabel(selected)}</strong><small>{Math.round(Number(selected.elapsed_ms || 0))} ms · recompensa {Number(selected.reward || 0).toFixed(2)}</small></div>
            <details><summary>Detalle técnico</summary><pre className="system-json">{JSON.stringify(selected, null, 2)}</pre></details>
          </> : <div className="laboratory-empty"><Icon name="trace" size={22} /><strong>Selecciona un evento</strong><span>Aquí verás la comparación sin tener que leer el JSON completo.</span></div>}
        </section>
      </div>
    </>}
  </section>;
}

export function RlTrainingLaboratory({ client }: { client: BagoClient }) {
  const [status, setStatus] = useState<RecordValue | null>(null);
  const [result, setResult] = useState<RecordValue | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setError('');
    try { setStatus(await client.getRlStatus()); }
    catch (cause) { setError(errorMessage(cause)); }
  }, [client]);
  useEffect(() => { void load(); }, [load]);

  const training = record(status?.training);
  const enabled = Boolean(status?.enabled) && status?.mode !== 'off';
  const policyExists = Boolean(training.policy_exists);
  const samples = Number(training.samples || 0);
  const numpyAvailable = training.numpy_available !== false;
  const actions = Array.isArray(training.actions) ? training.actions.map(String) : ['chat', 'review', 'execute', 'work'];

  const run = async (action: 'shadow' | 'train' | 'eval' | 'refresh') => {
    setBusy(action); setError(''); setNotice('');
    try {
      const response = action === 'shadow'
        ? await client.setRlShadow({ enabled: !enabled })
        : action === 'train'
          ? await client.trainRlBc()
          : action === 'eval'
            ? await client.evalRlPolicy()
            : await client.getRlStatus();
      if (action === 'train') {
        setNotice(response.status === 'no_samples' ? 'No hay muestras suficientes. Activa observación o usa BAGO para generar historial.' : `Entrenamiento completado con ${String(response.samples || 0)} muestras.`);
      } else if (action === 'eval') {
        setNotice(response.status === 'no_policy' ? 'Todavía no hay una política entrenada.' : 'Evaluación completada sin ejecutar ninguna acción.');
      } else if (action === 'shadow') {
        setNotice(enabled ? 'Recopilación de observaciones pausada.' : 'Recopilación de observaciones activada.');
      }
      setResult(action === 'refresh' || action === 'shadow' ? null : response);
      await load();
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(''); }
  };

  const resultStatus = String(result?.status || '');
  const prediction = Number(result?.prediction_for_zero_vector);
  const predictionLabel = Number.isInteger(prediction) && actions[prediction] ? actionLabel(actions[prediction]) : 'Sin recomendación';

  return <section className="laboratory-panel rl-training-laboratory" role="tabpanel">
    <header className="laboratory-header"><div><h3>Entrenamiento RL</h3><p>Aprende del historial para recomendar la intención adecuada, siempre en modo observador.</p></div><button className="secondary-button compact" type="button" disabled={Boolean(busy)} onClick={() => void run('refresh')}><Icon name="refresh" size={13} /> Actualizar</button></header>
    <div className="laboratory-safety"><Icon name="check" size={15} /><span><strong>Aprende, no actúa</strong><small>La política puede recomendar Conversación, Revisión, Ejecución o Trabajo. La decisión final permanece en BAGO.</small></span></div>
    {(error || notice) && <div className={`laboratory-message ${error ? 'is-error' : ''}`} role={error ? 'alert' : 'status'}>{error || notice}</div>}
    {!status ? <div className="system-tab-loading">Cargando entrenamiento RL…</div> : <>
      <div className="rl-training-layout">
        <section className="rl-training-flow">
          <article className={`rl-training-step ${enabled ? 'is-ready' : ''}`}><span className="rl-step-index">1</span><div><strong>Recopilar observaciones</strong><p>Registra casos reales y resultados en segundo plano.</p><small>{enabled ? `${Number(status.events_logged || 0)} eventos observados` : 'Recopilación pausada'}</small></div><button className="secondary-button compact" type="button" disabled={Boolean(busy)} onClick={() => void run('shadow')}>{busy === 'shadow' ? 'Guardando…' : enabled ? 'Pausar' : 'Activar'}</button></article>
          <article className={`rl-training-step ${samples > 0 ? 'is-ready' : ''}`}><span className="rl-step-index">2</span><div><strong>Entrenar política</strong><p>Ajusta una política local con las muestras disponibles.</p><small>{samples} muestras · {numpyAvailable ? 'motor disponible' : 'falta NumPy'}</small></div><button className="primary-button compact" type="button" disabled={Boolean(busy) || !numpyAvailable} onClick={() => void run('train')}>{busy === 'train' ? 'Entrenando…' : policyExists ? 'Volver a entrenar' : 'Entrenar'}</button></article>
          <article className={`rl-training-step ${policyExists ? 'is-ready' : ''}`}><span className="rl-step-index">3</span><div><strong>Evaluar política</strong><p>Comprueba que la política se carga y produce una recomendación.</p><small>{policyExists ? 'Política disponible' : 'Entrena primero'}</small></div><button className="secondary-button compact" type="button" disabled={Boolean(busy) || !policyExists} onClick={() => void run('eval')}>{busy === 'eval' ? 'Evaluando…' : 'Evaluar'}</button></article>
        </section>

        <aside className="rl-training-result">
          <header><strong>Último resultado</strong><span className="provider-status is-on">observer-only</span></header>
          {!result ? <div className="laboratory-empty"><Icon name="live" size={22} /><strong>Aún no hay resultado</strong><span>Entrena o evalúa la política para ver métricas aquí.</span></div> : resultStatus === 'trained' ? <div className="rl-result-summary"><span>Política entrenada</span><strong>{Number(result.samples || 0)} muestras</strong><small>Pérdida media {Number(result.loss || 0).toFixed(4)} · fuente {String(result.source || 'registro')}</small></div> : resultStatus === 'ok' ? <div className="rl-result-summary"><span>Evaluación correcta</span><strong>{predictionLabel}</strong><small>Recomendación ante un vector neutro · sin ejecución</small></div> : <div className="rl-result-summary"><span>Estado</span><strong>{resultStatus || 'Sin datos'}</strong><small>{String(result.reason || 'No se produjo una política nueva.')}</small></div>}
          {result && <details><summary>Detalle técnico</summary><pre className="system-json">{JSON.stringify(result, null, 2)}</pre></details>}
        </aside>
      </div>
    </>}
  </section>;
}
