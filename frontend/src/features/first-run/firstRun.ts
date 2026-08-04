import type { BackendProviders, UiBootstrapSnapshot } from '@/contracts/backend';

export const FIRST_RUN_KEY = 'bago.first-run.v1.completed';

export interface FirstRunProviderOption {
  id: string;
  label: string;
  configured: boolean;
  baseUrl: string;
  enabled: boolean;
  hasSecret: boolean;
  modelCount: number;
  authKind: string;
  state: string;
}

export function shouldShowFirstRun(storage: Pick<Storage, 'getItem'> | null): boolean {
  return storage?.getItem(FIRST_RUN_KEY) !== 'true';
}

export function markFirstRunComplete(storage: Pick<Storage, 'setItem'> | null): void {
  storage?.setItem(FIRST_RUN_KEY, 'true');
}

export function firstRunProviderOptions(providers: BackendProviders | null): FirstRunProviderOption[] {
  const configured = Array.isArray(providers?.providers) ? providers.providers : [];
  const catalog = Array.isArray(providers?.catalog) ? providers.catalog : [];
  const source = [...configured, ...catalog];
  const seen = new Set<string>();
  return source.flatMap((entry) => {
    const id = String(entry.provider_id || entry.id || entry.name || '').trim();
    if (!id || seen.has(id)) return [];
    seen.add(id);
    return [{
      id,
      label: String(entry.label || entry.name || id),
      configured: Boolean(entry.configured || entry.enabled || entry.state === 'confirmed'),
      baseUrl: String(entry.base_url || entry.default_base_url || entry.url || ''),
      enabled: entry.enabled !== false,
      hasSecret: Boolean(entry.has_secret),
      modelCount: Number(entry.modelCount || entry.model_count || 0),
      authKind: String(entry.auth_kind || 'api-key'),
      state: String(entry.state || 'catalog')
    }];
  });
}

export function firstRunReadiness(snapshot: UiBootstrapSnapshot | null) {
  return {
    backend: Boolean(snapshot?.system.backendAvailable),
    provider: snapshot?.model.state === 'confirmed' || snapshot?.model.state === 'degraded',
    workspace: Boolean(snapshot?.workspace.linkedToSession && snapshot.workspace.manifestState === 'valid')
  };
}
