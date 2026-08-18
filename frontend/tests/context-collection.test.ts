import { describe, expect, it } from 'vitest';
import { buildCollectionPrompt, parseStructuredCollection } from '@/features/context-tree/contextCollection';

describe('context collection contract', () => {
  it('builds a prompt with full bounded conversation content', () => {
    const prompt = buildCollectionPrompt('ordena UI', [
      { role: 'user', text: 'La ventana debe conservar tareas abiertas.' },
      { role: 'assistant', text: 'La rama UI tendrá pantallas.' }
    ], ['UI', 'UI/Pantallas']);
    expect(prompt).toContain('La ventana debe conservar tareas abiertas.');
    expect(prompt).toContain('UI/Pantallas');
    expect(prompt).toContain('SOLO JSON válido');
  });

  it('parses only safe structured create operations', () => {
    const proposal = parseStructuredCollection('```json\n{"summary":"UI","clarification":"","operations":[{"op":"create","parent_path":["UI","Pantallas"],"type":"pending","title":"Chat","summary":"Pantalla abierta","priority":"medium"},{"op":"delete","title":"no permitido"}]}\n```');
    expect(proposal?.operations).toHaveLength(1);
    expect(proposal?.operations[0].parent_path).toEqual(['UI', 'Pantallas']);
    expect(proposal?.operations[0].type).toBe('pending');
  });
});
