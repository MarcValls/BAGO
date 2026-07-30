import { describe, expect, it } from 'vitest';
import { normalizeChatResponse } from '../src/shared/chatResponse';

describe('chat response normalization', () => {
  it('turns legacy task JSON into readable text', () => {
    const response = normalizeChatResponse(JSON.stringify({
      intent: 'work', objective: 'Actualizar la pantalla', facts: [], evidence: ['captura'],
      proposed_changes: ['Ocultar el contrato'], validation_actions: ['build'],
      missing_information: [], confidence: 0.9
    }));
    expect(response.state).toBe('done');
    expect(response.text).toContain('Actualizar la pantalla');
    expect(response.text).not.toContain('"intent"');
  });

  it('does not mark an empty contract as done', () => {
    const response = normalizeChatResponse(JSON.stringify({
      intent: 'work', objective: '', facts: [], evidence: [], proposed_changes: [],
      validation_actions: [], missing_information: [], confidence: 1
    }));
    expect(response.state).toBe('needs_confirmation');
  });

  it('hides the legacy clarification marker', () => {
    const response = normalizeChatResponse('__BAGO_CLARIFY__{"question":"¿Qué hago?","options":[]}');
    expect(response).toMatchObject({ text: '¿Qué hago?', state: 'needs_confirmation' });
  });
});
