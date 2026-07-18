export interface ProviderModelEntry {
  id: string;
  available: boolean;
}

function asModelEntry(value: unknown): ProviderModelEntry | null {
  if (typeof value === 'string') {
    const id = value.trim();
    return id ? { id, available: true } : null;
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  const id = String(record.id || record.model_id || record.wire_name || '').trim();
  return id ? { id, available: record.available !== false } : null;
}

export function normalizeProviderModels(payload: unknown): ProviderModelEntry[] {
  const record = payload && typeof payload === 'object' && !Array.isArray(payload)
    ? payload as Record<string, unknown>
    : {};
  const source = Array.isArray(record.items)
    ? record.items
    : Array.isArray(record.model_items)
      ? record.model_items
      : Array.isArray(record.models)
        ? record.models
        : [];
  const seen = new Set<string>();
  const models: ProviderModelEntry[] = [];
  for (const value of source) {
    const entry = asModelEntry(value);
    if (!entry || seen.has(entry.id)) continue;
    seen.add(entry.id);
    models.push(entry);
  }
  return models;
}
