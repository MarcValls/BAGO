import type { BackendProviders, BackendRouterEntry } from '@/contracts/backend';

export function mergeProviderStates(payload: BackendProviders | null): Array<Record<string, unknown>> {
  const catalog = Array.isArray(payload?.catalog) ? payload.catalog : [];
  const live = Array.isArray(payload?.providers) ? payload.providers : [];
  const merged = new Map<string, Record<string, unknown>>();

  for (const descriptor of catalog) {
    const id = String(descriptor.id || descriptor.canonical_id || '').trim();
    if (!id) continue;
    merged.set(id, {
      ...descriptor,
      id,
      name: descriptor.name || id,
      default_base_url: descriptor.default_base_url || descriptor.base_url || '',
      runtime_kind: descriptor.runtime_kind || descriptor.runtime,
      state: descriptor.state || 'available',
      configured: descriptor.configured === true,
      enabled: descriptor.enabled === true,
      models: Array.isArray(descriptor.models) ? descriptor.models : []
    });
  }

  for (const state of live) {
    const id = String(state.id || state.name || state.canonical_id || '').trim();
    if (!id) continue;
    const catalogState = merged.get(id);
    merged.set(id, {
      ...catalogState,
      ...state,
      id,
      name: state.name || id,
      default_base_url: state.default_base_url || catalogState?.default_base_url || catalogState?.base_url || ''
    });
  }
  return [...merged.values()];
}

export function buildChatModelEntries(
  routerEntries: BackendRouterEntry[],
  payload: BackendProviders | null
): BackendRouterEntry[] {
  const merged = [...routerEntries];
  for (const provider of mergeProviderStates(payload)) {
    const providerId = String(provider.id || provider.name || '').trim();
    if (!providerId || !Array.isArray(provider.models)) continue;
    for (const rawModel of provider.models) {
      const model = typeof rawModel === 'string'
        ? rawModel
        : String((rawModel as Record<string, unknown>)?.id || (rawModel as Record<string, unknown>)?.model_id || (rawModel as Record<string, unknown>)?.name || '');
      if (!model) continue;
      const key = `${providerId}/${model}`;
      if (!merged.some((entry) => String(entry.key || `${entry.provider || ''}/${entry.model_id || entry.wire_name || ''}`) === key)) {
        merged.push({ provider: providerId, model_id: model, wire_name: model, key, available: true });
      }
    }
  }
  return merged;
}
