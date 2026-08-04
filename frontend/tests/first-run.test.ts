import { describe, expect, it } from 'vitest';
import { FIRST_RUN_KEY, firstRunProviderOptions, markFirstRunComplete, shouldShowFirstRun } from '../src/features/first-run/firstRun';

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
});
