// quiet-status.ts
// Regla: si está confirmado/ok/listo, no decir nada.
// Si hay error/bloqueo/parcial, sí mostrar la etiqueta.

const SILENT: Record<string, true> = {
  confirmed: true,
  ok: true,
  done: true,
  valid: true,
  certified: true,
  ready: true,
  active: true,
  available: true
};

const LABELS: Record<string, string> = {
  running: 'En curso',
  loading: 'Cargando',
  pending: 'Pendiente',
  partial: 'Parcial',
  stale: 'Desactualizado',
  degraded: 'Limitado',
  legacy_detected: 'Legado',
  blocked: 'Bloqueado',
  error: 'Con error',
  failed: 'Con error',
  rejected: 'Rechazado',
  invalid: 'No válido',
  not_detected: 'No detectado',
  refused: 'Rechazado',
  high: 'Alto',
  unknown: '—',
  none: '—'
};

export function quietStatus(value: string | null | undefined): string {
  if (!value) return '';
  const key = String(value).toLowerCase().trim();
  if (SILENT[key]) return '';
  return LABELS[key] || value;
}
