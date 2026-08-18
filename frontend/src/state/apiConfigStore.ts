const STORAGE_BASE = 'bago.ui.apiBase';

export function readStoredApiBase(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem(STORAGE_BASE) || '';
}

export function persistApiConfig(apiBase: string): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(STORAGE_BASE, apiBase.trim().replace(/\/+$/, ''));
}
