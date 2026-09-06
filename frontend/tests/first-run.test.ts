import { describe, expect, it } from 'vitest';
import { FIRST_RUN_KEY, firstRunInitialStep, firstRunProviderOptions, markFirstRunComplete, shouldShowFirstRun, shouldSkipAutomaticFirstRun } from '../src/features/first-run/firstRun';

describe('first run contract', () => {
  it('remains visible until the user completes it', () => {
    const values = new Map<string, string>();
    const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value) };
    expect(shouldShowFirstRun(storage)).toBe(true);
    markFirstRunComplete(storage);
    expect(values.get(FIRST_RUN_KEY)).toBe('true');
    expect(shouldShowFirstRun(storage)).toBe(false);
  });

  it('deduplicates provider catalog entries', () => {
    const options = firstRunProviderOptions({ catalog: [{ provider_id: 'copilot', label: 'Copilot' }, { id: 'copilot' }, { id: 'ollama-local' }] });
    expect(options.map((item) => item.id)).toEqual(['copilot', 'ollama-local']);
  });

  it('skips the automatic wizard when the runtime is already ready', () => {
    expect(shouldSkipAutomaticFirstRun({
      system: { backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: true, manifestState: 'valid' }
    } as never)).toBe(true);
    expect(shouldSkipAutomaticFirstRun({
      system: { backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: false, manifestState: 'missing' }
    } as never)).toBe(false);
  });

  it('opens directly on the first setup step that still needs attention', () => {
    expect(firstRunInitialStep(null)).toBe(0);
    expect(firstRunInitialStep({
      system: { backendAvailable: true },
      model: { state: 'missing' },
      workspace: { linkedToSession: false, manifestState: 'missing' }
    } as never)).toBe(1);
    expect(firstRunInitialStep({
      system: { backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: false, manifestState: 'missing' }
    } as never)).toBe(2);
    expect(firstRunInitialStep({
      system: { backendAvailable: true },
      model: { state: 'confirmed' },
      workspace: { linkedToSession: true, manifestState: 'valid' }
    } as never)).toBe(3);
  });
});
