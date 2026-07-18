import { describe, expect, it } from 'vitest';
import { resolveProviderDescriptor } from '../src/shared/provider-catalog';
import { normalizeProviderModels } from '../src/shared/providerModels';

describe('real provider registry presentation', () => {
  it('maps runtime provider ids without inventing catalog ids', () => {
    expect(resolveProviderDescriptor('copilot').provider_id).toBe('copilot');
    expect(resolveProviderDescriptor('opencode').provider_id).toBe('opencode');
    expect(resolveProviderDescriptor('cpp-local').base_url).toBe('http://127.0.0.1:8765');
  });

  it('keeps unknown backend adapters configurable under their real id', () => {
    const descriptor = resolveProviderDescriptor('custom-runtime', 'Custom runtime');
    expect(descriptor.provider_id).toBe('custom-runtime');
    expect(descriptor.label).toBe('Custom runtime');
  });

  it('normalizes the canonical model contract and removes duplicates', () => {
    expect(normalizeProviderModels({
      items: [
        { id: 'qwen3:8b', available: true },
        { model_id: 'qwen3:8b', available: true },
        { wire_name: 'offline-model', available: false }
      ]
    })).toEqual([
      { id: 'qwen3:8b', available: true },
      { id: 'offline-model', available: false }
    ]);
  });
});
