import type { BackendRouterEntry } from '@/contracts/backend';

export interface ChatModelOption {
  key: string;
  label: string;
}

function entryKey(entry: BackendRouterEntry): string {
  const explicit = String(entry.key || '').trim();
  if (explicit) return explicit;
  const provider = String(entry.provider || '').trim();
  const model = String(entry.model_id || entry.wire_name || '').trim();
  return provider && model ? `${provider}/${model}` : '';
}

export function buildChatModelOptions(
  entries: BackendRouterEntry[],
  activeProvider: string | null,
  activeModels: Set<string>,
  sessionModel: string | null
): ChatModelOption[] {
  const available = entries.filter((entry) => entry.available !== false && entryKey(entry));
  const scoped = activeProvider && activeModels.size > 0
    ? available.filter((entry) => {
        const provider = String(entry.provider || '').trim();
        const model = String(entry.model_id || entry.wire_name || '').trim();
        const key = entryKey(entry);
        return provider === activeProvider
          && (activeModels.has(model) || activeModels.has(key) || activeModels.has(String(entry.wire_name || '').trim()));
      })
    : available;

  const options: ChatModelOption[] = [];
  const seen = new Set<string>();
  for (const entry of scoped) {
    const key = entryKey(entry);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const provider = String(entry.provider || key.split('/', 1)[0] || '').trim();
    const model = String(entry.model_id || entry.wire_name || key.slice(key.indexOf('/') + 1)).trim();
    options.push({ key, label: provider ? `${provider} · ${model}` : model });
  }

  const current = String(sessionModel || '').trim();
  if (current && !seen.has(current)) {
    options.unshift({ key: current, label: `${current.replace('/', ' · ')} · actual` });
  }
  return options;
}
