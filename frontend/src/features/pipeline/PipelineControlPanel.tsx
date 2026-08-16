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
  onSetSection?: (section: 'chat' | 'pipeline' | 'workspace' | 'system' | 'home' | 'context' | 'evidence') => void;
  onClose?: () => void;
}

export function PipelineControlPanel({ client, onRefreshSnapshot, onSetSection, onClose }: Props) {
  const [plans, setPlans] = useState<RecordValue[]>([]);
  const [jobs, setJobs] = useState<RecordValue[]>([]);
  const [schedules, setSchedules] = useState<RecordValue[]>([]);
  const [selectedJob, setSelectedJob] = useState<RecordValue | null>(null);
  const [pendingPlan, setPendingPlan] = useState('');
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [scheduleName, setScheduleName] = useState('');
  const [scheduleTask, setScheduleTask] = useState('');
  const [scheduleMinutes, setScheduleMinutes] = useState(60);
  const [scheduleConfirmed, setScheduleConfirmed] = useState(false);

  async function load() {
    setError('');
    try {
      const [planPayload, jobPayload, schedulePayload] = await Promise.all([client.listPlans(), client.listJobs(), client.listSchedule()]);
      setPlans(records(planPayload.plans));
      setJobs(records(jobPayload.jobs));
      setSchedules(records(schedulePayload.jobs));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([client.listPlans(), client.listJobs(), client.listSchedule()])
      .then(([planPayload, jobPayload, schedulePayload]) => {
        if (!active) return;
        setPlans(records(planPayload.plans));
        setJobs(records(jobPayload.jobs));
        setSchedules(records(schedulePayload.jobs));
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
      if (action.startsWith('execute:') && typeof onSetSection === 'function') {
        setTimeout(() => onSetSection('chat'), 0);
      }
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

  const createSchedule = () => run('schedule:create', async () => {
    const response = await client.createSchedule({
      name: scheduleName.trim(),
      target_type: 'task',
      target: { task: scheduleTask.trim() },
      schedule_type: 'interval',
      interval_s: Math.max(1, scheduleMinutes) * 60,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
      enabled: true,
      confirmed: scheduleConfirmed,
      approved_permissions: []
    });
    setScheduleName('');
    setScheduleTask('');
    setScheduleConfirmed(false);
    return response;
  });

  return (
    <section className="pipeline-control-center" aria-label="Planes guardados y jobs">
      <div className="pipeline-section-head">
        <strong>Planes y ejecuciones</strong>
        <div className="pipeline-section-head-actions">
          <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => void load()}><Icon name="refresh" size={13} /> Refrescar</button>
          {onClose && <button className="text-button" type="button" aria-label="Cerrar" onClick={onClose}><Icon name="close" size={13} /></button>}
        </div>
      </div>

      <div className="pipeline-runtime-grid">
        <article>
          <div className="pipeline-runtime-title"><strong>Planes</strong><span>{plans.length}</span></div>
          {plans.length === 0 ? <p className="pipeline-runtime-empty">No hay planes guardados.</p> : (
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
          {jobs.length === 0 ? <p className="pipeline-runtime-empty">No hay ejecuciones.</p> : (
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

      <section className="pipeline-schedule-workbench">
        <div className="pipeline-section-head">
          <strong>Programaciones</strong>
          <span>{schedules.length} configuradas</span>
        </div>
        <form className="pipeline-schedule-form" onSubmit={(event) => { event.preventDefault(); void createSchedule(); }}>
          <label><span>Nombre</span><input value={scheduleName} required maxLength={120} onChange={(event) => setScheduleName(event.target.value)} placeholder="Informe semanal" /></label>
          <label className="pipeline-schedule-task"><span>Tarea</span><textarea value={scheduleTask} required rows={2} onChange={(event) => setScheduleTask(event.target.value)} placeholder="Genera un informe de los archivos modificados..." /></label>
          <label><span>Cada (minutos)</span><input type="number" min={1} value={scheduleMinutes} onChange={(event) => setScheduleMinutes(Math.max(1, Number(event.target.value) || 1))} /></label>
          <label className="capability-package-check"><input type="checkbox" checked={scheduleConfirmed} onChange={(event) => setScheduleConfirmed(event.target.checked)} /><span>Confirmo la creación y ejecución recurrente</span></label>
          <button className="primary-button compact" type="submit" disabled={Boolean(busy) || !scheduleName.trim() || !scheduleTask.trim() || !scheduleConfirmed}>{busy === 'schedule:create' ? 'Creando…' : 'Crear programación'}</button>
        </form>
        <div className="pipeline-schedule-list">
          {schedules.length === 0 && <p className="pipeline-runtime-empty">No hay tareas programadas.</p>}
          {schedules.map((schedule) => {
            const id = String(schedule.id || '');
            const enabled = schedule.enabled === true;
            return <article key={id}>
              <span><strong>{String(schedule.name || id)}</strong><small>{enabled ? 'Activa' : 'Pausada'} · próxima {String(schedule.next_run_at || 'sin fecha')} · {Number(schedule.run_count || 0)} ejecuciones</small>{schedule.error ? <em>{String(schedule.error)}</em> : null}</span>
              <div>
                <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => void run(`schedule:run:${id}`, () => client.runSchedule(id))}>Ejecutar ahora</button>
                <button className="text-button" type="button" disabled={Boolean(busy)} onClick={() => void run(`schedule:toggle:${id}`, () => client.updateSchedule(id, { enabled: !enabled, confirmed: true }))}>{enabled ? 'Pausar' : 'Reanudar'}</button>
                <button className="text-button danger" type="button" disabled={Boolean(busy)} onClick={() => void run(`schedule:delete:${id}`, () => client.deleteSchedule(id))}>Eliminar</button>
              </div>
            </article>;
          })}
        </div>
      </section>

      {message && <div className="system-tool-message" role="status">{message}</div>}
      {error && <div className="system-tool-message is-error" role="alert">{error}</div>}
      {selectedJob && <details className="system-tool-result" open><summary>Detalle del job</summary><pre className="system-json">{JSON.stringify(selectedJob, null, 2)}</pre></details>}
    </section>
  );
}
