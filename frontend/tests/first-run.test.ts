import { describe, expect, it } from 'vitest';
import { FIRST_RUN_DISMISSED_KEY, FIRST_RUN_KEY, firstRunInitialStep, firstRunProviderOptions, markFirstRunComplete, markFirstRunDismissed, shouldShowFirstRun, shouldSkipAutomaticFirstRun } from '../src/features/first-run/firstRun';

describe('first run contract', () => {
  it('remains visible until the user completes it', () => {
    const values = new Map<string, string>();
    const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value) };
    expect(shouldShowFirstRun(storage)).toBe(true);
    markFirstRunComplete(storage);
    expect(values.get(FIRST_RUN_KEY)).toBe('true');
    expect(shouldShowFirstRun(storage)).toBe(false);
  });

  it('does not confuse dismissal with completion', () => {
    const values = new Map<string, string>();
    const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value) };
    markFirstRunDismissed(storage);
    expect(values.get(FIRST_RUN_DISMISSED_KEY)).toBe('true');
    expect(values.get(FIRST_RUN_KEY)).toBeUndefined();
    expect(shouldShowFirstRun(storage)).toBe(false);
  });

  it('deduplicates provider catalog entries', () => {
    const options = firstRunProviderOptions({ catalog: [{ provider_id: 'copilot', label: 'Copilot' }, { id: 'copilot' }, { id: 'ollama-local' }] });
    expect(options.map((item) => item.id)).toEqual(['copilot', 'ollama-local']);
  });

  it('skips the automatic wizard when the runtime is already ready', () => {
    expect(shouldSkipAutomaticFirstRun({
      system: { state: 'confirmed', backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: true, manifestState: 'valid' },
      session: { state: 'valid' }
    } as never)).toBe(true);
    expect(shouldSkipAutomaticFirstRun({
      system: { state: 'confirmed', backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: false, manifestState: 'missing' },
      session: { state: 'missing' }
    } as never)).toBe(false);
  });

  it('does not skip setup from a degraded or unbound runtime signal', () => {
    const ready = {
      system: { state: 'confirmed', backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: true, manifestState: 'valid' },
      session: { state: 'valid' }
    } as never;
    expect(shouldSkipAutomaticFirstRun({ ...ready, system: { state: 'error', backendAvailable: false } })).toBe(false);
    expect(shouldSkipAutomaticFirstRun({ ...ready, system: { state: 'degraded', backendAvailable: true } })).toBe(false);
    expect(shouldSkipAutomaticFirstRun({ ...ready, system: { state: 'blocked', backendAvailable: true } })).toBe(false);
    expect(shouldSkipAutomaticFirstRun({ ...ready, model: { state: 'degraded' } })).toBe(false);
    expect(shouldSkipAutomaticFirstRun({ ...ready, session: { state: 'missing' } })).toBe(false);
  });

  it('opens directly on the first setup step that still needs attention', () => {
    expect(firstRunInitialStep(null)).toBe(0);
    expect(firstRunInitialStep({
      system: { state: 'confirmed', backendAvailable: true },
      model: { state: 'missing' },
      workspace: { linkedToSession: false, manifestState: 'missing' },
      session: { state: 'missing' }
    } as never)).toBe(1);
    expect(firstRunInitialStep({
      system: { state: 'confirmed', backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: false, manifestState: 'missing' },
      session: { state: 'missing' }
    } as never)).toBe(2);
    expect(firstRunInitialStep({
      system: { state: 'confirmed', backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: true, manifestState: 'valid' },
      session: { state: 'valid' }
    } as never)).toBe(3);
  });
});
