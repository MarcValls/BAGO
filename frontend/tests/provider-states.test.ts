import { describe, expect, it } from 'vitest';
import { buildChatModelEntries, mergeProviderStates } from '@/shared/providerStates';

describe('provider catalogue and live state merge', () => {
  it('keeps every catalog provider while live state remains authoritative', () => {
    const result = mergeProviderStates({
      catalog: [
        { id: 'copilot', description: 'GitHub Copilot', runtime: 'delegated-cli', base_url: 'https://api.githubcopilot.com' },
        { id: 'openai', description: 'OpenAI' }
      ],
      providers: [
        { name: 'copilot', configured: true, state: 'ready', base_url: '', models: ['gpt-5.4-mini'] }
      ]
    });

    expect(result.map((provider) => provider.id)).toEqual(['copilot', 'openai']);
    expect(result[0]).toMatchObject({ configured: true, state: 'ready', runtime_kind: 'delegated-cli' });
    expect(result[0].models).toEqual(['gpt-5.4-mini']);
    expect(result[0].default_base_url).toBe('https://api.githubcopilot.com');
  });

  it('still supports older backends without a catalog', () => {
    expect(mergeProviderStates({ providers: [{ name: 'ollama-local' }] })).toMatchObject([
      { id: 'ollama-local', name: 'ollama-local' }
    ]);
  });

  it('builds the same chat catalogue from router and provider models', () => {
    const result = buildChatModelEntries(
      [{ provider: 'router', model_id: 'router-model', wire_name: 'router-model', key: 'router/router-model' }],
      { providers: [{ name: 'ollama-cloud', models: ['cloud-model'] }] }
    );

    expect(result.map((entry) => entry.key)).toEqual(['router/router-model', 'ollama-cloud/cloud-model']);
  });
});
