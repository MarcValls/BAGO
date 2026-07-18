// Tipos del ContextTreeModule. Define la forma del árbol, los nodos,
// los packs, las propuestas de patch del Chat y los receipts.
//
// Se mantiene 100% en el frontend porque el MVP no crea endpoints
// nuevos: persistimos en archivos dentro de .bago/context/ vía
// /files/read y /files/write (ver contextTreeApi.ts).

export type ContextNodeType =
  | 'root'
  | 'intent'
  | 'source'
  | 'file'
  | 'decision'
  | 'rule'
  | 'claim'
  | 'risk'
  | 'pending'
  | 'evidence'
  | 'proposal'
  | 'pack'
  | 'note';

export type ContextNodeStatus =
  | 'active'
  | 'proposed'
  | 'excluded'
  | 'archived'
  | 'canon'
  | 'conflict'
  | 'stale';

export type ContextNodePriority = 'low' | 'medium' | 'high' | 'critical';

export type ContextNodeAuthor = 'user' | 'chat' | 'system';

export interface ContextSourceRef {
  kind:
    | 'workspace_file'
    | 'workspace_directory'
    | 'chat_turn'
    | 'pipeline_step'
    | 'manual'
    | 'evidence'
    | 'memory'
    | 'history'
    | 'interpret_rule'
    | 'project_status';
  path?: string;
  id?: string;
  label?: string;
  origin?: string;
}

export interface ContextNode {
  id: string;
  treeId: string;
  parentId: string | null;
  type: ContextNodeType;
  status: ContextNodeStatus;
  title: string;
  summary: string;
  body?: string;
  priority: ContextNodePriority;
  weightTokens?: number;
  sourceRefs: ContextSourceRef[];
  evidenceRefs: string[];
  linkedNodeIds: string[];
  conflictNodeIds: string[];
  tags: string[];
  metadata: Record<string, unknown>;
  createdBy: ContextNodeAuthor;
  updatedBy: ContextNodeAuthor;
  createdAt: string;
  updatedAt: string;
  // Snapshot para revert. Solo presente en nodos que el chat ha modificado
  // bajo validación. Se mantiene dentro del nodo por simplicidad en MVP.
  previous?: Pick<ContextNode, 'parentId' | 'type' | 'status' | 'title' | 'summary' | 'body' | 'tags' | 'metadata'> | null;
}

export interface ContextTree {
  id: string;
  name: string;
  archived: boolean;
  createdAt: string;
  updatedAt: string;
  rootId: string;
  nodes: Record<string, ContextNode>;
}

export type ContextPackStatus = 'draft' | 'valid' | 'warning' | 'blocked' | 'compiled';

export interface ContextPack {
  id: string;
  treeId: string;
  name: string;
  status: ContextPackStatus;
  nodeIds: string[];
  weightTokens: number;
  conflicts: number;
  proposals: number;
  staleCount: number;
  compiledAt?: string;
  markdown?: string;
  notes?: string;
}

export type ContextPatchRisk = 'low' | 'medium' | 'high' | 'critical';

export type ContextPatchOp =
  | { op: 'create'; nodeId: string; parentId: string; type: ContextNodeType; title: string; summary?: string; status?: ContextNodeStatus; priority?: ContextNodePriority }
  | { op: 'move'; nodeId: string; newParentId: string }
  | { op: 'update'; nodeId: string; patch: Partial<Pick<ContextNode, 'title' | 'summary' | 'body' | 'status' | 'tags' | 'priority' | 'weightTokens'>> }
  | { op: 'exclude'; nodeId: string }
  | { op: 'restore'; nodeId: string }
  | { op: 'canon'; nodeId: string; value: boolean }
  | { op: 'link'; nodeId: string; targetId: string; relation: 'supports' | 'contradicts' | 'depends_on' }
  | { op: 'unlink'; nodeId: string; targetId: string }
  | { op: 'add_to_pack'; nodeId: string; packId: string }
  | { op: 'remove_from_pack'; nodeId: string; packId: string };

export interface ContextPatchRequest {
  id: string;
  treeId: string;
  validationMode: 'inline' | 'modal';
  proposalType: string;
  title: string;
  reason: string;
  riskLevel: ContextPatchRisk;
  targetNodeId?: string;
  patch: { operations: ContextPatchOp[] };
  createdAt: string;
  createdBy: 'chat' | 'user' | 'system';
  // Estado del flujo de validación.
  status: 'pending' | 'accepted' | 'rejected' | 'edited' | 'failed' | 'reverted' | 'review_requested';
  appliedAt?: string;
  rejectedAt?: string;
  errorMessage?: string;
  receiptId?: string;
  // Edición opcional del usuario antes de aplicar.
  editedPatch?: ContextPatchRequest['patch'];
}

export interface ContextReceipt {
  id: string;
  kind: 'chat_patch_applied' | 'chat_patch_rejected' | 'chat_patch_reverted' | 'tree_mutation' | 'pack_compiled' | 'pack_sent' | 'node_added' | 'node_excluded' | 'node_canon' | 'node_stale';
  treeId?: string;
  packId?: string;
  nodeId?: string;
  patchId?: string;
  summary: string;
  before?: unknown;
  after?: unknown;
  riskLevel?: ContextPatchRisk;
  createdAt: string;
  createdBy: ContextNodeAuthor;
}

// Piezas que se pueden arrastrar al árbol desde el Banco contextual.
export type ContextBankItemKind =
  | 'workspace_file'
  | 'workspace_directory'
  | 'source_root'
  | 'claim'
  | 'risk'
  | 'pending'
  | 'receipt'
  | 'memory'
  | 'history'
  | 'rule'
  | 'project_status'
  | 'manual';

export interface ContextBankItem {
  id: string;
  kind: ContextBankItemKind;
  title: string;
  origin: string;
  path?: string;
  tags?: string[];
  weightTokens?: number;
  usedInTree?: boolean;
  usedInNodeId?: string;
  raw?: Record<string, unknown>;
  // Sugerencia de rama donde se añade por defecto al doble click.
  suggestedBranch: ContextNodeType;
}

// CANON[CTX-023]: Gestión de directorios fuente. Un usuario puede
// vincular un directorio (ej. D:\docs\mi-proyecto) y luego decidir
// qué archivos de ese directorio quiere incluir en el árbol de
// contexto y a qué rama asignarlos.
export interface SourceDirectoryFile {
  path: string;
  title: string;
  include: boolean;
  branch: ContextNodeType;
  language?: string;
  size?: number;
}

export interface SourceDirectory {
  id: string;
  path: string;
  title: string;
  kind: 'directory' | 'file';
  files: SourceDirectoryFile[];
  createdAt: string;
  updatedAt: string;
}

export interface ContextCompiledPack {
  id: string;
  packId: string;
  markdown: string;
  nodeCount: number;
  weightTokens: number;
  conflicts: number;
  proposals: number;
  staleCount: number;
  generatedAt: string;
}

export interface ContextBankSnapshot {
  files: ContextBankItem[];
  sources: ContextBankItem[];
  claims: ContextBankItem[];
  receipts: ContextBankItem[];
  memory: ContextBankItem[];
  history: ContextBankItem[];
  rules: ContextBankItem[];
  project: ContextBankItem[];
  manual: ContextBankItem[];
  errors: string[];
}
