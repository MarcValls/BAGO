// Clasificador de riesgo de un patch. Decide si la UI muestra
// validación inline, requiere revisión CRIT, o bloquea el patch.
//
// Reglas adoptadas:
//   - Operaciones sobre nodos CANON o que los vuelven CANON son CRIT.
//   - Excluir nodos activos de impacto alto es CRIT.
//   - Modificar/eliminar nodos que ya están en el pack es HIGH.
//   - Crear reglas, mover activos, excluir fuentes no canónicas es MEDIUM.
//   - Crear notas, mover no activos, vincular no críticos es LOW.
//
// La función toma la operación concreta + el contexto (status actual
// del nodo, pertenencia al pack activo) y devuelve un nivel de riesgo
// agregado para todo el patch. El patch se evalúa operación por
// operación y se queda con el peor nivel.
import type {
  ContextBankItem,
  ContextNode,
  ContextPatchOp,
  ContextPatchRequest,
  ContextTree
} from './contextTreeTypes';
import type { ContextPack } from './contextTreeTypes';

export interface PatchRiskContext {
  tree: ContextTree;
  activePack?: ContextPack;
}

function nodeRiskForOperation(node: ContextNode | undefined, op: ContextPatchOp): ContextPatchRequest['riskLevel'] {
  if (!node) return 'low';
  if (op.op === 'canon') {
    // Convertir o revertir canon es siempre CRIT.
    return 'critical';
  }
  if (node.status === 'canon' && (op.op === 'update' || op.op === 'exclude' || op.op === 'move')) {
    return 'critical';
  }
  if (op.op === 'exclude' && node.status === 'active' && (node.priority === 'high' || node.priority === 'critical')) {
    return 'critical';
  }
  if (op.op === 'update' && (node.type === 'decision' || node.type === 'rule') && node.status === 'active') {
    return 'high';
  }
  if (op.op === 'move' && node.status === 'active') {
    return 'medium';
  }
  if (op.op === 'exclude' && node.status === 'active') {
    return 'medium';
  }
  if (op.op === 'add_to_pack' || op.op === 'remove_from_pack') {
    return 'medium';
  }
  if (op.op === 'create' && (op.type === 'rule' || op.type === 'decision' || op.type === 'risk')) {
    return 'medium';
  }
  if (op.op === 'create') {
    return 'low';
  }
  return 'low';
}

function isInActivePack(nodeId: string, pack?: ContextPack): boolean {
  if (!pack) return false;
  return pack.nodeIds.includes(nodeId);
}

export function classifyOperationRisk(
  op: ContextPatchOp,
  ctx: PatchRiskContext
): ContextPatchRequest['riskLevel'] {
  if (op.op === 'create') {
    return nodeRiskForOperation(undefined, op);
  }
  if (op.op === 'link' || op.op === 'unlink') {
    const target = ctx.tree.nodes[op.targetId];
    if (target && (target.status === 'canon' || target.priority === 'critical')) {
      return 'high';
    }
    return 'low';
  }
  const node = ctx.tree.nodes[op.nodeId];
  const baseRisk = nodeRiskForOperation(node, op);
  // Si la operación toca un nodo que está en el pack activo, sube un escalón.
  if (baseRisk === 'medium' && isInActivePack(op.nodeId, ctx.activePack)) {
    return 'high';
  }
  if (baseRisk === 'low' && isInActivePack(op.nodeId, ctx.activePack)) {
    return 'medium';
  }
  return baseRisk;
}

const RISK_ORDER: Record<ContextPatchRequest['riskLevel'], number> = {
  low: 0,
  medium: 1,
  high: 2,
  critical: 3
};

export function worstRisk(...levels: ContextPatchRequest['riskLevel'][]): ContextPatchRequest['riskLevel'] {
  return levels.reduce((acc, level) => (RISK_ORDER[level] > RISK_ORDER[acc] ? level : acc), 'low');
}

export function classifyPatchRisk(patch: ContextPatchRequest, ctx: PatchRiskContext): ContextPatchRequest['riskLevel'] {
  // Si el patch declara su propio riskLevel, lo respetamos salvo que el
  // análisis local lo eleve. Esto evita confiar ciegamente en lo que
  // dice el chat.
  const local = worstRisk(...patch.patch.operations.map((op) => classifyOperationRisk(op, ctx)));
  if (RISK_ORDER[local] >= RISK_ORDER[patch.riskLevel]) {
    return local;
  }
  return patch.riskLevel;
}

export function suggestNodeTypeForBankItem(item: ContextBankItem): ContextNode['type'] {
  if (item.kind === 'workspace_file' || item.kind === 'workspace_directory' || item.kind === 'source_root') {
    return 'source';
  }
  if (item.kind === 'claim' || item.kind === 'receipt') {
    return 'evidence';
  }
  if (item.kind === 'memory') {
    return 'note';
  }
  if (item.kind === 'history') {
    return 'note';
  }
  if (item.kind === 'rule') {
    return 'rule';
  }
  if (item.kind === 'project_status') {
    return 'risk';
  }
  return 'note';
}
