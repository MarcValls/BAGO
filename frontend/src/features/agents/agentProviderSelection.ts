import { normalizeProviderModels } from '@/shared/providerModels';

export interface AgentModelGroup {
  providerId: string;
  label: string;
  state: string;
  models: string[];
}

const BLOCKED_STATES = ['disabled', 'blocked', 'error', 'failed', 'unavailable', 'unauthenticated'];

function readBool(value: unknown): boolean {
  return value === true || value === 'true' || value === 1 || value === '1';
}

function readString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function readProviderId(provider: Record<string, unknown>): string {
  return readString(provider.id || provider.name || provider.canonical_id);
}

function isStateAllowed(state: string): boolean {
  const clean = state.toLowerCase();
  return !clean || !BLOCKED_STATES.some((blocked) => clean.includes(blocked));
}

function isLocalRuntime(provider: Record<string, unknown>): boolean {
  const runtime = readString(provider.runtime_kind || provider.runtime).toLowerCase();
  const auth = readString(provider.auth_kind).toLowerCase();
  return runtime.includes('local') || auth === 'none' || auth === 'auth_none_local';
}

export function isProviderLoggedInUsable(provider: Record<string, unknown>): boolean {
  const configured = readBool(provider.configured);
  const enabled = readBool(provider.enabled);
  const state = readString(provider.state);
  const usable = readBool(provider.usable) || readBool(provider.healthy);
  const hasSecret = readBool(provider.has_secret);

  if (!configured || !enabled || !isStateAllowed(state)) {
    return false;
  }
  if (usable) {
    return true;
  }
  if (isLocalRuntime(provider) && !hasSecret) {
    return false;
  }
  return hasSecret;
}

function readBackendModelNames(provider: Record<string, unknown>, extras: string[] = []): string[] {
  const entries = [
    ...normalizeProviderModels({ models: provider.models }),
    ...normalizeProviderModels({ models: provider.available_models }),
    ...normalizeProviderModels({ models: provider.active_models }),
    ...normalizeProviderModels({ models: extras }),
  ];
  for (const value of [provider.default_model, provider.model, provider.selected_model, provider.effective_model]) {
    const id = readString(value);
    if (id) entries.push({ id, available: true });
  }

  const seen = new Set<string>();
  const models: string[] = [];
  for (const entry of entries) {
    if (!entry.available || seen.has(entry.id)) continue;
    seen.add(entry.id);
    models.push(entry.id);
  }
  return models;
}

export function buildAgentModelGroups(
  providers: Array<Record<string, unknown>>,
  extraModels: Record<string, string[]> = {}
): AgentModelGroup[] {
  return providers
    .filter(isProviderLoggedInUsable)
    .map((provider) => {
      const providerId = readProviderId(provider);
      return {
        providerId,
        label: readString(provider.description) || readString(provider.name) || providerId,
        state: readString(provider.state) || (readBool(provider.usable) ? 'usable' : 'confirmed'),
        models: readBackendModelNames(provider, extraModels[providerId] || []),
      };
    })
    .filter((group) => Boolean(group.providerId) && group.models.length > 0);
}

export function firstAgentModelSelection(groups: AgentModelGroup[]): { provider: string; model: string } | null {
  const group = groups.find((entry) => entry.models.length > 0);
  if (!group) return null;
  return { provider: group.providerId, model: group.models[0] };
}

export function resolveAgentModelSelection(
  groups: AgentModelGroup[],
  provider: string | undefined | null,
  model: string | undefined | null
): { provider: string; model: string } | null {
  if (!groups.length) return null;

  const safeProvider = (provider ?? '').trim();
  const safeModel = (model ?? '').trim();
  const providerGroup = groups.find((group) => group.providerId === safeProvider);
  if (providerGroup && providerGroup.models.length > 0) {
    if (!safeModel || !providerGroup.models.includes(safeModel)) {
      return { provider: providerGroup.providerId, model: providerGroup.models[0] };
    }
    return { provider: providerGroup.providerId, model: safeModel };
  }
  const fallbackGroup = groups.find((group) => group.models.length > 0);
  if (!fallbackGroup) return null;
  return { provider: fallbackGroup.providerId, model: fallbackGroup.models[0] };
}

export function agentModelSelectionAvailable(groups: AgentModelGroup[], provider: string, model: string): boolean {
  return groups.some((group) => group.providerId === provider && group.models.includes(model));
}

export function encodeAgentModelSelection(provider: string, model: string): string {
  return `${encodeURIComponent(provider)}/${encodeURIComponent(model)}`;
}

export function decodeAgentModelSelection(value: string): { provider: string; model: string } | null {
  const separator = value.indexOf('/');
  if (separator < 0) return null;
  const provider = decodeURIComponent(value.slice(0, separator)).trim();
  const model = decodeURIComponent(value.slice(separator + 1)).trim();
  return provider && model ? { provider, model } : null;
}
