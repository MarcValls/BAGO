export type ChatPresentation =
  | { kind: 'message'; text: string }
  | { kind: 'activity' | 'error'; title: string; summary: string; technicalDetail?: string };

export type ChatTimelineGroup<T> = {
  id: string;
  kind: 'turn' | 'execution';
  turns: T[];
};

function parseRecord(text: string): Record<string, unknown> | null {
  const clean = text.trim();
  if (!clean.startsWith('{') || !clean.endsWith('}')) return null;
  try {
    const value = JSON.parse(clean);
    return value && typeof value === 'object' && !Array.isArray(value)
      ? value as Record<string, unknown>
      : null;
  } catch {
    return null;
  }
}

function friendlyError(message: string): string {
  const clean = message.trim();
  const missingFile = clean.match(/^file not found:\s*(.+)$/i);
  if (missingFile) return `No se encontró el recurso solicitado: ${missingFile[1]}.`;
  return clean || 'El backend no pudo completar la acción.';
}

export function presentChatTurn(text: string, status?: string): ChatPresentation {
  const clean = String(text || '').trim();
  if (/^\[tool_calls?\]$/i.test(clean)) {
    return {
      kind: 'activity',
      title: 'Herramientas utilizadas',
      summary: 'BAGO inició una acción con las herramientas del workspace.'
    };
  }

  if (/^usage:/i.test(clean)) {
    return {
      kind: 'activity',
      title: 'Salida de herramienta',
      summary: 'La herramienta devolvió sus instrucciones de uso.',
      technicalDetail: clean
    };
  }

  const record = parseRecord(clean);
  const recordError = record && (record.ok === false || record.error)
    ? String(record.error || record.message || '').trim()
    : '';
  if (recordError) {
    return {
      kind: 'error',
      title: 'Acción no completada',
      summary: friendlyError(recordError),
      technicalDetail: JSON.stringify(record, null, 2)
    };
  }

  if (record) {
    const entries = Array.isArray(record.entries) ? record.entries.length : 0;
    const files = Array.isArray(record.files) ? record.files.length : 0;
    const count = Number(record.count || entries || files || 0);
    const path = String(record.path || record.root || '').trim();
    const location = path === '.' ? 'la carpeta actual' : path;
    const summary = String(record.message || '').trim()
      || (count ? `La herramienta devolvió ${count} ${count === 1 ? 'elemento' : 'elementos'}${location ? ` de ${location}` : ''}.` : '')
      || (location ? `La herramienta completó la acción sobre ${location}.` : 'La herramienta completó la acción.');
    return {
      kind: 'activity',
      title: 'Acción completada',
      summary,
      technicalDetail: JSON.stringify(record, null, 2)
    };
  }

  if ((status === 'failed' || status === 'blocked') && clean) {
    return {
      kind: 'error',
      title: status === 'blocked' ? 'Acción bloqueada' : 'Respuesta con error',
      summary: clean
    };
  }

  return { kind: 'message', text: clean };
}

export function groupTechnicalTurns<T extends { id: string; role: string; text: string; status?: string }>(turns: T[]): ChatTimelineGroup<T>[] {
  const groups: ChatTimelineGroup<T>[] = [];
  let index = 0;
  while (index < turns.length) {
    const turn = turns[index];
    const presentation = presentChatTurn(turn.text, turn.status);
    if (turn.role !== 'assistant' || presentation.kind === 'message') {
      groups.push({ id: turn.id, kind: 'turn', turns: [turn] });
      index += 1;
      continue;
    }

    const executionTurns = [turn];
    index += 1;
    while (index < turns.length && turns[index].role === 'assistant') {
      const next = turns[index];
      executionTurns.push(next);
      index += 1;
      if (presentChatTurn(next.text, next.status).kind === 'message') break;
    }
    groups.push({ id: `execution-${turn.id}`, kind: 'execution', turns: executionTurns });
  }
  return groups;
}
