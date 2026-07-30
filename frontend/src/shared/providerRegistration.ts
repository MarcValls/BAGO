const OLLAMA_PROVIDERS = new Set(['ollama-local', 'ollama-cloud']);

export function normalizeProviderBaseUrl(providerId: string, value: unknown, fallback = ''): string {
  let url = String(value || fallback || '').trim().replace(/\/+$/, '');
  if (OLLAMA_PROVIDERS.has(providerId) && /\/api$/i.test(url)) {
    url = url.slice(0, -4).replace(/\/+$/, '');
  }
  return url;
}
