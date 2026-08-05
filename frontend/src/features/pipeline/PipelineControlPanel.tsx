import { useEffect, useState } from 'react';
import type { BagoClient } from '@/api/client';
import { Icon } from '@/shared/Icon';

type RecordValue = Record<string, unknown>;

function records(value: unknown): RecordValue[] {
  return Array.isArray(value) ? value.filter((item): item is RecordValue => Boolean(item) && typeof item === 'object' && !Array.isArray(item)) : [];
}

function statusOf(item: RecordValue): string {
  return String(item.status || item.state || 'unknown').toLowerCase();
}

interface Props {
  client: BagoClient;
  onRefreshSnapshot: () => void;
}

export function PipelineControlPanel({ client, onRefreshSnapshot }: Props) {
  const [plans, setPlans] = useState<RecordValue[]>([]);
  const [jobs, setJobs] = useState<RecordValue[]>([]);
  const [selectedJob, setSelectedJob] = useState<RecordValue | null>(null);
  const [pendingPlan, setPendingPlan] = useState('');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function load() {
    setError('');
    try {
      const [planPayload, jobPayload] = await Promise.all([client.listPlans(), client.listJobs()]);
      setPlans(records(planPayload.plans));
      setJobs(records(jobPayload.jobs));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([client.listPlans(), client.listJobs()])
      .then(([planPayload, jobPayload]) => {
        if (!active) return;
        setPlans(records(planPayload.plans));
        setJobs(records(jobPayload.jobs));
      })
      .catch((cause) => { if (active) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { active = false; };
  }, [client]);

  async function run(action: string, operation: () => Promise<RecordValue>) {
    setBusy(action);
    setError('');
    setMessage('');
    try {
      const result = await operation();
      setMessage(String(result.message || (result.ok === false ? 'La operación no se completó.' : 'Operación completada.')));
      await load();
      onRefreshSnapshot();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy('');
    }
  }

  async function inspectJob(executionId: string) {
    setBusy(`detail:${executionId}`);
    setError('');
    try {
      const payload = await client.getJob(executionId);
      setSelectedJob(payload.job && typeof payload.job === 'object' ? payload.job as RecordValue : payload);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy('');
    }
  }

  return (
    <section className="pipeline-control-center" aria-label="Planes guardados y jobs">
      <div className="pipeline-section-head">
        <div><span className="surface-eyebrow">Control de ejecución</span><strong>Planes guardados y jobs</strong></div>
        <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => void load()}><Icon name="refresh" size={13} /> Refrescar</button>
      </div>

      <div className="pipeline-runtime-grid">
        <article>
          <div className="pipeline-runtime-title"><strong>Planes</strong><span>{plans.length}</span></div>
          {plans.length === 0 ? <p className="pipeline-runtime-empty">No hay planes persistentes en esta sesión.</p> : (
            <ul className="pipeline-runtime-list">
              {plans.map((plan, index) => {
                const planId = String(plan.id || plan.plan_id || `plan-${index}`);
                const planStatus = statusOf(plan);
                const stepCount = records(plan.steps).length;
                return <li key={planId}>
                  <span><strong>{String(plan.task || plan.objective || planId)}</strong><small>{planStatus} · {stepCount} pasos · {planId}</small></span>
                  {pendingPlan === planId ? (
                    <span className="pipeline-inline-confirm">
                      <button className="primary-button compact" type="button" disabled={Boolean(busy)} onClick={() => { setPendingPlan(''); void run(`execute:${planId}`, () => client.executePlan(planId)); }}>Confirmar</button>
                      <button className="text-button" type="button" onClick={() => setPendingPlan('')}>Cancelar</button>
                    </span>
                  ) : (
                    <button className="secondary-button compact" type="button" disabled={Boolean(busy) || planStatus === 'running'} onClick={() => setPendingPlan(planId)}><Icon name="send" size={13} /> Ejecutar</button>
                  )}
                </li>;
              })}
            </ul>
          )}
        </article>

        <article>
          <div className="pipeline-runtime-title"><strong>Jobs</strong><span>{jobs.length}</span></div>
          {jobs.length === 0 ? <p className="pipeline-runtime-empty">No hay jobs activos ni programados.</p> : (
            <ul className="pipeline-runtime-list">
              {jobs.map((job, index) => {
                const executionId = String(job.execution_id || job.id || `job-${index}`);
                const jobStatus = statusOf(job);
                const isPipeline = String(job.kind || '') === 'pipeline';
                return <li key={executionId}>
                  <span><strong>{String(job.prompt || job.task || job.kind || executionId)}</strong><small>{jobStatus} · {executionId}</small></span>
                  <span className="pipeline-runtime-actions">
                    <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => void inspectJob(executionId)}>Detalle</button>
                    {isPipeline && !['done', 'cancelled'].includes(jobStatus) && <button className="text-button danger" type="button" disabled={Boolean(busy)} onClick={() => void run(`cancel:${executionId}`, () => client.cancelJob(executionId))}>Cancelar</button>}
                    {isPipeline && ['failed', 'blocked'].includes(jobStatus) && <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => void run(`retry:${executionId}`, () => client.retryJob(executionId))}>Reintentar</button>}
                  </span>
                </li>;
              })}
            </ul>
          )}
        </article>
      </div>

      {message && <div className="system-tool-message" role="status">{message}</div>}
      {error && <div className="system-tool-message is-error" role="alert">{error}</div>}
      {selectedJob && <details className="system-tool-result" open><summary>Detalle del job</summary><pre className="system-json">{JSON.stringify(selectedJob, null, 2)}</pre></details>}
    </section>
  );
}
