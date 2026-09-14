import { describe, expect, it } from 'vitest';
import { projectInspectionAction } from '../src/features/workspace/useProjectInspection';

describe('project inspection action', () => {
  it('does not offer a write action while inspection is unavailable', () => {
    expect(projectInspectionAction({ kind: 'idle' })).toMatchObject({ kind: 'unavailable', seed: false });
    expect(projectInspectionAction({ kind: 'loading' })).toMatchObject({ kind: 'unavailable', seed: false });
    expect(projectInspectionAction({ kind: 'error', message: 'Ruta inaccesible' })).toMatchObject({ kind: 'unavailable', seed: false });
  });

  it('offers abrir only for a configured, linked and confirmed workspace', () => {
    expect(projectInspectionAction({ kind: 'ready', configured: true, linked: true, bindingConfirmed: true }))
      .toMatchObject({ kind: 'open', label: 'Abrir workspace', seed: false });
  });

  it('offers vincular when BAGO is configured but not linked', () => {
    expect(projectInspectionAction({ kind: 'ready', configured: true, linked: false, bindingConfirmed: false }))
      .toMatchObject({ kind: 'link', label: 'Vincular workspace', seed: false });
  });

  it('makes preparation explicit when workspace files or binding confirmation are missing', () => {
    expect(projectInspectionAction({ kind: 'ready', configured: false, linked: false, bindingConfirmed: false }))
      .toMatchObject({ kind: 'prepare', label: 'Preparar workspace', seed: true });
    expect(projectInspectionAction({ kind: 'ready', configured: true, linked: true, bindingConfirmed: false }))
      .toMatchObject({ kind: 'prepare', seed: true });
  });
});
