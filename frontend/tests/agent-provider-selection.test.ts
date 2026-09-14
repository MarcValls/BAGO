import { describe, expect, it } from 'vitest';
import {
  agentModelSelectionAvailable,
  buildAgentModelGroups,
  decodeAgentModelSelection,
  encodeAgentModelSelection,
  firstAgentModelSelection,
  isProviderLoggedInUsable,
  resolveAgentModelSelection,
} from '../src/features/agents/agentProviderSelection';

describe('agent provider/model eligibility', () => {
  it('allows configured enabled providers with backend-confirmed usability or credentials', () => {
    expect(isProviderLoggedInUsable({
      id: 'openai',
      configured: true,
      enabled: true,
      state: 'confirmed',
      has_secret: true,
    })).toBe(true);
    expect(isProviderLoggedInUsable({
      id: 'codex',
      configured: true,
      enabled: true,
      state: 'confirmed',
      usable: true,
      auth_kind: 'delegated',
    })).toBe(true);
  });

  it('does not expose configured local providers without a secret unless backend marks them usable', () => {
    expect(isProviderLoggedInUsable({
      id: 'ollama-local',
      configured: true,
      enabled: true,
      state: 'confirmed',
      runtime_kind: 'local',
      has_secret: false,
      usable: false,
      healthy: false,
    })).toBe(false);
    expect(isProviderLoggedInUsable({
      id: 'ollama-local',
      configured: true,
      enabled: true,
      state: 'confirmed',
      runtime_kind: 'local',
      has_secret: false,
      usable: true,
      models: ['llama3.2:3b'],
    })).toBe(true);
  });

  it('builds grouped model options only from eligible backend-confirmed models', () => {
    const groups = buildAgentModelGroups([
      {
        id: 'openai',
        description: 'OpenAI Platform',
        configured: true,
        enabled: true,
        state: 'confirmed',
        has_secret: true,
        models: ['gpt-4o-mini'],
      },
      {
        id: 'ollama-local',
        configured: true,
        enabled: true,
        runtime_kind: 'local',
        state: 'confirmed',
        models: ['llama3.2'],
      },
      {
        id: 'disabled',
        configured: true,
        enabled: false,
        has_secret: true,
        models: ['hidden'],
      },
    ], { openai: ['gpt-4o-mini', 'gpt-4.1'] });

    expect(groups).toEqual([
      {
        providerId: 'openai',
        label: 'OpenAI Platform',
        state: 'confirmed',
        models: ['gpt-4o-mini', 'gpt-4.1'],
      },
    ]);
    expect(firstAgentModelSelection(groups)).toEqual({ provider: 'openai', model: 'gpt-4o-mini' });
    expect(agentModelSelectionAvailable(groups, 'openai', 'gpt-4.1')).toBe(true);
    expect(agentModelSelectionAvailable(groups, 'openai', 'not-confirmed')).toBe(false);
  });

  it('round-trips model values without losing slash-delimited model names', () => {
    const value = encodeAgentModelSelection('openrouter', 'anthropic/claude-3.5-sonnet');
    expect(decodeAgentModelSelection(value)).toEqual({
      provider: 'openrouter',
      model: 'anthropic/claude-3.5-sonnet',
    });
  });

  it('preserves a complete existing selection while providing a default for a new agent', () => {
    const groups = buildAgentModelGroups([
      {
        id: 'openai',
        description: 'OpenAI Platform',
        configured: true,
        enabled: true,
        state: 'confirmed',
        has_secret: true,
        models: ['gpt-4o-mini', 'gpt-4.1'],
      },
      {
        id: 'anthropic',
        description: 'Anthropic',
        configured: true,
        enabled: true,
        state: 'confirmed',
        has_secret: true,
        models: ['claude-3.5-sonnet'],
      },
    ]);

    expect(resolveAgentModelSelection(groups, 'missing', 'undefined')).toEqual({
      provider: 'missing',
      model: 'undefined',
    });
    expect(resolveAgentModelSelection(groups, 'openai', 'ghost-model')).toEqual({
      provider: 'openai',
      model: 'ghost-model',
    });
    expect(resolveAgentModelSelection(groups, null, undefined)).toEqual({
      provider: 'openai',
      model: 'gpt-4o-mini',
    });
  });
});
