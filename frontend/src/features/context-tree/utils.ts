// Utilidades de presentación del ContextTreeModule.

export function shortenPath(value: string, maxLength = 60): string {
  const clean = String(value || '').trim();
  if (!clean || clean.length <= maxLength) return clean;
  const head = clean.slice(0, Math.max(8, Math.floor(maxLength * 0.4)));
  const tail = clean.slice(-Math.max(8, maxLength - head.length - 2));
  return `${head}…${tail}`;
}

export function formatRelativeTime(iso: string | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const now = Date.now();
  const diffMs = now - then;
  if (diffMs < 60_000) return 'hace un momento';
  if (diffMs < 3_600_000) return `hace ${Math.floor(diffMs / 60_000)} min`;
  if (diffMs < 86_400_000) return `hace ${Math.floor(diffMs / 3_600_000)} h`;
  if (diffMs < 7 * 86_400_000) return `hace ${Math.floor(diffMs / 86_400_000)} d`;
  return new Date(iso).toLocaleString();
}

export function summarizeText(value: string | undefined, maxLength = 90): string {
  if (!value) return '';
  const text = String(value).replace(/\s+/g, ' ').trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}…`;
}
