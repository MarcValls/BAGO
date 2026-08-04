import { describe, expect, it } from 'vitest';
import { groupTechnicalTurns, presentChatTurn } from '../src/shared/chatPresentation';

describe('presentChatTurn', () => {
  it('turns tool call markers into readable activity', () => {
    expect(presentChatTurn('[tool_calls]')).toEqual({
      kind: 'activity',
      title: 'Herramientas utilizadas',
      summary: 'BAGO inició una acción con las herramientas del workspace.'
    });
  });

  it('keeps backend errors visible without exposing raw JSON first', () => {
    const result = presentChatTurn('{"ok":false,"error":"File not found: project-memory"}');
    expect(result.kind).toBe('error');
    expect(result.summary).toBe('No se encontró el recurso solicitado: project-memory.');
    expect(result.technicalDetail).toContain('File not found');
  });

  it('leaves normal replies unchanged', () => {
    expect(presentChatTurn('Proyecto inspeccionado.')).toEqual({ kind: 'message', text: 'Proyecto inspeccionado.' });
  });

  it('groups tool activity, error and final assistant response', () => {
    const turns = [
      { id: '1', role: 'assistant', text: '[tool_calls]' },
      { id: '2', role: 'assistant', text: '{"ok":false,"error":"File not found: project-memory"}' },
      { id: '3', role: 'assistant', text: 'No pude completar la inspección.' },
      { id: '4', role: 'user', text: 'Reintenta.' }
    ];
    const groups = groupTechnicalTurns(turns);
    expect(groups).toHaveLength(2);
    expect(groups[0]).toMatchObject({ kind: 'execution' });
    expect(groups[0].turns.map((turn) => turn.id)).toEqual(['1', '2', '3']);
    expect(groups[1]).toMatchObject({ kind: 'turn', turns: [{ id: '4' }] });
  });
});
