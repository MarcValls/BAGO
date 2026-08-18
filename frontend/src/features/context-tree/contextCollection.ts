import type { ContextNodeType, ContextPatchOp } from './contextTreeTypes';
import { compactTaskTitle } from '@/shared/taskPresentation';

export interface CollectionHistoryItem {
  role: string;
  text: string;
  timestamp?: string;
}

export interface StructuredCollectionOperation {
  op: 'create';
  parent_path?: string[];
  type?: ContextNodeType;
  title: string;
  summary?: string;
  priority?: 'low' | 'medium' | 'high' | 'critical';
}

export interface StructuredCollectionProposal {
  summary: string;
  clarification: string;
  operations: StructuredCollectionOperation[];
}

const NODE_TYPES: ContextNodeType[] = ['intent', 'source', 'decision', 'rule', 'claim', 'risk', 'pending', 'evidence', 'proposal', 'note'];
const PRIORITIES = ['low', 'medium', 'high', 'critical'] as const;

export function buildCollectionPrompt(
  question: string,
  history: CollectionHistoryItem[],
  treePaths: string[]
): string {
  const transcript = history.map((item, index) => {
    const timestamp = item.timestamp ? ` [${item.timestamp}]` : '';
    return `${index + 1}. ${item.role}${timestamp}: ${item.text}`;
  }).join('\n').slice(0, 32000);
  return [
    '[BAGO_CONTEXT_COLLECTION_JSON]',
    'Analiza el historial de esta tarea y prepara una propuesta estructurada de contexto.',
    'No ejecutes acciones, no modifiques archivos y no afirmes hechos que no estén en el historial.',
    'Devuelve SOLO JSON válido, sin markdown, con esta forma exacta:',
    '{"summary":"...","clarification":"...","operations":[{"op":"create","parent_path":["UI","Pantallas"],"type":"pending","title":"...","summary":"...","priority":"medium"}]}',
    'parent_path es una ruta de ramas relativa a la raíz del árbol. Usa [] para colgar directamente de la raíz.',
    `Ramas ya existentes: ${treePaths.length ? treePaths.join(' | ') : '(ninguna)'}`,
    question.trim() ? `Pregunta del usuario: ${question.trim()}` : 'Pregunta del usuario: ninguna; identifica solo contexto claramente respaldado.',
    'Historial completo disponible:',
    transcript || '(vacío)',
    'Reglas: máximo 12 operaciones; usa solo op=create; cada título debe describir la tarea en 8 palabras o menos, sin copiar instrucciones del chat; añade el detalle al resumen; conserva las tareas abiertas como pending.'
  ].join('\n');
}

function parseCandidate(raw: string): unknown {
  const fenced = raw.match(/```(?:json)?\s*([\s\S]*?)```/i)?.[1];
  const candidates = [fenced, raw].filter(Boolean) as string[];
  for (const candidate of candidates) {
    const start = candidate.indexOf('{');
    const end = candidate.lastIndexOf('}');
    if (start < 0 || end <= start) continue;
    try {
      return JSON.parse(candidate.slice(start, end + 1));
    } catch {
      continue;
    }
  }
  return null;
}

export function parseStructuredCollection(raw: string): StructuredCollectionProposal | null {
  const value = parseCandidate(raw);
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const record = value as Record<string, unknown>;
  const rawOperations = Array.isArray(record.operations) ? record.operations : [];
  const operations: StructuredCollectionOperation[] = [];
  for (const item of rawOperations.slice(0, 12)) {
    if (!item || typeof item !== 'object' || Array.isArray(item)) continue;
    const operation = item as Record<string, unknown>;
    if (String(operation.op || 'create').toLowerCase() !== 'create') continue;
    const rawTitle = String(operation.title || '').trim();
    if (!rawTitle) continue;
    const title = compactTaskTitle(rawTitle, 72);
    const parentPath = Array.isArray(operation.parent_path)
      ? operation.parent_path.map((entry) => String(entry).trim()).filter(Boolean).slice(0, 5)
      : [];
    const typeCandidate = String(operation.type || 'note').toLowerCase() as ContextNodeType;
    const priorityCandidate = String(operation.priority || 'medium').toLowerCase() as typeof PRIORITIES[number];
    operations.push({
      op: 'create',
      parent_path: parentPath,
      type: NODE_TYPES.includes(typeCandidate) ? typeCandidate : 'note',
      title,
      summary: String(operation.summary || '').trim().slice(0, 600),
      priority: PRIORITIES.includes(priorityCandidate) ? priorityCandidate : 'medium'
    });
  }
  if (!operations.length) return null;
  return {
    summary: String(record.summary || 'Propuesta estructurada a partir del historial del chat.').trim().slice(0, 600),
    clarification: String(record.clarification || '').trim().slice(0, 600),
    operations
  };
}

export function collectionOperationToPatch(
  operation: StructuredCollectionOperation,
  parentId: string,
  nodeId: string
): ContextPatchOp {
  return {
    op: 'create',
    nodeId,
    parentId,
    type: operation.type || 'note',
    title: operation.title,
    summary: operation.summary || '',
    status: operation.type === 'pending' ? 'proposed' : 'proposed',
    priority: operation.priority || 'medium'
  };
}
