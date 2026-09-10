import { readFileSync, readdirSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const picker = readFileSync(new URL('../src/features/workspace/WorkspacePickerDialog.tsx', import.meta.url), 'utf8');
const firstRun = readFileSync(new URL('../src/features/first-run/FirstRunWizard.tsx', import.meta.url), 'utf8');
const context = readFileSync(new URL('../src/features/context-tree/ContextTreeModule.tsx', import.meta.url), 'utf8');
const controlPlane = readFileSync(new URL('../src/app/ControlPlane.tsx', import.meta.url), 'utf8');
const componentsDir = new URL('../src/styles/components/', import.meta.url);
const components = readdirSync(componentsDir)
  .filter((f) => f.endsWith('.css'))
  .map((f) => readFileSync(new URL(`./${f}`, componentsDir), 'utf8'))
  .join('\n');

describe('workspace and context UX contract', () => {
  it('offers the same browser selector during first run', () => {
    expect(firstRun).toContain('<WorkspacePickerDialog');
    expect(picker).toContain('client.browseWorkspace');
    expect(picker).toContain('projectInspectionAction');
    expect(picker).toContain('action.label');
    expect(firstRun).toContain('continueWithInspectedWorkspace');
    expect(firstRun).toContain('activateWorkspace(projectRoot, inspectionAction.seed)');
    expect(firstRun).toContain('onConfirm={(seedAfterLink)');
    expect(controlPlane).toContain('seedAfterLink: Boolean(options?.seedAfterLink)');
    expect(firstRun).not.toContain('Usar proyecto existente');
    expect(firstRun).not.toContain('Crear proyecto demo');
    expect(controlPlane).toMatch(/event\.key === 'Escape'[\s\S]*setWorkspacePickerOpen\(false\)/);
    expect(picker).toContain("document.addEventListener('keydown', onKeyDown, true)");
    expect(components).toMatch(/\.command-palette-backdrop\.workspace-picker-backdrop\s*\{[^}]*place-items:\s*center;[^}]*padding:\s*24px;/);
    expect(picker).toContain('browseRequestRef');
    expect(picker).toContain('requestId !== browseRequestRef.current');
    expect(controlPlane).toContain('routerEntries={chatModelEntries}');
    expect(controlPlane).toContain('chatModelEntries={chatModelEntries}');
  });

  it('does not advertise semantic workspace filters without backend attributes', () => {
    const toolbar = readFileSync(new URL('../src/features/workspace/WorkspaceToolbar.tsx', import.meta.url), 'utf8');
    const explorer = readFileSync(new URL('../src/features/workspace/FileExplorer.tsx', import.meta.url), 'utf8');
    const types = readFileSync(new URL('../src/features/workspace/workspaceTypes.ts', import.meta.url), 'utf8');
    for (const unsupported of ['modified', 'in-context', 'with-evidence']) {
      expect(toolbar).not.toContain(unsupported);
      expect(explorer).not.toContain(`case '${unsupported}'`);
      expect(types).not.toContain(`| '${unsupported}'`);
    }
  });

  it('keeps advanced context capabilities behind progressive disclosure', () => {
    for (const view of ['Ahora', 'Tareas', 'Biblioteca']) expect(context).toContain(`'${view}'`);
    expect(context).toContain('context-workbench-more');
    expect(context).toContain('Configuración avanzada');
    for (const stage of ['ContextStageSources', 'ContextStageStructure', 'ContextStagePack', 'ContextStageCompile', 'ContextStageDestination']) expect(context).toContain(stage);
  });
});
