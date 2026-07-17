// Parser de patches estructurados que el chat emite con el formato:
//
//   <<BAGO:CONTEXT_PATCH_REQUEST>>
//   { ...json... }
//   <</BAGO:CONTEXT_PATCH_REQUEST>>
//
// El parser es tolerante: ignora mayúsculas, espacios extra, y devuelve
// una lista vacía si no encuentra ningún bloque válido. El frontend
// muestra cada patch como una tarjeta inline dentro del turno de chat
// (ver ContextPatchValidationCard).
import type { ContextPatchRequest } from './contextTreeTypes';
import { newPatchId } from './contextTreeApi';

const OPEN_TAG = '<<BAGO:CONTEXT_PATCH_REQUEST>>';
const CLOSE_TAG = '<</BAGO:CONTEXT_PATCH_REQUEST>>';

interface RawBlock {
  start: number;
  end: number;
  body: string;
}

function findBlocks(text: string): RawBlock[] {
  const blocks: RawBlock[] = [];
  const lower = text.toLowerCase();
  let cursor = 0;
  while (true) {
    const start = lower.indexOf(OPEN_TAG.toLowerCase(), cursor);
    if (start < 0) break;
    const end = lower.indexOf(CLOSE_TAG.toLowerCase(), start + OPEN_TAG.length);
    if (end < 0) break;
    const body = text.slice(start + OPEN_TAG.length, end);
    blocks.push({ start, end: end + CLOSE_TAG.length, body });
    cursor = end + CLOSE_TAG.length;
  }
  return blocks;
}

interface ParsedPatch {
  patch: ContextPatchRequest;
  // Bloque original en el texto (incluyendo tags) para borrarlo o
  // marcarlo como aplicado en la propia respuesta del chat.
  raw: string;
  // Offset en el texto original donde comienza el bloque.
  start: number;
  end: number;
}

function tryParseJson(body: string): Record<string, unknown> | null {
  const trimmed = body.trim();
  if (!trimmed) return null;
  // Busca el primer '{' y el último '}' para tolerar prefijos/sufijos.
  const firstBrace = trimmed.indexOf('{');
  const lastBrace = trimmed.lastIndexOf('}');
  if (firstBrace < 0 || lastBrace < 0 || lastBrace <= firstBrace) return null;
  const candidate = trimmed.slice(firstBrace, lastBrace + 1);
  try {
    const value = JSON.parse(candidate);
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return value as Record<string, unknown>;
    }
  } catch {
    return null;
  }
  return null;
}

function isContextPatchOp(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false;
  const op = String((value as Record<string, unknown>).op);
  return ['create', 'move', 'update', 'exclude', 'restore', 'canon', 'link', 'unlink', 'add_to_pack', 'remove_from_pack'].includes(op);
}

function asOpArray(value: unknown): ContextPatchRequest['patch']['operations'] {
  if (!Array.isArray(value)) return [];
  const ops: ContextPatchRequest['patch']['operations'] = [];
  for (const item of value) {
    if (isContextPatchOp(item)) {
      ops.push(item as ContextPatchRequest['patch']['operations'][number]);
    }
  }
  return ops;
}

function asRisk(value: unknown): ContextPatchRequest['riskLevel'] {
  const candidate = String(value || '').toLowerCase();
  if (['low', 'medium', 'high', 'critical'].includes(candidate)) {
    return candidate as ContextPatchRequest['riskLevel'];
  }
  return 'low';
}

export function parseContextPatchRequests(text: string, fallbackTreeId: string): ParsedPatch[] {
  const blocks = findBlocks(text);
  const out: ParsedPatch[] = [];
  for (const block of blocks) {
    const json = tryParseJson(block.body);
    if (!json) continue;
    const patch = json.patch && typeof json.patch === 'object' ? json.patch as Record<string, unknown> : null;
    if (!patch) continue;
    const operations = asOpArray(patch.operations);
    if (!operations.length) continue;
    const request: ContextPatchRequest = {
      id: newPatchId(),
      treeId: String(json.treeId || fallbackTreeId),
      validationMode: (String(json.validationMode || 'inline').toLowerCase() === 'modal' ? 'modal' : 'inline'),
      proposalType: String(json.proposalType || 'context_patch'),
      title: String(json.title || 'Cambio contextual sugerido'),
      reason: String(json.reason || 'El chat sugiere una modificación al árbol de contexto.'),
      riskLevel: asRisk(json.riskLevel),
      targetNodeId: typeof json.targetNodeId === 'string' ? json.targetNodeId : undefined,
      patch: { operations },
      createdAt: new Date().toISOString(),
      createdBy: 'chat',
      status: 'pending'
    };
    out.push({
      patch: request,
      raw: text.slice(block.start, block.end),
      start: block.start,
      end: block.end
    });
  }
  return out;
}

export function summarizePatchText(patch: ContextPatchRequest): string {
  return patch.patch.operations.map((op) => {
    switch (op.op) {
      case 'create':
        return `crear "${op.title}"`;
      case 'move':
        return `mover a ${op.newParentId}`;
      case 'update':
        return `editar ${Object.keys(op.patch).join(', ')}`;
      case 'exclude':
        return `excluir del contexto`;
      case 'restore':
        return `restaurar al contexto`;
      case 'canon':
        return op.value ? 'marcar como CANON' : 'desmarcar CANON';
      case 'link':
        return `vincular con ${op.targetId}`;
      case 'unlink':
        return `desvincular de ${op.targetId}`;
      case 'add_to_pack':
        return `añadir al pack`;
      case 'remove_from_pack':
        return `quitar del pack`;
      default:
        return op.op;
    }
  }).join(' · ');
}
