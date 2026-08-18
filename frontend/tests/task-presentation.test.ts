import { describe, expect, it } from 'vitest';
import { compactTaskTitle, priorityLabel, statusLabel } from '../src/shared/taskPresentation';

describe('task presentation', () => {
  it('turns copied prompts into short task titles', () => {
    expect(compactTaskTitle('Tarea: Aplicar pack principal Eres el orquestador de BAGO. Genera un plan numerado')).toBe('Aplicar pack principal');
  });

  it('localizes technical states', () => {
    expect(priorityLabel('medium')).toBe('Media');
    expect(statusLabel('pending')).toBe('Pendiente');
  });
});
