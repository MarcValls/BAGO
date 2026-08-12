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
    expect(firstRun).toContain('mode="select"');
    expect(picker).toContain('client.browseWorkspace');
    expect(picker).toContain('Usar esta carpeta');
    expect(controlPlane).toMatch(/event\.key === 'Escape'[\s\S]*setWorkspacePickerOpen\(false\)/);
    expect(picker).toContain("document.addEventListener('keydown', onKeyDown, true)");
    expect(components).toMatch(/\.command-palette-backdrop\.workspace-picker-backdrop\s*\{[^}]*place-items:\s*center;[^}]*padding:\s*24px;/);
  });

  it('keeps advanced context capabilities behind progressive disclosure', () => {
    for (const view of ['Ahora', 'Tareas', 'Biblioteca']) expect(context).toContain(`'${view}'`);
    expect(context).toContain('context-workbench-more');
    expect(context).toContain('Configuración avanzada');
    for (const stage of ['ContextStageSources', 'ContextStageStructure', 'ContextStagePack', 'ContextStageCompile', 'ContextStageDestination']) expect(context).toContain(stage);
  });
});
