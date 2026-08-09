import type { ContextNode, ContextPatchRequest } from '@/features/context-tree/contextTreeTypes';
import { Icon } from '@/shared/Icon';

type PipelineStep = Record<string, unknown>;

interface Props {
  proposals: ContextPatchRequest[];
  tasks: ContextNode[];
  steps: PipelineStep[];
  pipelineStatus: string;
  focused: boolean;
  onFocusedChange: (focused: boolean) => void;
  onValidate: (proposal: ContextPatchRequest) => void;
  onEdit: (proposal: ContextPatchRequest) => void;
  onStartProposal: (proposal: ContextPatchRequest) => void;
  onStartTask: (task: ContextNode) => void;
  onOpenTask: (task: ContextNode) => void;
  onOpenContext: () => void;
  onOpenPipeline: () => void;
}

function proposalStatus(proposal: ContextPatchRequest): string {
  if (proposal.status === 'pending') return 'Por validar';
  if (proposal.status === 'accepted' || proposal.status === 'edited') return 'Validada';
  if (proposal.status === 'rejected') return 'Descartada';
  if (proposal.status === 'failed') return 'Fallida';
  return proposal.status;
}

function taskStatus(task: ContextNode): string {
  if (task.status === 'canon') return 'Cerrada';
  if (task.status === 'archived') return 'Archivada';
  return 'Abierta';
}

function stepTitle(step: PipelineStep, index: number): string {
  return String(step.title || step.label || step.name || step.task || `Paso ${index + 1}`);
}

function stepStatus(step: PipelineStep): string {
  return String(step.status || step.state || 'pendiente');
}

export function WorkGraph(props: Props) {
  const proposals = (props.focused ? props.proposals.filter((proposal) => proposal.status === 'pending') : props.proposals).slice(0, 8);
  const tasks = (props.focused ? props.tasks.filter((task) => task.status !== 'canon' && task.status !== 'archived') : props.tasks).slice(0, 8);
  const steps = props.steps.slice(0, 8);

  return <section className="work-graph" aria-label="Mapa de trabajo accionable">
    <header className="work-graph-head">
      <div><span>MAPA DE TRABAJO</span><h2>De la mención a la ejecución</h2><p>Valida el contexto o inicia la tarea exactamente donde aparece.</p></div>
      <div className="work-graph-summary"><span><b>{proposals.length}</b> menciones</span><span><b>{tasks.length}</b> tareas</span><span><b>{steps.length}</b> pasos</span></div>
    </header>
    <div className="work-graph-toolbar">
      <div className="graph-segmented" role="group" aria-label="Alcance del mapa">
        <button type="button" className={props.focused ? 'is-active' : ''} onClick={() => props.onFocusedChange(true)}>Pendiente</button>
        <button type="button" className={!props.focused ? 'is-active' : ''} onClick={() => props.onFocusedChange(false)}>Todo</button>
      </div>
      <span><Icon name="pipeline" size={12} /> Mención → tarea → Pipeline</span>
    </div>
    <div className="work-graph-lanes">
      <section className="work-graph-lane lane-mentions">
        <header><span><Icon name="inbox" size={13} /> 1. Menciones</span><b>{proposals.length}</b></header>
        <div className="work-graph-items">
          {proposals.length === 0 && <div className="work-graph-empty"><Icon name="verified" size={18} /><strong>Sin menciones pendientes</strong><button type="button" className="text-button" onClick={props.onOpenContext}>Abrir Contexto</button></div>}
          {proposals.map((proposal) => <article key={proposal.id} className="work-graph-node" data-state={proposal.status}>
            <div className="work-graph-node-head"><span>{proposalStatus(proposal)}</span><small>{proposal.patch.operations.length} cambios</small></div>
            <h3>{proposal.title}</h3><p>{proposal.reason || 'Sin explicación adicional.'}</p>
            <div className="work-graph-node-actions">
              {proposal.status === 'pending' && <button type="button" className="primary-button compact" onClick={() => props.onValidate(proposal)}><Icon name="check" size={11} /> Validar</button>}
              <button type="button" className="secondary-button compact" onClick={() => props.onStartProposal(proposal)}><Icon name="pipeline" size={11} /> Iniciar tarea</button>
              {proposal.status === 'pending' && <button type="button" className="text-button" onClick={() => props.onEdit(proposal)}>Editar</button>}
            </div>
          </article>)}
        </div>
      </section>

      <section className="work-graph-lane lane-tasks">
        <header><span><Icon name="context" size={13} /> 2. Tareas</span><b>{tasks.length}</b></header>
        <div className="work-graph-items">
          {tasks.length === 0 && <div className="work-graph-empty"><Icon name="context" size={18} /><strong>Sin tareas de contexto</strong><button type="button" className="text-button" onClick={props.onOpenContext}>Crear tarea</button></div>}
          {tasks.map((task) => <article key={task.id} className="work-graph-node" data-state={task.status}>
            <div className="work-graph-node-head"><span>{taskStatus(task)}</span><small>{task.priority}</small></div>
            <button type="button" className="work-graph-node-title" onClick={() => props.onOpenTask(task)}><h3>{task.title}</h3><Icon name="chevron" size={12} /></button><p>{task.summary || 'Sin resumen.'}</p>
            <div className="work-graph-node-actions"><button type="button" className="primary-button compact" onClick={() => props.onStartTask(task)}><Icon name="pipeline" size={11} /> Iniciar</button><button type="button" className="text-button" onClick={() => props.onOpenTask(task)}>Abrir</button></div>
          </article>)}
        </div>
      </section>

      <section className="work-graph-lane lane-execution">
        <header><span><Icon name="pipeline" size={13} /> 3. Ejecución</span><b>{steps.length}</b></header>
        <div className="work-graph-items">
          {steps.length === 0 && <div className="work-graph-empty"><Icon name="pipeline" size={18} /><strong>Pipeline sin pasos</strong><span>Inicia una tarea desde cualquiera de las columnas anteriores.</span></div>}
          {steps.map((step, index) => <article key={String(step.id || index)} className="work-graph-node" data-state={stepStatus(step)}>
            <div className="work-graph-node-head"><span>{stepStatus(step)}</span><small>Paso {index + 1}</small></div>
            <h3>{stepTitle(step, index)}</h3><p>{String(step.summary || step.description || 'Paso generado por el Pipeline.')}</p>
            <div className="work-graph-node-actions"><button type="button" className="secondary-button compact" onClick={props.onOpenPipeline}>Abrir Pipeline <Icon name="arrowRight" size={11} /></button></div>
          </article>)}
        </div>
        <footer><span>Estado: {props.pipelineStatus}</span><button type="button" className="text-button" onClick={props.onOpenPipeline}>Ver ejecución completa</button></footer>
      </section>
    </div>
  </section>;
}
