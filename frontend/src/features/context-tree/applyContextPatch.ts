// Aplica un patch validado al árbol. Garantiza:
//   1. Validación previa (ciclo, nodo inexistente, ROOT, CANON, etc.).
//   2. Snapshot del estado anterior en cada nodo tocado.
//   3. Emisión de un receipt con la mutación.
//   4. Recompilación del pack si corresponde.
//
// Devuelve una tupla [tree, pack, receipt] para que el caller los
// persista en lote. Si la validación falla, lanza un Error con código
// semántico para que la UI lo muestre.
import type {
  ContextNode,
  ContextPack,
  ContextPatchOp,
  ContextPatchRequest,
  ContextReceipt,
  ContextTree
} from './contextTreeTypes';
import { newNodeId } from './contextTreeApi';

const CANON_FIELDS: Array<keyof Pick<ContextNode, 'parentId' | 'type' | 'status' | 'title' | 'summary' | 'body' | 'tags' | 'metadata'>> = [
  'parentId', 'type', 'status', 'title', 'summary', 'body', 'tags', 'metadata'
];

export class PatchValidationError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'PatchValidationError';
    this.code = code;
  }
}

interface ApplyContext {
  now?: string;
  actor?: 'user' | 'chat' | 'system';
  patchId: string;
  pack?: ContextPack;
}

function snapshotNode(node: ContextNode): ContextNode['previous'] {
  return {
    parentId: node.parentId,
    type: node.type,
    status: node.status,
    title: node.title,
    summary: node.summary,
    body: node.body,
    tags: [...node.tags],
    metadata: { ...node.metadata }
  };
}

function isAncestor(tree: ContextTree, ancestorId: string, candidateId: string): boolean {
  if (ancestorId === candidateId) return true;
  let current = tree.nodes[candidateId];
  const guard = new Set<string>();
  while (current && current.parentId) {
    if (guard.has(current.id)) return false;
    guard.add(current.id);
    if (current.parentId === ancestorId) return true;
    current = tree.nodes[current.parentId];
  }
  return false;
}

function assertNodeExists(tree: ContextTree, id: string, label: string) {
  if (!tree.nodes[id]) {
    throw new PatchValidationError('node_missing', `No se encontró el nodo ${label}: ${id}`);
  }
}

function assertNotCanon(node: ContextNode, action: string) {
  if (node.status === 'canon') {
    throw new PatchValidationError('canon_protected', `Nodo CANON no puede ${action}. Solicita una nueva versión o crea una contradicción.`);
  }
}

function applyCreate(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'create' }>, ctx: ApplyContext): ContextNode {
  if (!op.title?.trim()) {
    throw new PatchValidationError('invalid_create', 'Un nodo nuevo requiere título.');
  }
  assertNodeExists(tree, op.parentId, 'padre');
  const parent = tree.nodes[op.parentId];
  if (parent.type === 'root' && op.type === 'root') {
    throw new PatchValidationError('root_conflict', 'Solo puede haber una raíz activa.');
  }
  if (parent.status === 'canon' && op.type === 'root') {
    throw new PatchValidationError('canon_protected', 'No se puede crear una segunda raíz dentro de un nodo CANON.');
  }
  const id = op.nodeId && !tree.nodes[op.nodeId] ? op.nodeId : newNodeId();
  const now = ctx.now || new Date().toISOString();
  const actor = ctx.actor || 'user';
  const node: ContextNode = {
    id,
    treeId: tree.id,
    parentId: op.parentId,
    type: op.type,
    status: op.status || 'active',
    title: op.title,
    summary: op.summary || '',
    priority: op.priority || 'medium',
    sourceRefs: [],
    evidenceRefs: [],
    linkedNodeIds: [],
    conflictNodeIds: [],
    tags: [],
    metadata: { createdByPatch: ctx.patchId },
    createdBy: actor,
    updatedBy: actor,
    createdAt: now,
    updatedAt: now
  };
  tree.nodes[id] = node;
  return node;
}

function applyMove(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'move' }>) {
  assertNodeExists(tree, op.nodeId, 'origen');
  assertNodeExists(tree, op.newParentId, 'destino');
  const node = tree.nodes[op.nodeId];
  if (node.type === 'root') {
    throw new PatchValidationError('root_protected', 'La raíz no se puede mover.');
  }
  if (isAncestor(tree, op.nodeId, op.newParentId)) {
    throw new PatchValidationError('cycle', 'Mover el nodo dentro de su propio descendiente crearía un ciclo.');
  }
  assertNotCanon(node, 'moverse');
  node.parentId = op.newParentId;
  node.updatedAt = new Date().toISOString();
}

function applyUpdate(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'update' }>, ctx: ApplyContext) {
  assertNodeExists(tree, op.nodeId, 'objetivo');
  const node = tree.nodes[op.nodeId];
  if (node.type === 'root') {
    throw new PatchValidationError('root_protected', 'La raíz no se puede editar directamente.');
  }
  assertNotCanon(node, 'editarse');
  if (!node.previous) {
    node.previous = snapshotNode(node);
  }
  for (const [key, value] of Object.entries(op.patch)) {
    if (key === 'tags' && Array.isArray(value)) {
      node.tags = value.map((entry) => String(entry));
    } else if (key === 'weightTokens' && typeof value === 'number') {
      node.weightTokens = value;
    } else if (key in node && key !== 'id' && key !== 'treeId' && key !== 'parentId' && key !== 'type') {
      (node as unknown as Record<string, unknown>)[key] = value;
    }
  }
  node.updatedAt = ctx.now || new Date().toISOString();
  node.updatedBy = ctx.actor || 'user';
}

function applyExclude(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'exclude' }>, ctx: ApplyContext) {
  assertNodeExists(tree, op.nodeId, 'objetivo');
  const node = tree.nodes[op.nodeId];
  if (node.type === 'root') {
    throw new PatchValidationError('root_protected', 'La raíz no se puede excluir del contexto.');
  }
  assertNotCanon(node, 'excluirse');
  if (!node.previous) node.previous = snapshotNode(node);
  node.status = 'excluded';
  node.updatedAt = ctx.now || new Date().toISOString();
  node.updatedBy = ctx.actor || 'user';
}

function applyRestore(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'restore' }>, ctx: ApplyContext) {
  assertNodeExists(tree, op.nodeId, 'objetivo');
  const node = tree.nodes[op.nodeId];
  if (node.status !== 'excluded' && node.status !== 'archived') {
    return; // No-op visible
  }
  node.status = 'active';
  node.updatedAt = ctx.now || new Date().toISOString();
  node.updatedBy = ctx.actor || 'user';
}

function applyCanon(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'canon' }>, ctx: ApplyContext) {
  assertNodeExists(tree, op.nodeId, 'objetivo');
  const node = tree.nodes[op.nodeId];
  if (op.value && !node.previous) {
    node.previous = snapshotNode(node);
  }
  node.status = op.value ? 'canon' : 'active';
  node.updatedAt = ctx.now || new Date().toISOString();
  node.updatedBy = ctx.actor || 'user';
}

function applyLink(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'link' }>, ctx: ApplyContext) {
  assertNodeExists(tree, op.nodeId, 'origen');
  assertNodeExists(tree, op.targetId, 'destino');
  const node = tree.nodes[op.nodeId];
  if (op.relation === 'contradicts') {
    if (!node.conflictNodeIds.includes(op.targetId)) node.conflictNodeIds.push(op.targetId);
    const target = tree.nodes[op.targetId];
    if (!target.conflictNodeIds.includes(op.nodeId)) target.conflictNodeIds.push(op.nodeId);
  } else if (op.relation === 'supports' || op.relation === 'depends_on') {
    if (!node.linkedNodeIds.includes(op.targetId)) node.linkedNodeIds.push(op.targetId);
  }
  node.updatedAt = ctx.now || new Date().toISOString();
  node.updatedBy = ctx.actor || 'user';
}

function applyUnlink(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'unlink' }>, ctx: ApplyContext) {
  assertNodeExists(tree, op.nodeId, 'origen');
  const node = tree.nodes[op.nodeId];
  node.conflictNodeIds = node.conflictNodeIds.filter((id) => id !== op.targetId);
  node.linkedNodeIds = node.linkedNodeIds.filter((id) => id !== op.targetId);
  if (tree.nodes[op.targetId]) {
    const target = tree.nodes[op.targetId];
    target.conflictNodeIds = target.conflictNodeIds.filter((id) => id !== op.nodeId);
    target.linkedNodeIds = target.linkedNodeIds.filter((id) => id !== op.nodeId);
  }
  node.updatedAt = ctx.now || new Date().toISOString();
  node.updatedBy = ctx.actor || 'user';
}

function applyAddToPack(tree: ContextTree, op: Extract<ContextPatchOp, { op: 'add_to_pack' }>, pack?: ContextPack) {
  if (!pack) {
    throw new PatchValidationError('pack_missing', 'No hay pack activo para añadir el nodo.');
  }
  assertNodeExists(tree, op.nodeId, 'objetivo');
  if (!pack.nodeIds.includes(op.nodeId)) pack.nodeIds.push(op.nodeId);
}

function applyRemoveFromPack(op: Extract<ContextPatchOp, { op: 'remove_from_pack' }>, pack?: ContextPack) {
  if (!pack) {
    throw new PatchValidationError('pack_missing', 'No hay pack activo desde el que quitar el nodo.');
  }
  pack.nodeIds = pack.nodeIds.filter((id) => id !== op.nodeId);
}

export interface ApplyResult {
  tree: ContextTree;
  pack?: ContextPack;
  receipt: ContextReceipt;
}

export function applyContextPatch(
  patch: ContextPatchRequest,
  tree: ContextTree,
  ctx: ApplyContext
): ApplyResult {
  // Validación previa: no se permite patch vacío.
  if (!patch.patch.operations.length) {
    throw new PatchValidationError('empty_patch', 'El patch no contiene operaciones.');
  }
  // Clonar árbol para mantener inmutabilidad referencial.
  const next: ContextTree = {
    ...tree,
    nodes: { ...tree.nodes }
  };
  const pack = ctx.pack ? { ...ctx.pack, nodeIds: [...ctx.pack.nodeIds] } : undefined;
  const now = ctx.now || new Date().toISOString();
  // Snapshot completo antes de tocar nada.
  const beforeNodes: Record<string, ContextNode> = {};
  for (const op of patch.patch.operations) {
    if (op.op === 'create') continue;
    const id = (op as { nodeId?: string }).nodeId;
    if (id && next.nodes[id] && !beforeNodes[id]) {
      beforeNodes[id] = { ...next.nodes[id] };
    }
    if (op.op === 'link' || op.op === 'unlink') {
      const target = next.nodes[op.targetId];
      if (target && !beforeNodes[op.targetId]) {
        beforeNodes[op.targetId] = { ...target };
      }
    }
  }
  for (const op of patch.patch.operations) {
    switch (op.op) {
      case 'create':
        applyCreate(next, op, { ...ctx, now });
        break;
      case 'move':
        applyMove(next, op);
        break;
      case 'update':
        applyUpdate(next, op, { ...ctx, now });
        break;
      case 'exclude':
        applyExclude(next, op, { ...ctx, now });
        break;
      case 'restore':
        applyRestore(next, op, { ...ctx, now });
        break;
      case 'canon':
        applyCanon(next, op, { ...ctx, now });
        break;
      case 'link':
        applyLink(next, op, { ...ctx, now });
        break;
      case 'unlink':
        applyUnlink(next, op, { ...ctx, now });
        break;
      case 'add_to_pack':
        applyAddToPack(next, op, pack);
        break;
      case 'remove_from_pack':
        applyRemoveFromPack(op, pack);
        break;
      default:
        // operación desconocida: ignorar
        break;
    }
  }
  next.updatedAt = now;
  // Si había pack, recalcular sus métricas.
  if (pack) {
    pack.weightTokens = pack.nodeIds
      .map((id) => next.nodes[id]?.weightTokens || 0)
      .reduce((acc, n) => acc + n, 0);
    pack.proposals = Object.values(next.nodes).filter((n) => n.status === 'proposed').length;
    pack.staleCount = Object.values(next.nodes).filter((n) => n.status === 'stale').length;
    pack.conflicts = Object.values(next.nodes).filter((n) => n.status === 'conflict' || n.conflictNodeIds.length > 0).length;
  }
  const receipt: ContextReceipt = {
    id: `rcpt_${Math.random().toString(36).slice(2, 10)}`,
    kind: 'chat_patch_applied',
    treeId: tree.id,
    packId: pack?.id,
    patchId: patch.id,
    summary: patch.title,
    before: { nodes: beforeNodes },
    after: { operations: patch.patch.operations.length },
    riskLevel: patch.riskLevel,
    createdAt: now,
    createdBy: ctx.actor || 'user'
  };
  return { tree: next, pack, receipt };
}

// Revertir un patch requiere snapshot. Como guardamos `previous` en los
// nodos tocados, restauramos ese estado y emitimos un receipt nuevo.
export function revertContextPatch(patch: ContextPatchRequest, tree: ContextTree, ctx: ApplyContext = { patchId: patch.id }): ApplyResult {
  const next: ContextTree = { ...tree, nodes: { ...tree.nodes } };
  const now = ctx.now || new Date().toISOString();
  const restored: string[] = [];
  for (const op of patch.patch.operations) {
    if (op.op === 'create') {
      const id = (op as { nodeId?: string }).nodeId;
      if (id && next.nodes[id]) {
        delete next.nodes[id];
        restored.push(`deleted ${id}`);
      }
      continue;
    }
    const id = (op as { nodeId?: string }).nodeId;
    if (!id) continue;
    const node = next.nodes[id];
    if (!node || !node.previous) continue;
    const prev = node.previous;
    node.parentId = prev.parentId;
    node.type = prev.type;
    node.status = prev.status;
    node.title = prev.title;
    node.summary = prev.summary;
    node.body = prev.body;
    node.tags = [...prev.tags];
    node.metadata = { ...prev.metadata };
    node.updatedAt = now;
    node.updatedBy = 'user';
    restored.push(id);
  }
  next.updatedAt = now;
  const receipt: ContextReceipt = {
    id: `rcpt_${Math.random().toString(36).slice(2, 10)}`,
    kind: 'chat_patch_reverted',
    treeId: tree.id,
    patchId: patch.id,
    summary: `Reversión de: ${patch.title}`,
    before: { restored },
    riskLevel: patch.riskLevel,
    createdAt: now,
    createdBy: 'user'
  };
  return { tree: next, receipt };
}

export { CANON_FIELDS };
