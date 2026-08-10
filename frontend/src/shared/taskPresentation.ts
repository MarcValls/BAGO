const PRIORITY_LABELS: Record<string, string> = {
  low: 'Baja', medium: 'Media', high: 'Alta', critical: 'Crítica'
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pendiente', running: 'En ejecución', done: 'Completada', completed: 'Completada',
  failed: 'Fallida', blocked: 'Bloqueada', active: 'Abierta', proposed: 'Propuesta',
  canon: 'Cerrada', archived: 'Archivada', invalid: 'No válido', confirmed: 'Confirmado'
};

export function compactTaskTitle(value: string, maxLength = 72): string {
  const clean = String(value || '')
    .replace(/^tarea\s*:\s*/i, '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!clean) return 'Tarea sin título';

  const instructionBreak = clean.search(/\b(?:eres el|genera un plan|cada paso|responde solo|instrucciones?)\b/i);
  const semantic = instructionBreak > 12 ? clean.slice(0, instructionBreak).trim().replace(/[,:;.-]+$/, '') : clean;
  if (semantic.length <= maxLength) return semantic;
  const clipped = semantic.slice(0, maxLength + 1);
  const wordBoundary = clipped.lastIndexOf(' ');
  return `${clipped.slice(0, wordBoundary > maxLength * 0.55 ? wordBoundary : maxLength).trim()}…`;
}

export function priorityLabel(value: unknown): string {
  const key = String(value || '').toLowerCase();
  return PRIORITY_LABELS[key] || String(value || 'Media');
}

export function statusLabel(value: unknown): string {
  const key = String(value || '').toLowerCase();
  return STATUS_LABELS[key] || String(value || 'Pendiente');
}
