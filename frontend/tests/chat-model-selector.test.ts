import { describe, expect, it } from 'vitest';
import { buildChatModelOptions } from '../src/layout/chatModelOptions';

const entries = [
  { key: 'ollama-local/qwen3:8b', provider: 'ollama-local', model_id: 'qwen3:8b', available: true },
  { key: 'ollama-local/phi4:latest', provider: 'ollama-local', model_id: 'phi4:latest', available: true },
  { key: 'openai/gpt-5-mini', provider: 'openai', model_id: 'gpt-5-mini', available: true },
  { key: 'openai/offline', provider: 'openai', model_id: 'offline', available: false }
];

describe('chat model selector', () => {
  it('lists all router models when no active-model filter exists', () => {
    expect(buildChatModelOptions(entries, null, new Set(), null).map((option) => option.key)).toEqual([
      'ollama-local/qwen3:8b',
      'ollama-local/phi4:latest',
      'openai/gpt-5-mini',
      'openai/offline'
    ]);
  });

  it('keeps available and unavailable providers visible when a local active-model filter exists', () => {
    expect(buildChatModelOptions(entries, 'ollama-local', new Set(['phi4:latest']), null)).toEqual([
      { key: 'ollama-local/qwen3:8b', label: 'ollama-local · qwen3:8b', provider: 'ollama-local', model: 'qwen3:8b', unavailable: false },
      { key: 'ollama-local/phi4:latest', label: 'ollama-local · phi4:latest', provider: 'ollama-local', model: 'phi4:latest', unavailable: false },
      { key: 'openai/gpt-5-mini', label: 'openai · gpt-5-mini', provider: 'openai', model: 'gpt-5-mini', unavailable: false },
      { key: 'openai/offline', label: 'openai · offline', provider: 'openai', model: 'offline', unavailable: true }
    ]);
  });

  it('keeps the current session override visible when the catalog changed', () => {
    expect(buildChatModelOptions(entries, 'ollama-local', new Set(['qwen3:8b']), 'openai/gpt-5-nano')[0]).toEqual({
      key: 'openai/gpt-5-nano',
      label: 'openai · gpt-5-nano · actual',
      provider: 'openai',
      model: 'gpt-5-nano'
    });
  });
});
