import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const contextModule = readFileSync(new URL('../src/features/context-tree/ContextTreeModule.tsx', import.meta.url), 'utf8');
const activityTray = readFileSync(new URL('../src/features/context-tree/ContextActivityTray.tsx', import.meta.url), 'utf8');
const sections = readFileSync(new URL('../src/features/sections.tsx', import.meta.url), 'utf8');
const workGraph = readFileSync(new URL('../src/features/graph/WorkGraph.tsx', import.meta.url), 'utf8');

describe('context action flow', () => {
  it('opens Contexto in the focused action view and keeps advanced tools available', () => {
    expect(contextModule).toContain("type ContextWorkbenchView = 'focus' | 'tasks' | 'library' | 'advanced'");
    expect(contextModule).toContain("return 'focus'");
    for (const label of ['Ahora', 'Tareas', 'Contexto', 'Avanzado']) expect(contextModule).toContain(`'${label}'`);
  });

  it('offers validation and task launch beside every pending mention', () => {
    expect(contextModule).toContain('Validar</button>');
    expect(contextModule).toContain('Iniciar tarea</button>');
    expect(activityTray).toContain('onStartTask?: (patch: ContextPatchRequest) => void');
    expect(activityTray).toContain('props.onStartTask?.(patch)');
  });

  it('projects real proposals, context tasks and pipeline steps in the graph', () => {
    expect(sections).toContain('<WorkGraph');
    expect(sections).toContain('proposals={props.contextTree.proposals}');
    expect(sections).toContain('tasks={taskNodes}');
    expect(sections).toContain('steps={steps}');
    expect(sections).not.toContain("id: 'layout-hierarchical'");
    expect(sections).not.toContain('const baseNodes = [');
    expect(workGraph).toContain('De la mención a la ejecución');
    expect(workGraph).toContain('onValidate(proposal)');
    expect(workGraph).toContain('onStartProposal(proposal)');
  });

  it('passes both the specific title and summary to Pipeline', () => {
    expect(sections).toContain("[title.trim(), summary.trim()].filter(Boolean).join('\\n\\n')");
    expect(contextModule).toContain('await props.onCreatePlan(\n      proposal.title,');
  });
});
