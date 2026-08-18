import { useMemo, useState } from 'react';
import type { BagoClient } from '@/api/client';
import { Icon, type IconName } from '@/shared/Icon';
import { PIPELINE_TASK_MAX_LENGTH } from '@/shared/inputLimits';

interface PipelineTemplate {
  id: string;
  name: string;
  description: string;
  icon: IconName;
  task: string;
}

const TEMPLATES: PipelineTemplate[] = [
  { id: 'app-starter', name: 'Aplicación desde una idea', description: 'Estructura, implementación y validación.', icon: 'sparkle', task: 'Diseña y crea una aplicación a partir de esta idea:\n\n[Describe la idea, usuarios y resultado esperado]\n\nIncluye estructura, implementación, pruebas y documentación de uso.' },
  { id: 'file-batch', name: 'Procesar una carpeta', description: 'Transformación acotada con evidencia.', icon: 'folder', task: 'Procesa los archivos de [carpeta] con estas reglas:\n\n[Reglas de transformación]\n\nNo sobrescribas los originales. Genera un resumen de cambios y receipts.' },
  { id: 'local-report', name: 'Generar un informe', description: 'Informe Markdown y JSON desde fuentes locales.', icon: 'evidence', task: 'Genera un informe sobre [tema] usando [fuentes locales]. Incluye resumen, hallazgos, incidencias y próximos pasos. Exporta Markdown y JSON.' },
  { id: 'scheduled-report', name: 'Informe programado', description: 'Informe recurrente con programación explícita.', icon: 'history', task: 'Genera periódicamente un informe de actividad del workspace: archivos modificados, tareas abiertas, ejecuciones fallidas y receipts recientes.' }
];

const STAGES = ['Objetivo', 'Origen', 'Entradas', 'Dependencias', 'Ejecución', 'Programación', 'Revisión'] as const;
const CAPABILITIES = [
  { id: 'local.text-transform', label: 'Transformar texto' },
  { id: 'local.file-batch', label: 'Procesar archivos' },
  { id: 'local.report-builder', label: 'Construir informes' }
];
const PERMISSIONS = [
  { id: 'filesystem.read', label: 'Leer archivos' },
  { id: 'filesystem.write', label: 'Escribir archivos' },
  { id: 'network', label: 'Acceder a red' },
  { id: 'process', label: 'Ejecutar procesos' }
];

interface Props {
  client: BagoClient;
  task: string;
  hasSteps: boolean;
  onTaskChange: (task: string) => void;
  onCreatePlan: (task: string) => Promise<void>;
  onOpenCapabilities: () => void;
  onCreated: () => void;
}

function parseVariables(value: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(value || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

export function PipelineGuidedBuilder(props: Props) {
  const [stage, setStage] = useState(0);
  const [source, setSource] = useState<'idea' | 'template' | 'package'>('idea');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [variablesText, setVariablesText] = useState('{\n  "input": ""\n}');
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [modelPolicy, setModelPolicy] = useState('auto');
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [scheduleMinutes, setScheduleMinutes] = useState(1440);
  const [scheduleConfirmed, setScheduleConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const selected = useMemo(() => TEMPLATES.find((item) => item.id === selectedTemplate) || null, [selectedTemplate]);
  const variables = useMemo(() => parseVariables(variablesText), [variablesText]);

  const useTemplate = (template: PipelineTemplate) => {
    setSource('template');
    setSelectedTemplate(template.id);
    props.onTaskChange(template.task);
    if (template.id === 'scheduled-report') setScheduleEnabled(true);
  };

  const toggle = (value: string, values: string[], update: (next: string[]) => void) => {
    update(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  };

  const canAdvance = stage === 0
    ? Boolean(props.task.trim())
    : stage === 2
      ? variables !== null
      : stage === 5
        ? !scheduleEnabled || scheduleConfirmed
        : true;

  const create = async () => {
    const objective = props.task.trim();
    if (!objective || !variables) return;
    setBusy(true);
    setError('');
    try {
      const contract = [
        objective,
        '',
        'Configuración estructurada del Pipeline:',
        `- origen: ${source}${selected ? ` (${selected.name})` : ''}`,
        `- variables: ${JSON.stringify(variables)}`,
        `- capacidades: ${capabilities.length ? capabilities.join(', ') : 'ninguna'}`,
        `- permisos aprobables: ${permissions.length ? permissions.join(', ') : 'ninguno'}`,
        `- política de modelo: ${modelPolicy}`,
        '- conserva receipts y detén el flujo ante fallos no recuperables.'
      ].join('\n');
      await props.onCreatePlan(contract);
      if (scheduleEnabled) {
        await props.client.createSchedule({
          name: selected?.name || objective.split('\n')[0].slice(0, 120) || 'Pipeline programado',
          target_type: 'task',
          target: { task: contract },
          schedule_type: 'interval',
          interval_s: Math.max(1, scheduleMinutes) * 60,
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
          enabled: true,
          confirmed: true,
          approved_permissions: permissions
        });
      }
      props.onCreated();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No se pudo crear el Pipeline.');
    } finally {
      setBusy(false);
    }
  };

  return <section className="pipeline-builder pipeline-guided-builder" aria-label="Creador guiado de Pipeline">
    <nav className="pipeline-builder-steps" aria-label="Pasos del creador">
      {STAGES.map((label, index) => <button key={label} type="button" className={stage === index ? 'is-active' : index < stage ? 'is-complete' : ''} aria-current={stage === index ? 'step' : undefined} onClick={() => { if (index <= stage || canAdvance) setStage(index); }}><span>{index + 1}</span>{label}</button>)}
    </nav>

    <div className="pipeline-builder-stage">
      {stage === 0 && <label className="pipeline-builder-task"><span>¿Qué resultado debe producir?</span><textarea value={props.task} onChange={(event) => props.onTaskChange(event.target.value)} placeholder="Describe el objetivo, para quién es y cómo sabrás que está terminado…" rows={8} maxLength={PIPELINE_TASK_MAX_LENGTH} /><small>{props.task.length.toLocaleString()} / {PIPELINE_TASK_MAX_LENGTH.toLocaleString()} caracteres</small></label>}

      {stage === 1 && <div className="pipeline-builder-source"><h3>Elige un punto de partida</h3><div className="pipeline-source-grid">
        <button type="button" className={source === 'idea' ? 'is-selected' : ''} onClick={() => { setSource('idea'); setSelectedTemplate(''); }}><Icon name="sparkle" size={18} /><span><strong>Idea libre</strong><small>Construir desde el objetivo escrito.</small></span></button>
        <button type="button" className={source === 'template' ? 'is-selected' : ''} onClick={() => setSource('template')}><Icon name="pipeline" size={18} /><span><strong>Plantilla</strong><small>Partir de un patrón editable.</small></span></button>
        <button type="button" className={source === 'package' ? 'is-selected' : ''} onClick={() => setSource('package')}><Icon name="pack" size={18} /><span><strong>Paquete</strong><small>Usar un Pipeline BAGO instalado.</small></span></button>
      </div>{source === 'template' && <div className="pipeline-template-grid">{TEMPLATES.map((template) => <button key={template.id} type="button" title={template.description} className={selectedTemplate === template.id ? 'is-selected' : ''} onClick={() => useTemplate(template)}><Icon name={template.icon} size={17} /><strong>{template.name}</strong></button>)}</div>}{source === 'package' && <button className="secondary-button" type="button" onClick={props.onOpenCapabilities}><Icon name="pack" size={14} /> Abrir catálogo de paquetes</button>}</div>}

      {stage === 2 && <div className="pipeline-builder-fields"><h3>Variables y entradas</h3><p>Define un objeto JSON pequeño. El backend validará los valores antes de ejecutar.</p><textarea value={variablesText} onChange={(event) => setVariablesText(event.target.value)} rows={9} spellCheck={false} aria-invalid={variables === null} />{variables === null && <span className="system-tool-message is-error">Introduce un objeto JSON válido.</span>}</div>}

      {stage === 3 && <div className="pipeline-builder-fields"><h3>Capacidades y dependencias</h3><p>Selecciona solo las piezas necesarias. Se resolverán antes de iniciar.</p><div className="pipeline-option-grid">{CAPABILITIES.map((item) => <label key={item.id}><input type="checkbox" checked={capabilities.includes(item.id)} onChange={() => toggle(item.id, capabilities, setCapabilities)} /><span><strong>{item.label}</strong><small>{item.id}</small></span></label>)}</div><button className="text-button" type="button" onClick={props.onOpenCapabilities}>Revisar catálogo completo</button></div>}

      {stage === 4 && <div className="pipeline-builder-fields"><h3>Permisos y modelo</h3><p>Los permisos sensibles seguirán requiriendo confirmación en la ejecución.</p><div className="pipeline-option-grid">{PERMISSIONS.map((item) => <label key={item.id}><input type="checkbox" checked={permissions.includes(item.id)} onChange={() => toggle(item.id, permissions, setPermissions)} /><span><strong>{item.label}</strong><small>{item.id}</small></span></label>)}</div><label className="pipeline-builder-select"><span>Política de modelo</span><select value={modelPolicy} onChange={(event) => setModelPolicy(event.target.value)}><option value="auto">Automática</option><option value="fast">Priorizar rapidez</option><option value="capable">Priorizar capacidad</option><option value="local">Solo modelos locales</option></select></label></div>}

      {stage === 5 && <div className="pipeline-builder-fields"><h3>Programación opcional</h3><label className="capability-package-check"><input type="checkbox" checked={scheduleEnabled} onChange={(event) => { setScheduleEnabled(event.target.checked); if (!event.target.checked) setScheduleConfirmed(false); }} /><span>Crear una programación recurrente después de generar el Pipeline</span></label>{scheduleEnabled && <div className="pipeline-builder-schedule-fields"><label><span>Cada</span><input type="number" min={1} value={scheduleMinutes} onChange={(event) => setScheduleMinutes(Math.max(1, Number(event.target.value) || 1))} /><span>minutos</span></label><label className="capability-package-check"><input type="checkbox" checked={scheduleConfirmed} onChange={(event) => setScheduleConfirmed(event.target.checked)} /><span>Confirmo que BAGO podrá ejecutar esta tarea automáticamente</span></label></div>}<p className="pipeline-builder-note">Importar una plantilla nunca activa su programación. Esta confirmación crea una nueva programación explícita.</p></div>}

      {stage === 6 && <div className="pipeline-builder-review"><h3>Revisa antes de crear</h3><dl><div><dt>Objetivo</dt><dd>{props.task.trim().split('\n')[0]}</dd></div><div><dt>Origen</dt><dd>{source}{selected ? ` · ${selected.name}` : ''}</dd></div><div><dt>Entradas</dt><dd>{variables ? Object.keys(variables).length : 0} variables</dd></div><div><dt>Dependencias</dt><dd>{capabilities.length ? capabilities.join(', ') : 'Ninguna'}</dd></div><div><dt>Permisos</dt><dd>{permissions.length ? permissions.join(', ') : 'Ninguno'}</dd></div><div><dt>Modelo</dt><dd>{modelPolicy}</dd></div><div><dt>Programación</dt><dd>{scheduleEnabled ? `cada ${scheduleMinutes} minutos` : 'No crear'}</dd></div></dl><p>Al crear se genera un plan persistente. La ejecución seguirá siendo una acción separada y confirmable.</p></div>}
    </div>

    {error && <div className="system-tool-message is-error" role="alert">{error}</div>}
    <footer><button className="secondary-button" type="button" disabled={stage === 0 || busy} onClick={() => setStage((current) => Math.max(0, current - 1))}>Atrás</button>{stage < STAGES.length - 1 ? <button className="primary-button" type="button" disabled={!canAdvance || busy} onClick={() => setStage((current) => Math.min(STAGES.length - 1, current + 1))}>Continuar <Icon name="chevron" size={14} /></button> : <button className="primary-button" type="button" disabled={busy || !props.task.trim() || variables === null || (scheduleEnabled && !scheduleConfirmed)} onClick={() => void create()}><Icon name="pipeline" size={15} /> {busy ? 'Creando…' : props.hasSteps ? 'Crear nuevo plan' : 'Generar Pipeline'}</button>}</footer>
  </section>;
}
