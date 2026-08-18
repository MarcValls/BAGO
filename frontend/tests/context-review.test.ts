import { describe, expect, it } from 'vitest';
import { buildContextReviewPrompt, parseContextReviewResponse } from '../src/features/context-tree/contextReview';

describe('context review', () => {
  it('builds category-specific review instructions', () => {
    const prompt = buildContextReviewPrompt('risk', {
      title: 'Dependencia externa', summary: 'Puede fallar.', body: 'Mitigar con fallback.', priority: 'high', tags: ['runtime']
    });
    expect(prompt).toContain('causa, impacto, probabilidad, mitigación');
    expect(prompt).toContain('Dependencia externa');
  });

  it('parses fenced model JSON safely', () => {
    const review = parseContextReviewResponse('```json\n{"status":"warning","summary":"Falta probabilidad.","findings":[{"severity":"warning","field":"body","message":"No indica probabilidad.","suggestion":"Añadir escala."}]}\n```');
    expect(review).toMatchObject({ status: 'warning', summary: 'Falta probabilidad.' });
    expect(review?.findings).toHaveLength(1);
  });

  it('rejects non-contract responses', () => {
    expect(parseContextReviewResponse('Todo correcto')).toBeNull();
    expect(parseContextReviewResponse('{"status":"ok"}')).toBeNull();
  });
});
