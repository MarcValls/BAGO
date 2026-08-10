import type { BackendRouterEntry } from '@/contracts/backend';

export interface ChatModelOption {
  key: string;
  label: string;
  provider: string;
  model: string;
  unavailable?: boolean;
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
  const allEntries = entries.filter((entry) => entryKey(entry));

  const options: ChatModelOption[] = [];
  const seen = new Set<string>();
  for (const entry of allEntries) {
    const key = entryKey(entry);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    const provider = String(entry.provider || key.split('/', 1)[0] || '').trim();
    const model = String(entry.model_id || entry.wire_name || key.slice(key.indexOf('/') + 1)).trim();
    const unavailable = entry.available === false;
    options.push({ key, label: provider ? `${provider} · ${model}` : model, provider: provider || 'Otros', model, unavailable });
  }

  const current = String(sessionModel || '').trim();
  if (current && !seen.has(current)) {
    const separator = current.indexOf('/');
    const provider = separator > 0 ? current.slice(0, separator) : 'Otros';
    const model = separator > 0 ? current.slice(separator + 1) : current;
    options.unshift({ key: current, label: `${current.replace('/', ' · ')} · actual`, provider, model });
  }
  return options;
}
