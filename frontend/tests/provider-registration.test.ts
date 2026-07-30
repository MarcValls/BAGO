import { describe, expect, it } from 'vitest';
import { normalizeProviderBaseUrl } from '@/shared/providerRegistration';

describe('provider registration URL contract', () => {
  it('stores the Ollama host and removes a duplicated API suffix', () => {
    expect(normalizeProviderBaseUrl('ollama-cloud', 'https://ollama.com/api/')).toBe('https://ollama.com');
    expect(normalizeProviderBaseUrl('ollama-local', 'http://localhost:11434/api')).toBe('http://localhost:11434');
  });

  it('uses the catalog default without changing other provider paths', () => {
    expect(normalizeProviderBaseUrl('ollama-cloud', '', 'https://ollama.com')).toBe('https://ollama.com');
    expect(normalizeProviderBaseUrl('openrouter', 'https://openrouter.ai/api/v1/')).toBe('https://openrouter.ai/api/v1');
  });
});
