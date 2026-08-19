// Hook central del ContextTreeModule. Carga, persiste y mantiene
// árbol, packs, propuestas y receipts. Ofrece acciones de alto nivel
// (compilar pack, enviar a chat, aceptar/rechazar/editar patch, etc.)
// para que los componentes solo tengan que llamar funciones.
import { useEffect, useMemo, useRef, useState } from 'react';
import type { BagoClient } from '@/api/client';
import { friendlyErrorMessage } from '@/shared/friendly-error';
import type { BackendStatus } from '@/contracts/backend';
import type {
  ContextBankItem,
  ContextBankSnapshot,
  ContextCompiledPack,
  ContextNode,
  ContextPack,
  ContextPatchRequest,
  ContextReceipt,
  ContextTree,
  ContextNodeType,
  SourceDirectory
} from './contextTreeTypes';
import {
  buildDefaultPack,
  buildDefaultTree,
  detectLanguageFromName,
  loadContextBank,
  loadContextBankManual,
  loadContextPacks,
  loadContextPatchRequests,
  loadContextReceipts,
  loadContextTree,
  loadSourceDirectories,
  saveContextBankManual,
  saveContextPacks,
  saveContextPatchRequests,
  saveContextTree,
  saveSourceDirectories,
  sendCompiledContextToChat,
  appendContextReceipt
} from './contextTreeApi';
import { applyContextPatch, revertContextPatch, PatchValidationError } from './applyContextPatch';
import { classifyPatchRisk, worstRisk } from './classifyContextPatchRisk';
import { compileContextPack } from './compileContextPack';
import { contextNodeTypeForBankItem, contextSourceKindForBankItem } from './contextBankMapping';

export interface UseContextTreeState {
  ready: boolean;
  error: string | null;
  loading: boolean;
  tree: ContextTree | null;
  packs: ContextPack[];
  activePack: ContextPack | null;
  proposals: ContextPatchRequest[];
  receipts: ContextReceipt[];
  bank: ContextBankSnapshot;
  bankLoading: boolean;
  // CANON[CTX-019]: identificador del workspace al que pertenece el
  // estado actual (tree, packs, bank). Sirve para que el llamador
  // sepa cuándo recargar todo al cambiar de proyecto.
  workspaceKey: string | null;
  // acciones
  refresh: () => Promise<void>;
  refreshBank: () => Promise<void>;
  createDefaultTree: () => Promise<void>;
  renameTree: (name: string) => Promise<void>;
  archiveTree: () => Promise<void>;
  createPack: (name?: string) => Promise<ContextPack | null>;
  renamePack: (packId: string, name: string) => Promise<void>;
  setActivePack: (packId: string) => void;
  toggleNodeInPack: (nodeId: string) => Promise<void>;
  compileActivePack: () => Promise<ContextCompiledPack | null>;
  sendActivePackToChat: (extra?: string) => Promise<{ ok: boolean; message?: string }>;
  // mutaciones de nodo
  createNode: (input: { parentId: string; type: ContextNode['type']; title: string; summary?: string; status?: ContextNode['status']; priority?: ContextNode['priority']; sourceRefs?: ContextNode['sourceRefs'] }) => Promise<ContextNode | null>;
  updateNode: (nodeId: string, patch: Partial<ContextNode>) => Promise<void>;
  closeTask: (nodeId: string, conclusion: string) => Promise<{ ok: boolean; error?: string }>;
  reopenTask: (nodeId: string) => Promise<{ ok: boolean; error?: string }>;
  moveNode: (nodeId: string, newParentId: string) => Promise<void>;
  excludeNode: (nodeId: string) => Promise<void>;
  restoreNode: (nodeId: string) => Promise<void>;
  toggleCanon: (nodeId: string) => Promise<void>;
  addBankItemToTree: (item: ContextBankItem, parentId?: string) => Promise<ContextNode | null>;
  // CANON[CTX-022]: gestión de items manuales del Banco. Permiten
  // añadir paths explícitos (archivos o directorios) que el usuario
  // quiere vincular al árbol pero que no aparecen en `/files/list`.
  addManualBankItem: (path: string, kind: 'source_root' | 'workspace_file' | 'workspace_directory', title?: string) => Promise<ContextBankItem | null>;
  removeManualBankItem: (itemId: string) => Promise<void>;
  // CANON[CTX-023]: gestión de directorios fuente. El usuario vincula
  // un directorio, ve sus archivos, decide cuáles incluir y a qué
  // rama del árbol asignarlos.
  sourceDirectories: SourceDirectory[];
  sourceDirectoriesLoading: boolean;
  addSourceDirectory: (path: string, title?: string) => Promise<SourceDirectory | null>;
  removeSourceDirectory: (id: string) => Promise<void>;
  refreshSourceDirectoryFiles: (id: string) => Promise<void>;
  toggleSourceFileInclude: (id: string, filePath: string, include: boolean) => Promise<void>;
  setSourceFileBranch: (id: string, filePath: string, branch: ContextNodeType) => Promise<void>;
  linkSourceDirectoryToTree: (id: string) => Promise<ContextNode[]>;
  // patches del chat
  ingestPatch: (request: ContextPatchRequest) => void;
  createProposal: (request: ContextPatchRequest) => Promise<void>;
  acceptPatch: (patchId: string) => Promise<{ ok: boolean; error?: string }>;
  rejectPatch: (patchId: string) => Promise<void>;
  applyPatchedEdited: (patchId: string, editedOperations: ContextPatchRequest['patch']['operations']) => Promise<{ ok: boolean; error?: string }>;
  revertPatch: (patchId: string) => Promise<{ ok: boolean; error?: string }>;
}

function emptyBank(): ContextBankSnapshot {
  return {
    files: [], sources: [], claims: [], receipts: [],
    memory: [], history: [], rules: [], project: [],
    manual: [],
    errors: []
  };
}

export function deriveWorkspaceKey(status: Pick<BackendStatus, 'workspace_id' | 'workspace_state_root' | 'workspace_scope_root' | 'project_root' | 'repo_root'> | null | undefined): string | null {
  if (!status) return null;
  const candidates = [
    status.workspace_id,
    status.workspace_state_root,
    status.workspace_scope_root,
    status.project_root,
    status.repo_root
  ];
  const key = candidates.map((value) => String(value || '').trim()).find((value) => Boolean(value));
  return key || null;
}

export function shouldResetWorkspaceState(previousKey: string | null, nextKey: string | null): boolean {
  return Boolean(previousKey && nextKey && previousKey !== nextKey);
}

export function useContextTree(client: BagoClient | null): UseContextTreeState {
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tree, setTree] = useState<ContextTree | null>(null);
  const [packs, setPacks] = useState<ContextPack[]>([]);
  const [activePackId, setActivePackId] = useState<string | null>(null);
  const [proposals, setProposals] = useState<ContextPatchRequest[]>([]);
  const [receipts, setReceipts] = useState<ContextReceipt[]>([]);
  const [bank, setBank] = useState<ContextBankSnapshot>(emptyBank());
  const [bankLoading, setBankLoading] = useState(false);
  const [sourceDirectories, setSourceDirectories] = useState<SourceDirectory[]>([]);
  const [sourceDirectoriesLoading, setSourceDirectoriesLoading] = useState(false);
  const [workspaceKey, setWorkspaceKey] = useState<string | null>(null);
  const initialLoadRan = useRef(false);
  const lastWorkspaceKeyRef = useRef<string | null>(null);

  const resetWorkspaceState = () => {
    setTree(null);
    setPacks([]);
    setActivePackId(null);
    setProposals([]);
    setReceipts([]);
    setBank(emptyBank());
    setSourceDirectories([]);
    setSourceDirectoriesLoading(false);
    setBankLoading(false);
    setLoading(false);
    setReady(false);
    setError(null);
  };

  const persistTree = async (next: ContextTree) => {
    if (!client) return;
    try {
      await saveContextTree(client, next);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  const persistPacks = async (next: ContextPack[]) => {
    if (!client) return;
    try {
      await saveContextPacks(client, next);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  const persistProposals = async (next: ContextPatchRequest[]) => {
    if (!client) return;
    try {
      await saveContextPatchRequests(client, next);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  const appendReceipt = async (receipt: ContextReceipt) => {
    if (!client) return;
    try {
      await appendContextReceipt(client, receipt);
      setReceipts((current) => [receipt, ...current].slice(0, 200));
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  const refresh = async () => {
    if (!client) return;
    setLoading(true);
    setError(null);
    try {
      const status = await client.getStatus().catch(() => null);
      const nextWorkspaceKey = deriveWorkspaceKey(status);
      const previousWorkspaceKey = lastWorkspaceKeyRef.current;
      if (shouldResetWorkspaceState(previousWorkspaceKey, nextWorkspaceKey)) {
        resetWorkspaceState();
      }
      lastWorkspaceKeyRef.current = nextWorkspaceKey;
      setWorkspaceKey(nextWorkspaceKey);
      const [loadedTree, loadedPacks, loadedProposals, loadedReceipts] = await Promise.all([
        loadContextTree(client),
        loadContextPacks(client),
        loadContextPatchRequests(client),
        loadContextReceipts(client)
      ]);
      let nextTree = loadedTree;
      if (!nextTree) {
        nextTree = buildDefaultTree();
        await saveContextTree(client, nextTree);
      }
      let nextPacks = loadedPacks;
      if (nextPacks.length === 0) {
        nextPacks = [buildDefaultPack(nextTree)];
        await saveContextPacks(client, nextPacks);
      }
      setTree(nextTree);
      setPacks(nextPacks);
      setProposals(loadedProposals);
      setReceipts(loadedReceipts);
      await refreshSourceDirectories();
      if (loadedPacks[0] && !activePackId) {
        setActivePackId(loadedPacks[0].id);
      }
    } catch (e) {
      setError(friendlyErrorMessage(e));
    } finally {
      setLoading(false);
      setReady(true);
    }
  };

  const refreshBank = async () => {
    if (!client) return;
    setBankLoading(true);
    try {
      const snap = await loadContextBank(client);
      setBank(snap);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    } finally {
      setBankLoading(false);
    }
  };

  // CANON[CTX-023]: gestión de directorios fuente. Carga la lista
  // persistida y permite alta, baja, listado de archivos y vínculo al
  // árbol. Los archivos se listan desde el mirror del workspace
  // filtrando por prefijo del path que el usuario añadió.
  const refreshSourceDirectories = async () => {
    if (!client) return;
    setSourceDirectoriesLoading(true);
    try {
      const list = await loadSourceDirectories(client);
      setSourceDirectories(Array.isArray(list) ? list : []);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    } finally {
      setSourceDirectoriesLoading(false);
    }
  };

  const listFilesForDirectory = async (path: string): Promise<Array<{ path: string; name: string; type: string; size?: number }>> => {
    if (!client) return [];
    try {
      const payload = await client.listFiles();
      const entries = (Array.isArray(payload) ? payload : (payload.entries || payload.files || [])) as Array<Record<string, unknown>>;
      const lowerPath = String(path || '').toLowerCase().replace(/\\/g, '/').replace(/\/$/, '');
      const out: Array<{ path: string; name: string; type: string; size?: number }> = [];
      for (const entry of entries) {
        const p = String(entry.path || '').toLowerCase().replace(/\\/g, '/');
        if (lowerPath && !p.startsWith(lowerPath + '/') && p !== lowerPath) continue;
        const type = String(entry.type || '').toLowerCase();
        if (type === 'directory' || type === 'dir' || type === 'folder') continue;
        out.push({
          path: String(entry.path || ''),
          name: String(entry.name || String(entry.path || '').split('/').pop() || ''),
          type,
          size: entry.size as number | undefined
        });
      }
      return out;
    } catch {
      return [];
    }
  };

  const addSourceDirectory = async (path: string, title?: string): Promise<SourceDirectory | null> => {
    if (!client) return null;
    const cleanPath = String(path || '').trim();
    if (!cleanPath) return null;
    const stamp = new Date().toISOString();
    const dirEntry: SourceDirectory = {
      id: `dir:${cleanPath}`,
      path: cleanPath,
      title: String(title || '').trim() || (cleanPath.split(/[\\/]/).filter(Boolean).pop() || cleanPath),
      kind: 'directory',
      files: [],
      createdAt: stamp,
      updatedAt: stamp
    };
    try {
      const current = await loadSourceDirectories(client);
      const safeCurrent = Array.isArray(current) ? current : [];
      const filtered = safeCurrent.filter((d) => d.id !== dirEntry.id);
      filtered.unshift(dirEntry);
      await saveSourceDirectories(client, filtered);
      setSourceDirectories(filtered);
      // Listar archivos inmediatamente
      const files = await listFilesForDirectory(cleanPath);
      const withFiles: SourceDirectory = {
        ...dirEntry,
        files: files.map((f) => ({
          path: f.path,
          title: f.name,
          include: true,
          branch: 'source' as ContextNodeType,
          language: detectLanguageFromName(f.name),
          size: f.size
        }))
      };
      const after = filtered.map((d) => d.id === dirEntry.id ? withFiles : d);
      await saveSourceDirectories(client, after);
      setSourceDirectories(after);
      return withFiles;
    } catch (e) {
      setError(friendlyErrorMessage(e));
      return null;
    }
  };

  const removeSourceDirectory = async (id: string) => {
    if (!client) return;
    try {
      const current = await loadSourceDirectories(client);
      const safeCurrent = Array.isArray(current) ? current : [];
      const next = safeCurrent.filter((d) => d.id !== id);
      await saveSourceDirectories(client, next);
      setSourceDirectories(next);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  const refreshSourceDirectoryFiles = async (id: string) => {
    if (!client) return;
    const current = sourceDirectories.find((d) => d.id === id);
    if (!current) return;
    try {
      const files = await listFilesForDirectory(current.path);
      const updated: SourceDirectory = {
        ...current,
        files: files.map((f) => {
          const existing = current.files.find((cf) => cf.path === f.path);
          return {
            path: f.path,
            title: f.name,
            include: existing ? existing.include : true,
            branch: existing ? existing.branch : 'source',
            language: detectLanguageFromName(f.name),
            size: f.size
          };
        }),
        updatedAt: new Date().toISOString()
      };
      const next = sourceDirectories.map((d) => d.id === id ? updated : d);
      await saveSourceDirectories(client, next);
      setSourceDirectories(next);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  const toggleSourceFileInclude = async (id: string, filePath: string, include: boolean) => {
    if (!client) return;
    const next = sourceDirectories.map((d) => {
      if (d.id !== id) return d;
      return {
        ...d,
        files: d.files.map((f) => f.path === filePath ? { ...f, include } : f),
        updatedAt: new Date().toISOString()
      };
    });
    setSourceDirectories(next);
    try {
      await saveSourceDirectories(client, next);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  const setSourceFileBranch = async (id: string, filePath: string, branch: ContextNodeType) => {
    if (!client) return;
    const next = sourceDirectories.map((d) => {
      if (d.id !== id) return d;
      return {
        ...d,
        files: d.files.map((f) => f.path === filePath ? { ...f, branch, include: true } : f),
        updatedAt: new Date().toISOString()
      };
    });
    setSourceDirectories(next);
    try {
      await saveSourceDirectories(client, next);
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  useEffect(() => {
    if (initialLoadRan.current) return;
    initialLoadRan.current = true;
    void refresh();
    void refreshBank();
  }, [refresh, refreshBank]);

  const activePack = useMemo(() => {
    if (!packs.length) return null;
    if (activePackId) return packs.find((p) => p.id === activePackId) || packs[0] || null;
    return packs[0] || null;
  }, [packs, activePackId]);

  // Métricas calculadas en el árbol.
  const treeMetrics = useMemo(() => {
    if (!tree) return { active: 0, proposed: 0, conflicts: 0, stale: 0, canon: 0 };
    const nodes = Object.values(tree.nodes);
    return {
      active: nodes.filter((n) => n.status === 'active').length,
      proposed: nodes.filter((n) => n.status === 'proposed').length,
      conflicts: nodes.filter((n) => n.status === 'conflict' || n.conflictNodeIds.length > 0).length,
      stale: nodes.filter((n) => n.status === 'stale').length,
      canon: nodes.filter((n) => n.status === 'canon').length
    };
  }, [tree]);

  // Handlers ------------------------------------------------------------
  const createDefaultTree = async () => {
    if (!client) return;
    const next = buildDefaultTree();
    setTree(next);
    await persistTree(next);
  };

  const renameTree = async (name: string) => {
    if (!tree) return;
    const next = { ...tree, name, updatedAt: new Date().toISOString() };
    setTree(next);
    await persistTree(next);
  };

  const archiveTree = async () => {
    if (!tree) return;
    const next = { ...tree, archived: true, updatedAt: new Date().toISOString() };
    setTree(next);
    await persistTree(next);
  };

  const createPack = async (name?: string) => {
    if (!client || !tree) return null;
    const pack: ContextPack = {
      id: `pack_${Math.random().toString(36).slice(2, 10)}`,
      treeId: tree.id,
      name: name || `Pack ${new Date().toLocaleTimeString()}`,
      status: 'draft',
      nodeIds: [],
      weightTokens: 0,
      conflicts: 0,
      proposals: 0,
      staleCount: 0
    };
    const next = [...packs, pack];
    setPacks(next);
    setActivePackId(pack.id);
    await persistPacks(next);
    return pack;
  };

  const renamePack = async (packId: string, name: string) => {
    const next = packs.map((p) => p.id === packId ? { ...p, name } : p);
    setPacks(next);
    await persistPacks(next);
  };

  const setActivePack = (packId: string) => {
    setActivePackId(packId);
  };

  const toggleNodeInPack = async (nodeId: string) => {
    if (!activePack) return;
    const nextPack = {
      ...activePack,
      nodeIds: activePack.nodeIds.includes(nodeId)
        ? activePack.nodeIds.filter((id) => id !== nodeId)
        : [...activePack.nodeIds, nodeId]
    };
    const nextPacks = packs.map((p) => p.id === activePack.id ? nextPack : p);
    setPacks(nextPacks);
    await persistPacks(nextPacks);
  };

  const compileActivePack = async () => {
    if (!tree || !activePack) return null;
    const compiled = compileContextPack(tree, activePack);
    const nextPack: ContextPack = {
      ...activePack,
      status: compiled.conflicts || compiled.staleCount ? 'warning' : 'compiled',
      weightTokens: compiled.weightTokens,
      conflicts: compiled.conflicts,
      proposals: compiled.proposals,
      staleCount: compiled.staleCount,
      compiledAt: compiled.generatedAt,
      markdown: compiled.markdown
    };
    const nextPacks = packs.map((p) => p.id === nextPack.id ? nextPack : p);
    setPacks(nextPacks);
    await persistPacks(nextPacks);
    await appendReceipt({
      id: `rcpt_${Math.random().toString(36).slice(2, 10)}`,
      kind: 'pack_compiled',
      treeId: tree.id,
      packId: nextPack.id,
      summary: `Pack ${nextPack.name} compilado · ${nextPack.weightTokens}t · ${nextPack.nodeIds.length} nodos`,
      after: { weightTokens: nextPack.weightTokens, nodeCount: nextPack.nodeIds.length },
      createdAt: new Date().toISOString(),
      createdBy: 'user'
    });
    return compiled;
  };

  const sendActivePackToChat = async (extra?: string) => {
    if (!client || !tree || !activePack || !activePack.markdown) {
      return { ok: false, message: 'El pack activo todavía no está compilado.' };
    }
    const result = await sendCompiledContextToChat(client, activePack, activePack.markdown, extra);
    await appendReceipt({
      id: `rcpt_${Math.random().toString(36).slice(2, 10)}`,
      kind: 'pack_sent',
      treeId: tree.id,
      packId: activePack.id,
      summary: result.ok ? `Pack ${activePack.name} enviado al chat.` : `Fallo al enviar: ${result.message}`,
      riskLevel: 'medium',
      createdAt: new Date().toISOString(),
      createdBy: 'user'
    });
    return result;
  };

  const createNode = async (input: { parentId: string; type: ContextNode['type']; title: string; summary?: string; status?: ContextNode['status']; priority?: ContextNode['priority']; sourceRefs?: ContextNode['sourceRefs'] }): Promise<ContextNode | null> => {
    if (!tree) return null;
    const id = `node_${Math.random().toString(36).slice(2, 10)}`;
    const now = new Date().toISOString();
    const node: ContextNode = {
      id,
      treeId: tree.id,
      parentId: input.parentId,
      type: input.type,
      status: input.status || 'active',
      title: input.title,
      summary: input.summary || '',
      priority: input.priority || 'medium',
      sourceRefs: input.sourceRefs || [],
      evidenceRefs: [],
      linkedNodeIds: [],
      conflictNodeIds: [],
      tags: [],
      metadata: {},
      createdBy: 'user',
      updatedBy: 'user',
      createdAt: now,
      updatedAt: now
    };
    const next: ContextTree = {
      ...tree,
      nodes: { ...tree.nodes, [id]: node },
      updatedAt: now
    };
    setTree(next);
    await persistTree(next);
    await appendReceipt({
      id: `rcpt_${Math.random().toString(36).slice(2, 10)}`,
      kind: 'node_added',
      treeId: tree.id,
      nodeId: id,
      summary: `Nodo creado: ${node.title}`,
      after: node,
      createdAt: now,
      createdBy: 'user'
    });
    return node;
  };

  const updateNode = async (nodeId: string, patch: Partial<ContextNode>) => {
    if (!tree) return;
    const current = tree.nodes[nodeId];
    if (!current) return;
    if (current.status === 'canon' && (patch.status || patch.title || patch.summary || patch.body || patch.tags)) {
      // No permitir edición directa de CANON. Forzar vía patch.
      return;
    }
    const next: ContextTree = {
      ...tree,
      nodes: {
        ...tree.nodes,
        [nodeId]: { ...current, ...patch, updatedAt: new Date().toISOString(), updatedBy: 'user' }
      },
      updatedAt: new Date().toISOString()
    };
    setTree(next);
    await persistTree(next);
  };

  const closeTask = async (nodeId: string, conclusion: string) => {
    if (!tree) return { ok: false, error: 'No hay árbol activo.' };
    const current = tree.nodes[nodeId];
    if (!current) return { ok: false, error: 'Rama no encontrada.' };
    const now = new Date().toISOString();
    const nextNode = { ...current, status: 'canon' as const, summary: conclusion.trim(), updatedAt: now, updatedBy: 'user' as const };
    const nextTree = { ...tree, nodes: { ...tree.nodes, [nodeId]: nextNode }, updatedAt: now };
    setTree(nextTree);
    await persistTree(nextTree);
    await appendReceipt({ id: `rcpt_${Math.random().toString(36).slice(2, 10)}`, kind: 'node_canon', treeId: tree.id, nodeId, summary: `Tarea cerrada: ${current.title}`, before: { status: current.status }, after: { status: 'canon', conclusion: conclusion.trim() }, createdAt: now, createdBy: 'user' });
    return { ok: true };
  };

  const reopenTask = async (nodeId: string) => {
    if (!tree) return { ok: false, error: 'No hay árbol activo.' };
    const current = tree.nodes[nodeId];
    if (!current) return { ok: false, error: 'Rama no encontrada.' };
    const now = new Date().toISOString();
    const nextTree = { ...tree, nodes: { ...tree.nodes, [nodeId]: { ...current, status: 'active' as const, updatedAt: now, updatedBy: 'user' as const } }, updatedAt: now };
    setTree(nextTree);
    await persistTree(nextTree);
    await appendReceipt({ id: `rcpt_${Math.random().toString(36).slice(2, 10)}`, kind: 'tree_mutation', treeId: tree.id, nodeId, summary: `Tarea reabierta: ${current.title}`, before: { status: current.status }, after: { status: 'active' }, createdAt: now, createdBy: 'user' });
    return { ok: true };
  };

  const moveNode = async (nodeId: string, newParentId: string) => {
    await updateNode(nodeId, { parentId: newParentId });
  };

  const excludeNode = async (nodeId: string) => {
    await updateNode(nodeId, { status: 'excluded' });
  };

  const restoreNode = async (nodeId: string) => {
    await updateNode(nodeId, { status: 'active' });
  };

  const toggleCanon = async (nodeId: string) => {
    if (!tree) return;
    const current = tree.nodes[nodeId];
    if (!current) return;
    const nextStatus = current.status === 'canon' ? 'active' : 'canon';
    const next: ContextTree = {
      ...tree,
      nodes: {
        ...tree.nodes,
        [nodeId]: { ...current, status: nextStatus, updatedAt: new Date().toISOString(), updatedBy: 'user' }
      },
      updatedAt: new Date().toISOString()
    };
    setTree(next);
    await persistTree(next);
    await appendReceipt({
      id: `rcpt_${Math.random().toString(36).slice(2, 10)}`,
      kind: nextStatus === 'canon' ? 'node_canon' : 'tree_mutation',
      treeId: tree.id,
      nodeId,
      summary: nextStatus === 'canon' ? `Nodo marcado como CANON: ${current.title}` : `CANON retirado: ${current.title}`,
      before: { status: current.status },
      after: { status: nextStatus },
      riskLevel: 'high',
      createdAt: new Date().toISOString(),
      createdBy: 'user'
    });
  };

  // CANON[CTX-023]: vincular un directorio fuente al árbol. Crea un
  // nodo `file` por cada archivo activo y lo mueve a la rama del
  // árbol que el usuario eligió (intent/source/decision/rule/etc.).
  const linkSourceDirectoryToTree = async (id: string): Promise<ContextNode[]> => {
    const dir = sourceDirectories.find((d) => d.id === id);
    if (!dir || !tree) return [];
    const created: ContextNode[] = [];
    for (const file of dir.files) {
      if (!file.include) continue;
      const result = await createNode({
        parentId: tree.rootId,
        type: 'file',
        title: file.title,
        summary: file.path,
        priority: 'medium',
        sourceRefs: [{ kind: 'workspace_file', path: file.path, origin: 'source_directory' }]
      });
      if (result) {
        created.push(result);
        if (file.branch !== 'file') {
          const branch = Object.values(tree.nodes).find((n) => n.type === file.branch && n.parentId === tree.rootId);
          if (branch) {
            try {
              await moveNode(result.id, branch.id);
            } catch {
              // Si no se puede mover, queda en root. No es crítico.
            }
          }
        }
      }
    }
    return created;
  };

  const addBankItemToTree = async (item: ContextBankItem, parentId?: string) => {
    if (!tree) return null;
    const branchType = item.suggestedBranch;
    const branch = Object.values(tree.nodes).find((n) => n.type === branchType && n.parentId === tree.rootId);
    const targetParent = parentId || branch?.id || tree.rootId;
    const type = contextNodeTypeForBankItem(item.kind);
    return createNode({
      parentId: targetParent,
      type,
      title: item.title,
      summary: `${item.origin}${item.path ? ` · ${item.path}` : ''}`,
      priority: 'medium',
      sourceRefs: [{
        kind: contextSourceKindForBankItem(item.kind),
        path: item.path,
        origin: item.origin
      }]
    });
  };

  // CANON[CTX-022]: alta y baja de items manuales del Banco. El usuario
  // introduce un path explícito (archivo o directorio) y se persiste
  // en `.bago/context/context-bank-manual.json` para sobrevivir
  // recargas. El doble-click lo añade al árbol como nodo `source`.
  const addManualBankItem = async (
    path: string,
    kind: 'source_root' | 'workspace_file' | 'workspace_directory',
    title?: string
  ): Promise<ContextBankItem | null> => {
    if (!client) return null;
    const cleanPath = String(path || '').trim();
    if (!cleanPath) return null;
    const normalizedKind: ContextBankItem['kind'] = kind;
    const titleClean = String(title || '').trim() || (cleanPath.split(/[\\/]/).filter(Boolean).pop() || cleanPath);
    const item: ContextBankItem = {
      id: `manual:${cleanPath}`,
      kind: normalizedKind,
      title: titleClean,
      origin: 'manual',
      path: cleanPath,
      tags: ['añadido'],
      suggestedBranch: 'source'
    };
    try {
      const current = await loadContextBankManual(client);
      const filtered = current.filter((existing) => existing.id !== item.id);
      filtered.unshift(item);
      await saveContextBankManual(client, filtered);
      setBank((snapshot) => ({
        ...snapshot,
        manual: [item, ...snapshot.manual.filter((existing) => existing.id !== item.id)]
      }));
      return item;
    } catch (e) {
      setError(friendlyErrorMessage(e));
      return null;
    }
  };

  const removeManualBankItem = async (itemId: string): Promise<void> => {
    if (!client) return;
    try {
      const current = await loadContextBankManual(client);
      const next = current.filter((existing) => existing.id !== itemId);
      await saveContextBankManual(client, next);
      setBank((snapshot) => ({
        ...snapshot,
        manual: snapshot.manual.filter((existing) => existing.id !== itemId)
      }));
    } catch (e) {
      setError(friendlyErrorMessage(e));
    }
  };

  // Patches del chat ----------------------------------------------------

  const ingestPatch = (request: ContextPatchRequest) => {
    setProposals((current) => {
      if (current.some((p) => p.id === request.id)) return current;
      const next = [request, ...current];
      void persistProposals(next);
      return next;
    });
  };

  const createProposal = async (request: ContextPatchRequest) => {
    const next = proposals.find((item) => item.id === request.id)
      ? proposals
      : [request, ...proposals];
    setProposals(next);
    await persistProposals(next);
  };

  const acceptPatch = async (patchId: string) => {
    if (!tree) return { ok: false, error: 'No hay árbol activo.' };
    const request = proposals.find((p) => p.id === patchId);
    if (!request) return { ok: false, error: 'Patch no encontrado.' };
    const risk = classifyPatchRisk(request, { tree, activePack: activePack || undefined });
    if (risk === 'critical') {
      return { ok: false, error: 'Patch crítico: requiere revisión manual. Crea una nueva versión o una contradicción.' };
    }
    try {
      const result = applyContextPatch(request, tree, { patchId, actor: 'user', pack: activePack || undefined });
      setTree(result.tree);
      if (result.pack) {
        const next = packs.map((p) => p.id === result.pack!.id ? result.pack! : p);
        setPacks(next);
        await persistPacks(next);
      }
      await persistTree(result.tree);
      await appendReceipt(result.receipt);
      const nextProposals = proposals.map((p) => p.id === patchId ? { ...p, status: 'accepted' as const, appliedAt: new Date().toISOString(), receiptId: result.receipt.id, riskLevel: risk } : p);
      setProposals(nextProposals);
      await persistProposals(nextProposals);
      return { ok: true };
    } catch (e) {
      const message = friendlyErrorMessage(e);
      const nextProposals = proposals.map((p) => p.id === patchId ? { ...p, status: 'failed' as const, errorMessage: message } : p);
      setProposals(nextProposals);
      await persistProposals(nextProposals);
      return { ok: false, error: message };
    }
  };

  const rejectPatch = async (patchId: string) => {
    const request = proposals.find((p) => p.id === patchId);
    if (!request) return;
    const nextProposals = proposals.map((p) => p.id === patchId ? { ...p, status: 'rejected' as const, rejectedAt: new Date().toISOString() } : p);
    setProposals(nextProposals);
    await persistProposals(nextProposals);
    await appendReceipt({
      id: `rcpt_${Math.random().toString(36).slice(2, 10)}`,
      kind: 'chat_patch_rejected',
      treeId: tree?.id,
      patchId,
      summary: `Rechazado: ${request.title}`,
      riskLevel: request.riskLevel,
      createdAt: new Date().toISOString(),
      createdBy: 'user'
    });
  };

  const applyPatchedEdited = async (patchId: string, editedOperations: ContextPatchRequest['patch']['operations']) => {
    if (!tree) return { ok: false, error: 'No hay árbol activo.' };
    const request = proposals.find((p) => p.id === patchId);
    if (!request) return { ok: false, error: 'Patch no encontrado.' };
    const edited: ContextPatchRequest = {
      ...request,
      status: 'pending',
      patch: { operations: editedOperations },
      editedPatch: { operations: editedOperations }
    };
    const risk = worstRisk(classifyPatchRisk(edited, { tree, activePack: activePack || undefined }), edited.riskLevel);
    if (risk === 'critical') {
      return { ok: false, error: 'La edición resultante sigue siendo crítica. Marca como revisión manual.' };
    }
    try {
      const result = applyContextPatch(edited, tree, { patchId, actor: 'user', pack: activePack || undefined });
      setTree(result.tree);
      if (result.pack) {
        const next = packs.map((p) => p.id === result.pack!.id ? result.pack! : p);
        setPacks(next);
        await persistPacks(next);
      }
      await persistTree(result.tree);
      await appendReceipt(result.receipt);
      const nextProposals = proposals.map((p) => p.id === patchId ? { ...p, status: 'edited' as const, editedPatch: { operations: editedOperations }, appliedAt: new Date().toISOString(), receiptId: result.receipt.id, riskLevel: risk } : p);
      setProposals(nextProposals);
      await persistProposals(nextProposals);
      return { ok: true };
    } catch (e) {
      const message = friendlyErrorMessage(e);
      const nextProposals = proposals.map((p) => p.id === patchId ? { ...p, status: 'failed' as const, errorMessage: message } : p);
      setProposals(nextProposals);
      await persistProposals(nextProposals);
      return { ok: false, error: message };
    }
  };

  const revertPatch = async (patchId: string) => {
    if (!tree) return { ok: false, error: 'No hay árbol activo.' };
    const request = proposals.find((p) => p.id === patchId);
    if (!request) return { ok: false, error: 'Patch no encontrado.' };
    try {
      const result = revertContextPatch(request, tree, { patchId });
      setTree(result.tree);
      await persistTree(result.tree);
      await appendReceipt(result.receipt);
      const nextProposals = proposals.map((p) => p.id === patchId ? { ...p, status: 'reverted' as const } : p);
      setProposals(nextProposals);
      await persistProposals(nextProposals);
      return { ok: true };
    } catch (e) {
      return { ok: false, error: friendlyErrorMessage(e) };
    }
  };

  return {
    ready,
    error,
    loading,
    tree,
    packs,
    activePack,
    proposals,
    receipts,
    bank,
    bankLoading,
    workspaceKey,
    refresh,
    refreshBank,
    createDefaultTree,
    renameTree,
    archiveTree,
    createPack,
    renamePack,
    setActivePack,
    toggleNodeInPack,
    compileActivePack,
    sendActivePackToChat,
    createNode,
    updateNode,
    closeTask,
    reopenTask,
    moveNode,
    excludeNode,
    restoreNode,
    toggleCanon,
    addBankItemToTree,
    addManualBankItem,
    removeManualBankItem,
    sourceDirectories,
    sourceDirectoriesLoading,
    addSourceDirectory,
    removeSourceDirectory,
    refreshSourceDirectoryFiles,
    toggleSourceFileInclude,
    setSourceFileBranch,
    linkSourceDirectoryToTree,
    ingestPatch,
    createProposal,
    acceptPatch,
    rejectPatch,
    applyPatchedEdited,
    revertPatch
  };
}

export { PatchValidationError };
