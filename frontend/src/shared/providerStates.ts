import type { BackendProviders } from '@/contracts/backend';

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
