import { describe, expect, it } from 'vitest';
import { PIPELINE_TASK_MAX_LENGTH } from '../src/shared/inputLimits';

describe('input limits', () => {
  it('allows detailed workflow descriptions beyond the chat limit', () => {
    expect(PIPELINE_TASK_MAX_LENGTH).toBe(24_000);
    expect(PIPELINE_TASK_MAX_LENGTH).toBeGreaterThan(12_000);
  });
});
