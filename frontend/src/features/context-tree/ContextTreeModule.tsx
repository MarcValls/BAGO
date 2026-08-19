// ContextTreeModule: componente raíz del módulo de arquitectura de
// contexto. Junta Toolbar + Banco + Canvas + Inspector + Bandeja +
// Pack bar. Reemplaza la antigua pantalla pasiva de métricas.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Drawer } from '@/lib/Drawer';
import type { ActiveSection, ContextTargetKind, SelectionRecord } from '@/contracts/backend';
import type {
  ContextBankItem,
  ContextNode,
  ContextNodeType,
  ContextPatchOp,
  ContextPatchRequest
} from './contextTreeTypes';
import type { UseContextTreeState } from './useContextTree';
import { ContextInspector } from './ContextInspector';
import { ContextCategoryExplorer, type ContextDisplayMode } from './ContextCategoryExplorer';
import { ContextPatchPreview } from './ContextPatchPreview';
import { ContextCollectionDialog } from './ContextCollectionDialog';
import { ContextActivityTray } from './ContextActivityTray';
import {
  ContextStageCompile,
  ContextStageDestination,
  ContextStagePack,
  ContextStageSources,
  ContextStageStructure
} from './ContextStages';
import { FlowShell } from '@/lib/flow-shell/FlowShell';
import type { FlowStageItem } from '@/lib/flow-shell/FlowNav';
import { Icon } from '@/shared/Icon';
import { readWorkspaceStorageValue, writeWorkspaceStorageValue } from '@/shared/workspaceStateKeys';
import { BagoClient, safeJson } from '@/api/client';
import { compactTaskTitle } from '@/shared/taskPresentation';
import {
  buildCollectionPrompt,
  collectionOperationToPatch,
  parseStructuredCollection,
  type CollectionHistoryItem
} from './contextCollection';
import {
  buildContextReviewPrompt,
  CONTEXT_CATEGORIES,
  parseContextReviewResponse,
  type ContextCategoryType,
  type ContextReviewResult
} from './contextReview';

interface Props {
  ctx: UseContextTreeState;
  apiBase: string;
  apiToken: string;
  workspaceRoot: string;
  onCreatePlan: (title: string, summary: string) => Promise<void> | void;
  onRunContextCommand: (command: string) => Promise<void>;
  onOpenInWorkspace: (path: string) => void;
  onSetSection: (section: ActiveSection) => void;
  // Patches extraídos de los turnos del chat, identificados por turno.
  // El módulo los ingiere y los une con la lista persistida.
  incomingPatches?: Array<{ patch: ContextPatchRequest; turnId: string }>;
  onPatchHandled?: (patchId: string) => void;
  bankPending?: Array<{
    id: string;
    kind: 'file' | 'directory' | 'source';
    path: string;
    title: string;
    destination: 'tree' | 'pack';
    createdAt: string;
  }>;
  onBankPendingConsumed?: (id: string) => void;
  initialSelectedNodeId?: string | null;
  initialEditingPatchId?: string | null;
  onInitialStateConsumed?: () => void;
}

const ROOT_TYPES: ContextNodeType[] = ['intent', 'source', 'decision', 'rule', 'claim', 'risk', 'pending', 'evidence', 'proposal', 'note'];
type ContextFlowStage = 'sources' | 'structure' | 'pack' | 'compile' | 'destination';
type ContextWorkbenchView = 'focus' | 'tasks' | 'library' | 'advanced';
const FLOW_STAGES: Array<{ id: ContextFlowStage; label: string; icon: 'folder' | 'tree' | 'pack' | 'refresh' | 'send' }> = [
  { id: 'sources', label: 'Fuentes', icon: 'folder' },
  { id: 'structure', label: 'Estructura', icon: 'tree' },
  { id: 'pack', label: 'Pack', icon: 'pack' },
  { id: 'compile', label: 'Compilación', icon: 'refresh' },
  { id: 'destination', label: 'Destino', icon: 'send' }
];

function newNodeDraft(parentId: string, type: ContextNodeType): { parentId: string; type: ContextNodeType; title: string } {
  return { parentId, type, title: '' };
}

export function workspaceContextStorageKey(workspaceRoot: string, suffix: string): string {
  const cleanRoot = String(workspaceRoot || '').trim();
  return cleanRoot ? `bago.context.${cleanRoot}::${suffix}` : `bago.context.global::${suffix}`;
}

function readWorkspaceContextSessionValue(
  workspaceRoot: string,
  suffix: string,
  allowed: readonly string[],
  fallback: string
): string {
  const stored = readWorkspaceStorageValue(workspaceRoot, `context.${suffix}`);
  return stored && (allowed.length === 0 || allowed.includes(stored)) ? stored : fallback;
}

function writeWorkspaceContextSessionValue(workspaceRoot: string, suffix: string, value: string): void {
  writeWorkspaceStorageValue(workspaceRoot, `context.${suffix}`, value);
}

export function ContextTreeModule(props: Props) {
  const ctx = props.ctx;
  const openChat = () => {
    writeWorkspaceStorageValue(props.workspaceRoot, 'chat-mode', 'open');
    props.onSetSection('home');
  };
  const [activeStage, setActiveStage] = useState<ContextFlowStage>('sources');
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(props.initialSelectedNodeId || null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [editingPatch, setEditingPatch] = useState<ContextPatchRequest | null>(null);
  const [newChildDraft, setNewChildDraft] = useState<{ parentId: string; type: ContextNodeType; title: string } | null>(null);
  const [inspectorDrawerOpen, setInspectorDrawerOpen] = useState<boolean>(false);
  const [exportingPack, setExportingPack] = useState(false);
  const [compiledModal, setCompiledModal] = useState<string | null>(null);
  const [collectionOpen, setCollectionOpen] = useState(false);
  const [collectionBusy, setCollectionBusy] = useState(false);
  const [collectionProposal, setCollectionProposal] = useState<ContextPatchRequest | null>(null);
  const [collectionNotice, setCollectionNotice] = useState<{ tone: 'info' | 'warning' | 'error'; message: string } | null>(null);
  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(() => {
    return readWorkspaceStorageValue(props.workspaceRoot, 'context.initial-branch') || null;
  });
  const [newBranchTitle, setNewBranchTitle] = useState('');
  const [branchFilter, setBranchFilter] = useState<'all' | 'open' | 'closed' | 'questions' | 'proposals' | 'errors'>('all');
  const [closeNote, setCloseNote] = useState('');
  const [closeOpen, setCloseOpen] = useState(false);
  const [workbenchView, setWorkbenchView] = useState<ContextWorkbenchView>(() => {
    return (readWorkspaceStorageValue(props.workspaceRoot, 'context.workbench-view') || 'focus') as ContextWorkbenchView;
  });
  const [activeContextView, setActiveContextView] = useState<ContextCategoryType>('intent');
  const [contextDisplayMode, setContextDisplayMode] = useState<ContextDisplayMode>(() => {
    return (readWorkspaceStorageValue(props.workspaceRoot, 'context.display-mode') || 'map') as ContextDisplayMode;
  });
  const [focusedCategoryNodeId, setFocusedCategoryNodeId] = useState<string | null>(null);
  const [reviewingNodeId, setReviewingNodeId] = useState<string | null>(null);
  const [reviewNotice, setReviewNotice] = useState<string>('');
  const [moduleNotice, setModuleNotice] = useState<{ tone: 'info' | 'warning' | 'error'; message: string } | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<{ type: 'reject' | 'revert' | 'review'; patchId: string } | null>(null);
  const clearModuleNotice = useCallback(() => setModuleNotice(null), []);
  useEffect(() => {
    if (!moduleNotice) return;
    const t = setTimeout(() => setModuleNotice(null), 6000);
    return () => clearTimeout(t);
  }, [moduleNotice]);
  useEffect(() => {
    if (!pendingConfirm) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        setPendingConfirm(null);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [pendingConfirm]);

  // CANON[CTX-016]: el chat puede pedir abrir un patch en modo edición.
  // Cuando lo recibimos, abrimos el preview y limpiamos el flag.
  useEffect(() => {
    if (!props.initialEditingPatchId) return;
    const patch = ctx.proposals.find((p) => p.id === props.initialEditingPatchId);
    if (patch) {
      setEditingPatch(patch);
    }
    props.onInitialStateConsumed?.();
  }, [props.initialEditingPatchId, ctx.proposals, props]);

  // Expansión automática: raíz y todas las ramas guía siempre expandidas.
  useEffect(() => {
    if (!ctx.tree) return;
    setExpanded((current) => {
      const next = new Set(current);
      next.add(ctx.tree!.rootId);
      for (const node of Object.values(ctx.tree!.nodes)) {
        if (node.parentId === ctx.tree!.rootId) next.add(node.id);
      }
      return next;
    });
  }, [ctx.tree?.id]);

  // Ingerir patches entrantes del chat.
  useEffect(() => {
    if (!props.incomingPatches?.length) return;
    for (const entry of props.incomingPatches) {
      if (entry.patch.status === 'pending' && !ctx.proposals.find((p) => p.id === entry.patch.id)) {
        ctx.ingestPatch(entry.patch);
        props.onPatchHandled?.(entry.patch.id);
      }
    }
  }, [props.incomingPatches, ctx.proposals, ctx, props]);

  // CANON[CTX-010]: consumir items encolados desde Workspace.
  // Cuando el árbol está listo, los añadimos al árbol o al pack y los
  // marcamos como consumidos en el padre.
  useEffect(() => {
    if (!ctx.tree || !ctx.ready) return;
    if (!props.bankPending?.length) return;
    for (const item of props.bankPending) {
      const kindMatch = item.title.match(/^\[(claim|rule)\]/);
      const typeOverride = kindMatch ? (kindMatch[1] as ContextNodeType) : (item.kind === 'source' ? 'source' : item.kind === 'directory' ? 'source' : 'file');
      const cleanTitle = item.title.replace(/^\[(claim|rule)\]\s*/, '');
      (async () => {
        const node = await ctx.createNode({
          parentId: typeOverride === 'rule' || typeOverride === 'claim'
            ? (Object.values(ctx.tree!.nodes).find((n) => n.type === typeOverride)?.id || ctx.tree!.rootId)
            : (Object.values(ctx.tree!.nodes).find((n) => n.type === 'source' && n.parentId === ctx.tree!.rootId)?.id || ctx.tree!.rootId),
          type: typeOverride,
          title: cleanTitle,
          summary: `Encolado desde otra pantalla · ${item.path}`,
          sourceRefs: [{
            kind: item.kind === 'source' ? 'manual' : item.kind === 'directory' ? 'workspace_directory' : 'workspace_file',
            path: item.path,
            origin: 'workspace'
          }]
        });
        if (item.destination === 'pack' && node && ctx.activePack) {
          await ctx.toggleNodeInPack(node.id);
        }
        if (node) {
          setSelectedNodeId(node.id);
        }
        props.onBankPendingConsumed?.(item.id);
      })();
    }
  }, [ctx.tree?.id, ctx.ready, props.bankPending, props.onBankPendingConsumed]);

  const selectedNode = useMemo(() => {
    if (!selectedNodeId || !ctx.tree) return null;
    return ctx.tree.nodes[selectedNodeId] || null;
  }, [ctx.tree, selectedNodeId]);

  const flatNodes = useMemo(() => ctx.tree ? Object.values(ctx.tree.nodes) : [], [ctx.tree]);

  const taskBranches = useMemo(() => {
    if (!ctx.tree) return [] as ContextNode[];
    return flatNodes
      .filter((node) => node.parentId === ctx.tree!.rootId && (node.type === 'pending' || node.metadata?.branch === true))
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  }, [ctx.tree, flatNodes]);

  const categoryNodes = useMemo(() => {
    return flatNodes
      .filter((node) => node.type === activeContextView && node.status !== 'archived')
      .sort((a, b) => {
        const aRoot = a.parentId === ctx.tree?.rootId ? 0 : 1;
        const bRoot = b.parentId === ctx.tree?.rootId ? 0 : 1;
        return aRoot - bRoot || b.updatedAt.localeCompare(a.updatedAt);
      });
  }, [activeContextView, flatNodes, ctx.tree?.rootId]);

  useEffect(() => {
    if (!selectedNodeId || ctx.tree?.nodes[selectedNodeId]?.type !== activeContextView) {
      setSelectedNodeId(categoryNodes[0]?.id || null);
    }
    setReviewNotice('');
  }, [activeContextView, categoryNodes, ctx.tree, selectedNodeId]);

  useEffect(() => {
    setFocusedCategoryNodeId(null);
  }, [activeContextView]);

  const changeWorkbenchView = (view: ContextWorkbenchView) => {
    if (view === 'advanced' && workbenchView !== 'advanced') setActiveStage(nextStage);
    setWorkbenchView(view);
    writeWorkspaceContextSessionValue(props.workspaceRoot, 'workbench-view', view);
  };

  const changeContextDisplayMode = (mode: ContextDisplayMode) => {
    setContextDisplayMode(mode);
    writeWorkspaceContextSessionValue(props.workspaceRoot, 'display-mode', mode);
  };

  const openCategoryNode = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setFocusedCategoryNodeId(nodeId);
    setReviewNotice('');
  };

  useEffect(() => {
    const nextSelectedBranchId = readWorkspaceContextSessionValue(props.workspaceRoot, 'initial-branch', [], '') || null;
    setSelectedBranchId(nextSelectedBranchId);
    if (!nextSelectedBranchId) {
      writeWorkspaceStorageValue(props.workspaceRoot, 'context.initial-branch', '');
    }
  }, [props.workspaceRoot]);

  useEffect(() => {
    if (!selectedBranchId || !taskBranches.some((branch) => branch.id === selectedBranchId)) {
      setSelectedBranchId(taskBranches[0]?.id || null);
    }
  }, [selectedBranchId, taskBranches]);

  const selectedBranch = taskBranches.find((branch) => branch.id === selectedBranchId) || taskBranches[0] || null;
  const pendingProposals = ctx.proposals.filter((proposal) => proposal.status === 'pending');
  const openTaskBranches = taskBranches.filter((branch) => branch.status !== 'canon' && branch.status !== 'archived');
  const filteredBranches = useMemo(() => taskBranches.filter((branch) => {
    const branchNodes = flatNodes.filter((node) => node.parentId === branch.id);
    const hasQuestion = pendingProposals.some((proposal) => proposal.metadata?.clarification && proposal.status === 'pending');
    if (branchFilter === 'open') return branch.status !== 'canon' && branch.status !== 'archived';
    if (branchFilter === 'closed') return branch.status === 'canon' || branch.status === 'archived';
    if (branchFilter === 'questions') return hasQuestion || branchNodes.some((node) => node.type === 'pending');
    if (branchFilter === 'proposals') return pendingProposals.length > 0;
    if (branchFilter === 'errors') return branchNodes.some((node) => node.status === 'conflict' || node.status === 'stale');
    return true;
  }), [taskBranches, flatNodes, branchFilter, pendingProposals]);
  const selectedBranchNodes = useMemo(() => {
    if (!selectedBranch || !ctx.tree) return [] as ContextNode[];
    const result: ContextNode[] = [];
    const visit = (parentId: string) => {
      flatNodes
        .filter((node) => node.parentId === parentId)
        .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
        .forEach((node) => {
          result.push(node);
          visit(node.id);
        });
    };
    visit(selectedBranch.id);
    return result;
  }, [ctx.tree, flatNodes, selectedBranch]);

  const stageIndex = (stage: ContextFlowStage) => FLOW_STAGES.findIndex((item) => item.id === stage);

  // FIX v0.3: declaraciones movidas ANTES de isStageLocked/flowStages
  // para evitar temporal dead zone (TDZ). El bug original era:
  //   - isStageLocked y flowStages usaban hasSources/hasStructuredNodes/
  //     hasPackSelection/destinationReady/nextStage
  //   - esas const se declaraban DESPUÉS de su uso
  //   - en strict mode (ESM) el acceso antes de const → ReferenceError
  // Cambiar el orden resuelve sin alterar la lógica.

  // Validación para envío al chat (movida arriba porque destinationReady
  // la consume).
  const packBlockedReason = useMemo(() => {
    if (!ctx.activePack) return 'No hay pack activo.';
    if (!ctx.tree) return 'No hay árbol activo.';
    if (!ctx.activePack.markdown) return 'El pack no ha sido compilado todavía.';
    if (!ctx.activePack.nodeIds.length) return 'El pack está vacío.';
    const rootNode = ctx.tree.nodes[ctx.tree.rootId];
    if (!rootNode) return 'Árbol sin raíz.';
    const intent = Object.values(ctx.tree.nodes).find((n) => n.type === 'intent' && n.parentId === ctx.tree!.rootId && n.status === 'active');
    if (!intent) return 'Falta intención raíz activa.';
    if (ctx.activePack.conflicts > 0) return 'Hay conflictos abiertos. Resuélvelos antes de enviar al chat.';
    return null;
  }, [ctx.tree, ctx.activePack]);

  const hasSources = useMemo(() => {
    return ctx.sourceDirectories.length > 0 || ctx.bank.sources.length > 0 || ctx.bank.manual.length > 0;
  }, [ctx.sourceDirectories.length, ctx.bank.sources.length, ctx.bank.manual.length]);

  const hasStructuredNodes = useMemo(() => {
    if (!ctx.tree) return false;
    return Object.values(ctx.tree.nodes).some((node) => node.parentId === ctx.tree!.rootId && node.type !== 'root');
  }, [ctx.tree]);

  const packNodeCount = ctx.activePack?.nodeIds.length || 0;
  const hasPackSelection = packNodeCount > 0;
  const hasCompiledPack = Boolean(ctx.activePack?.markdown);
  const destinationReady = hasCompiledPack && hasPackSelection && !packBlockedReason;

  const nextStage: ContextFlowStage = !hasSources
    ? 'sources'
    : !hasStructuredNodes
      ? 'structure'
      : !hasPackSelection
        ? 'pack'
        : !hasCompiledPack
          ? 'compile'
          : 'destination';

  function isStageLocked(stage: ContextFlowStage) {
    if (stage === 'sources') return false;
    if (stage === 'structure') return !hasSources;
    if (stage === 'pack') return !hasStructuredNodes;
    if (stage === 'compile') return !hasPackSelection;
    return !destinationReady;
  }

  const flowStages: FlowStageItem[] = FLOW_STAGES.map((stage) => {
    const locked = isStageLocked(stage.id);
    return {
      id: stage.id,
      label: stage.label,
      icon: stage.icon,
      state: stage.id === activeStage
        ? 'active'
        : stage.id === nextStage
          ? 'next'
          : stageIndex(stage.id) < stageIndex(nextStage)
            ? 'completed'
            : locked
              ? 'locked'
              : 'idle'
    };
  });

  const toggleExpand = (nodeId: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  };

  const refreshBank = () => ctx.refreshBank();

  const handleAddBankItem = async (item: ContextBankItem) => {
    const node = await ctx.addBankItemToTree(item);
    if (node) {
      setSelectedNodeId(node.id);
      setExpanded((current) => { const next = new Set(current); next.add(node.id); return next; });
    }
  };

  const handleAddBankToPack = async (item: ContextBankItem) => {
    const node = await ctx.addBankItemToTree(item);
    if (node && ctx.activePack) {
      await ctx.toggleNodeInPack(node.id);
    }
  };

  const openRelated = (nodeId: string) => {
    setSelectedNodeId(nodeId);
    setExpanded((current) => { const next = new Set(current); next.add(nodeId); return next; });
  };

  const handleSaveNode = async (patch: Partial<ContextNode>) => {
    if (!selectedNode) return;
    await ctx.updateNode(selectedNode.id, patch);
  };

  const createCategoryNode = async () => {
    if (!ctx.tree) return;
    const category = CONTEXT_CATEGORIES.find((entry) => entry.id === activeContextView);
    const categoryRoot = flatNodes.find((node) => node.type === activeContextView && node.parentId === ctx.tree!.rootId);
    const node = await ctx.createNode({
      parentId: categoryRoot?.id || ctx.tree.rootId,
      type: activeContextView,
      title: `Nueva ${category?.singular || 'entrada'}`,
      summary: category?.hint || '',
      status: 'active',
      priority: 'medium'
    });
    if (node) {
      setSelectedNodeId(node.id);
      setFocusedCategoryNodeId(node.id);
      setReviewNotice('Completa el contenido y guárdalo para revisarlo con el modelo activo.');
    }
  };

  const saveAndReviewCategoryNode = async (patch: Partial<ContextNode>) => {
    if (!selectedNode) return;
    const nodeId = selectedNode.id;
    const reviewedNode = { ...selectedNode, ...patch };
    const pendingMetadata = {
      ...selectedNode.metadata,
      context_review: {
        status: 'reviewing',
        summary: 'Contenido guardado. Consultando el modelo activo…',
        findings: [],
        reviewedAt: '',
        provider: '',
        model: ''
      }
    };
    setReviewingNodeId(nodeId);
    setReviewNotice('Contenido guardado. Revisando coherencia con el modelo activo…');
    await ctx.updateNode(nodeId, { ...patch, metadata: pendingMetadata });
    try {
      const client = new BagoClient(props.apiBase, props.apiToken);
      const response = await Promise.race([
        client.sendInternalChat(buildContextReviewPrompt(activeContextView, reviewedNode)),
        new Promise<never>((_, reject) => window.setTimeout(() => reject(new Error('El modelo no respondió en 45 segundos.')), 45_000))
      ]);
      const responseText = String(response.response || response.message || response.response_content || response.content || '').trim().slice(0, 16000);
      const review = parseContextReviewResponse(responseText);
      if (!review) throw new Error('El modelo no devolvió una revisión JSON válida.');
      const details = (response.details && typeof response.details === 'object' ? response.details : {}) as Record<string, unknown>;
      const metadata = {
        ...selectedNode.metadata,
        context_review: {
          ...review,
          reviewedAt: new Date().toISOString(),
          provider: String(response.provider || details.provider || ''),
          model: String(response.model || response.effective_model || details.model || '')
        }
      };
      await ctx.updateNode(nodeId, { ...patch, metadata });
      setReviewNotice(review.status === 'validated' ? 'Guardado y validado por el modelo activo.' : 'Guardado. La revisión ha detectado puntos que conviene comprobar.');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'No se pudo consultar el modelo activo.';
      await ctx.updateNode(nodeId, {
        ...patch,
        metadata: {
          ...selectedNode.metadata,
          context_review: {
            status: 'unavailable',
            summary: message,
            findings: [],
            reviewedAt: new Date().toISOString(),
            provider: '',
            model: ''
          }
        }
      });
      setReviewNotice(`El contenido quedó guardado. Revisión pendiente: ${message}`);
    } finally {
      setReviewingNodeId(null);
    }
  };

  const handleCreatePlan = async (summary: string) => {
    await props.onCreatePlan('Tarea desde Árbol de Contexto', summary);
  };

  const startProposalTask = async (proposal: ContextPatchRequest) => {
    const operationTitles = proposal.patch.operations.map((operation) => {
      if (operation.op === 'create') return operation.title;
      if (operation.op === 'update') return `Actualizar ${operation.nodeId}`;
      return `${operation.op} ${'nodeId' in operation ? operation.nodeId : ''}`.trim();
    }).filter(Boolean);
    await props.onCreatePlan(
      compactTaskTitle(proposal.title),
      [proposal.reason, operationTitles.length ? `Cambios mencionados: ${operationTitles.join(', ')}.` : ''].filter(Boolean).join('\n\n')
    );
  };

  const startBranchTask = async (branch: ContextNode) => {
    await props.onCreatePlan(compactTaskTitle(branch.title), branch.summary || 'Ejecutar la tarea abierta desde el contexto de trabajo.');
  };

  const createTaskBranch = async () => {
    if (!ctx.tree || !newBranchTitle.trim()) return;
    const node = await ctx.createNode({
      parentId: ctx.tree.rootId,
      type: 'pending',
      title: newBranchTitle.trim(),
      summary: 'Tarea abierta. El contexto se completa desde el chat y con recopilación autorizada.',
      status: 'active',
      priority: 'medium'
    });
    if (node) {
      setSelectedBranchId(node.id);
      setNewBranchTitle('');
    }
  };

  const openCollection = () => {
    const pending = ctx.proposals.find((proposal) => proposal.proposalType === 'context_collection' && proposal.status === 'pending') || null;
    setCollectionProposal(pending);
    setCollectionNotice(null);
    setCollectionOpen(true);
  };

  const collectFromChat = async (question: string) => {
    if (!ctx.tree) return;
    setCollectionBusy(true);
    setCollectionNotice(null);
    try {
      const history: CollectionHistoryItem[] = ctx.bank.history.slice(-20).map((item) => {
        const raw = item.raw || {};
        return {
          role: String(raw.role || raw.type || 'chat'),
          text: String(raw.content || raw.text || raw.message || item.title || '').trim().slice(0, 4000),
          timestamp: String(raw.timestamp || raw.created_at || '').trim() || undefined
        };
      }).filter((item) => item.text);
      if (!history.length) {
        setCollectionNotice({ tone: 'warning', message: 'No hay mensajes en esta conversación para recopilar. Escribe primero en el chat o añade contexto manualmente.' });
        return;
      }
      const treePaths = Object.values(ctx.tree.nodes)
        .filter((node) => node.parentId && node.status !== 'archived')
        .map((node) => node.title)
        .slice(0, 100);
      const targetBranchLabel = selectedBranch?.title || 'nueva rama de tarea';
      const collectionQuestion = [`Rama de destino: ${targetBranchLabel}. Toda la propuesta debe quedar dentro de esta rama.`, question.trim()].filter(Boolean).join('\n');
      const historyText = history.length ? `${history.length} mensajes completos` : 'No hay mensajes disponibles en el historial.';
      let modelText = '';
      let structured = null;
      let modelError = '';
      try {
        const collector = new BagoClient(props.apiBase, props.apiToken);
        const response = await collector.sendInternalChat(buildCollectionPrompt(collectionQuestion, history, treePaths));
        modelText = String(response.response || response.message || response.response_content || response.content || '').trim().slice(0, 16000);
        structured = parseStructuredCollection(modelText);
        if (!structured) modelError = 'El modelo respondió, pero no devolvió una propuesta JSON válida.';
      } catch (error) {
        modelError = error instanceof Error ? error.message : 'No se pudo consultar el modelo.';
      }
      if (!structured) {
        setCollectionNotice({ tone: 'warning', message: `${modelError || 'El modelo no respondió'} Se muestra un fallback local para revisión; no se añadirá nada sin tu permiso.` });
      }
      const fallbackUi = history.some((item) => /ui|pantalla|interfaz|frontend|vista|componente/i.test(item.text)) || /ui|pantalla|interfaz|frontend|vista|componente/i.test(question);
      const fallbackArea = fallbackUi ? 'UI' : targetBranchLabel;
      const fallbackOperations = [{
        op: 'create' as const,
        parent_path: fallbackUi && !selectedBranch ? ['UI', 'Pantallas'] : [],
        type: 'pending' as const,
        title: fallbackUi ? 'Pantalla o tarea detectada en el chat' : 'Contexto recopilado del chat',
        summary: history.map((item) => item.text).join(' ').slice(0, 320),
        priority: 'medium' as const
      }];
      const proposalData = structured || {
        summary: historyText,
        clarification: question.trim() || `Confirma que el contexto detectado pertenece a «${targetBranchLabel}».`,
        operations: fallbackOperations
      };
      const operations: ContextPatchOp[] = [];
      const nodeByPath = new Map<string, string>();
      for (const node of Object.values(ctx.tree.nodes)) {
        const segments: string[] = [];
        let current: typeof node | undefined = node;
        while (current && current.parentId && (!selectedBranch || current.id !== selectedBranch.id)) {
          segments.unshift(current.title);
          current = ctx.tree.nodes[current.parentId];
        }
        if (selectedBranch && current?.id !== selectedBranch.id) continue;
        if (segments.length) nodeByPath.set(segments.join('/').toLowerCase(), node.id);
      }
      for (const [index, operation] of proposalData.operations.entries()) {
        const path = (operation.parent_path || []).map((part) => String(part).trim()).filter(Boolean).slice(0, 5)
          .filter((part) => !selectedBranch || part.toLowerCase() !== selectedBranch.title.toLowerCase());
        let parentId = selectedBranch?.id || ctx.tree.rootId;
        const builtPath: string[] = [];
        for (const part of path) {
          builtPath.push(part);
          const key = builtPath.join('/').toLowerCase();
          const existingId = nodeByPath.get(key);
          if (existingId) {
            parentId = existingId;
            continue;
          }
          const nodeId = `collect_branch_${Date.now()}_${index}_${builtPath.length}`;
          operations.push({
            op: 'create', nodeId, parentId, type: 'note', title: part,
            summary: `Rama propuesta por recopilación: ${builtPath.join(' / ')}`, status: 'proposed', priority: 'medium'
          });
          nodeByPath.set(key, nodeId);
          parentId = nodeId;
        }
        operations.push(collectionOperationToPatch(operation, parentId, `collect_task_${Date.now()}_${index}`));
      }
      if (!operations.length) throw new Error('No se pudo construir ninguna operación de contexto.');
      const proposal: ContextPatchRequest = {
        id: `collect_${Date.now()}`,
        treeId: ctx.tree.id,
        validationMode: 'modal',
        proposalType: 'context_collection',
        title: `Recopilar contexto: ${structured ? 'propuesta del modelo' : fallbackArea}`,
        reason: proposalData.summary,
        riskLevel: 'low',
        patch: { operations },
        createdAt: new Date().toISOString(),
        createdBy: 'chat',
        status: 'pending',
        metadata: {
          clarification: proposalData.clarification || question.trim() || 'Confirma la propuesta antes de añadirla.',
          source: structured ? 'model_chat' : 'chat_history_fallback',
          model_error: modelError || '',
          history_items: String(history.length)
        }
      };
      await ctx.createProposal(proposal);
      setCollectionProposal(proposal);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'No se pudo recopilar el contexto.';
      setCollectionNotice({ tone: 'error', message: `No se aplicó ningún cambio. ${message}` });
    } finally {
      setCollectionBusy(false);
    }
  };

  const acceptCollection = async () => {
    if (!collectionProposal) return;
    setCollectionBusy(true);
    const result = await ctx.acceptPatch(collectionProposal.id);
    setCollectionBusy(false);
    if (!result.ok) {
      setModuleNotice({ tone: 'error', message: result.error || 'No se pudo aplicar la propuesta.' });
      return;
    }
    setCollectionProposal(null);
    setCollectionOpen(false);
  };

  const rejectCollection = async () => {
    if (collectionProposal) await ctx.rejectPatch(collectionProposal.id);
    setCollectionProposal(null);
    setCollectionOpen(false);
  };

  const acceptCollectionOperations = async (operations: ContextPatchOp[]) => {
    if (!collectionProposal || !operations.length) return;
    setCollectionBusy(true);
    const result = await ctx.applyPatchedEdited(collectionProposal.id, operations);
    setCollectionBusy(false);
    if (!result.ok) {
      setCollectionNotice({ tone: 'error', message: result.error || 'No se pudo aplicar la selección.' });
      return;
    }
    setCollectionProposal(null);
    setCollectionOpen(false);
  };

  const closeSelectedTask = async () => {
    if (!selectedBranch || !closeNote.trim()) return;
    const result = await ctx.closeTask(selectedBranch.id, closeNote.trim());
    if (!result.ok) {
      setModuleNotice({ tone: 'error', message: result.error || 'No se pudo cerrar la tarea.' });
      return;
    }
    setCloseNote('');
    setCloseOpen(false);
  };

  const reopenSelectedTask = async () => {
    if (!selectedBranch) return;
    const result = await ctx.reopenTask(selectedBranch.id);
    if (!result.ok) setModuleNotice({ tone: 'error', message: result.error || 'No se pudo reabrir la tarea.' });
  };

  const handleCopyId = (id: string) => {
    navigator.clipboard?.writeText(id);
    setModuleNotice({ tone: 'info', message: 'ID copiado al portapapeles.' });
  };

  const showCompiledRaw = () => {
    if (ctx.activePack?.markdown) setCompiledModal(ctx.activePack.markdown);
  };

  const copyPack = async () => {
    if (!ctx.activePack?.markdown) return;
    setExportingPack(true);
    try {
      await navigator.clipboard?.writeText(ctx.activePack.markdown);
    } finally {
      setExportingPack(false);
    }
  };

  const sendToChat = async () => {
    await ctx.sendActivePackToChat();
  };

  const sendToPipeline = async () => {
    if (!ctx.activePack?.markdown) return;
    await props.onCreatePlan(`Aplicar pack ${ctx.activePack.name}`, ctx.activePack.markdown.slice(0, 600));
  };

  const handleAcceptPatch = async (patchId: string) => {
    const result = await ctx.acceptPatch(patchId);
    if (!result.ok && result.error) {
      setModuleNotice({ tone: 'error', message: result.error });
    }
  };
  const handleRejectPatch = (patchId: string) => {
    setPendingConfirm({ type: 'reject', patchId });
  };
  const handleEditPatch = (patchId: string) => {
    const patch = ctx.proposals.find((p) => p.id === patchId);
    if (patch) setEditingPatch(patch);
  };
  const handleApplyEdited = async (operations: ContextPatchOp[]) => {
    if (!editingPatch) return;
    const result = await ctx.applyPatchedEdited(editingPatch.id, operations);
    if (!result.ok) {
      setModuleNotice({ tone: 'error', message: result.error || 'No se pudo aplicar el patch.' });
    }
    setEditingPatch(null);
  };
  const handleRevertPatch = (patchId: string) => {
    setPendingConfirm({ type: 'revert', patchId });
  };
  const handleOpenInTree = (patchId: string) => {
    const patch = ctx.proposals.find((p) => p.id === patchId);
    if (!patch) return;
    if (patch.targetNodeId) {
      openRelated(patch.targetNodeId);
    }
  };
  const handleReviewPatch = (patchId: string) => {
    setPendingConfirm({ type: 'review', patchId });
  };

  const resolvePendingConfirm = async (confirm: boolean) => {
    const request = pendingConfirm;
    setPendingConfirm(null);
    if (!confirm || !request) return;
    if (request.type === 'reject') {
      await ctx.rejectPatch(request.patchId);
      return;
    }
    if (request.type === 'revert') {
      const result = await ctx.revertPatch(request.patchId);
      if (!result.ok && result.error) {
        setModuleNotice({ tone: 'error', message: result.error });
      }
      return;
    }
    if (request.type === 'review') {
      // Para CRIT: no aplicamos. Sugerimos crear nueva versión (no-op por ahora).
      await ctx.rejectPatch(request.patchId);
    }
  };

  const handleAddChild = (parentId: string) => {
    const parent = ctx.tree?.nodes[parentId];
    const type: ContextNodeType = parent?.type === 'root' ? 'note' : (parent?.type || 'note');
    setNewChildDraft(newNodeDraft(parentId, type));
  };

  const submitNewChild = async () => {
    if (!newChildDraft || !newChildDraft.title.trim()) {
      setNewChildDraft(null);
      return;
    }
    const node = await ctx.createNode({ ...newChildDraft, title: newChildDraft.title.trim() });
    setNewChildDraft(null);
    if (node) setSelectedNodeId(node.id);
  };

  // FIX v0.3: hasSources/hasStructuredNodes/hasPackSelection/destinationReady/nextStage
  // se movieron ARRIBA (antes de isStageLocked/flowStages) para evitar TDZ.
  // packBlockedReason también se movió arriba (lo consume destinationReady).
  // Ver comentario sobre FIX v0.3 más arriba.

  const packNodes = useMemo(() => {
    if (!ctx.tree || !ctx.activePack) return [] as ContextNode[];
    return ctx.activePack.nodeIds
      .map((nodeId) => ctx.tree!.nodes[nodeId])
      .filter((node): node is ContextNode => Boolean(node));
  }, [ctx.tree, ctx.activePack]);

  const selectableNodes = useMemo(() => {
    if (!ctx.tree) return [] as ContextNode[];
    return Object.values(ctx.tree.nodes).filter((node) => node.id !== ctx.tree!.rootId);
  }, [ctx.tree]);

  if (ctx.error) return (
    <div className="task-context-page task-context-state" data-error="true">
      <Icon name="warning" size={24} /><h2>No se pudo cargar el contexto de trabajo</h2><p>{ctx.error}</p>
      <button type="button" className="primary-button" onClick={() => void ctx.refresh()}><Icon name="refresh" size={12} /> Reintentar</button>
    </div>
  );

  if (!ctx.ready) return (
    <div className="task-context-page task-context-state" data-loading="true">
      <Icon name="refresh" size={24} /><h2>Cargando contexto de trabajo</h2><p>Recuperando las ramas y propuestas pendientes…</p>
    </div>
  );

  if (!ctx.tree) return (
    <div className="task-context-page task-context-state">
      <Icon name="context" size={28} /><h2>Este proyecto aún no tiene contexto de trabajo</h2>
      <p>Crea la primera rama de tarea para empezar a ordenar el trabajo.</p>
      <button type="button" className="primary-button" onClick={() => void ctx.createDefaultTree()}><Icon name="plus" size={12} /> Crear contexto de trabajo</button>
    </div>
  );

  const recentChat = ctx.bank.history.slice(-5).reverse();
  const branchStatus = (branch: ContextNode) => branch.status === 'archived' ? 'Archivada' : branch.status === 'canon' ? 'Cerrada' : 'Abierta';
  const activeCategory = CONTEXT_CATEGORIES.find((entry) => entry.id === activeContextView) || null;
  const rawReview = selectedNode?.metadata?.context_review;
  const selectedReview = rawReview && typeof rawReview === 'object' && !Array.isArray(rawReview)
    ? rawReview as Partial<ContextReviewResult> & { reviewedAt?: string; provider?: string; model?: string }
    : null;
  const reviewFindings = Array.isArray(selectedReview?.findings) ? selectedReview.findings : [];
  const projectName = props.workspaceRoot.split(/[\\/]/).filter(Boolean).pop() || 'proyecto activo';

  return (
    <div className="task-context-page">
      {pendingConfirm && (
        <div className="context-confirm-banner" role="alertdialog" aria-live="polite" aria-modal="false">
          <div className="context-confirm-banner-content">
            <Icon name="warning" size={18} />
            <span>
              {pendingConfirm.type === 'reject'
                ? '¿Rechazar el patch? El árbol no se modificará.'
                : pendingConfirm.type === 'revert'
                  ? '¿Revertir este cambio? Volverá al snapshot previo.'
                  : 'Marcar el patch como revisión CRIT. Se creará una nueva versión y se rechazará el patch actual. ¿Continuar?'}
            </span>
          </div>
          <div className="context-confirm-banner-actions">
            <button type="button" className="secondary-button compact" onClick={() => void resolvePendingConfirm(false)}>Cancelar</button>
            <button type="button" className="primary-button compact" autoFocus onClick={() => void resolvePendingConfirm(true)}>Confirmar</button>
          </div>
        </div>
      )}
      <header className="context-workbench-header">
        <div className="context-workbench-title">
          <p>{openTaskBranches.length} {openTaskBranches.length === 1 ? 'tarea abierta' : 'tareas abiertas'} · {pendingProposals.length} {pendingProposals.length === 1 ? 'mención por validar' : 'menciones por validar'}</p>
        </div>
        <nav className="context-workbench-tabs" aria-label="Vistas de contexto">
          {([['focus', 'Ahora', 'live'], ['tasks', 'Tareas', 'context'], ['library', 'Biblioteca', 'folder']] as const).map(([id, label, icon]) => <button type="button" key={id} className={workbenchView === id ? 'is-active' : ''} onClick={() => changeWorkbenchView(id)}><Icon name={icon} size={12} /> {label}{id === 'focus' && pendingProposals.length > 0 && <span>{pendingProposals.length}</span>}</button>)}
          <details className="context-workbench-more">
            <summary className={workbenchView === 'advanced' ? 'is-active' : ''}><Icon name="more" size={12} /> Más</summary>
            <button type="button" onClick={() => changeWorkbenchView('advanced')}><Icon name="tree" size={12} /> Configuración avanzada</button>
          </details>
        </nav>
      </header>
      {moduleNotice && (
        <div className={`context-collection-notice tone-${moduleNotice.tone}`} style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '12px 16px 0' }}>
          <Icon name={moduleNotice.tone === 'error' ? 'warning' : moduleNotice.tone === 'warning' ? 'alert' : 'check-circle'} size={12} />
          <span style={{ flex: 1 }}>{moduleNotice.message}</span>
          <button type="button" className="icon-only" aria-label="Cerrar aviso" onClick={clearModuleNotice}><Icon name="close" size={12} /></button>
        </div>
      )}
      {workbenchView === 'focus' ? (
      <main className="context-focus-view">
        <section className="context-focus-intro">
          <div><span className="surface-eyebrow">SIGUIENTE ACCIÓN</span><h2>{pendingProposals.length ? `${pendingProposals.length} menciones esperan tu validación` : 'Contexto al día'}</h2><p>{pendingProposals.length ? 'Valida, edita o convierte cada mención en una tarea sin abandonar esta pantalla.' : 'No hay propuestas pendientes. Puedes recopilar el chat o iniciar una tarea abierta.'}</p></div>
          <button type="button" className="secondary-button compact" onClick={openCollection}><Icon name="sparkle" size={12} /> Recopilar del chat</button>
        </section>

        <div className="context-focus-grid">
          <section className="context-focus-panel context-focus-review" aria-label="Menciones por validar">
            <header><div><span>POR VALIDAR</span><strong>Menciones detectadas</strong></div><b>{pendingProposals.length}</b></header>
            <div className="context-focus-list">
              {pendingProposals.length === 0 && <div className="context-focus-empty"><Icon name="verified" size={20} /><strong>No hay menciones pendientes</strong><span>Los cambios aceptados y descartados siguen disponibles en el historial.</span></div>}
              {pendingProposals.map((proposal) => (
                <article key={proposal.id} className="context-focus-item">
                  <div className="context-focus-item-copy">
                    <div><span className={`context-focus-risk risk-${proposal.riskLevel}`}>{proposal.riskLevel === 'low' ? 'Riesgo bajo' : proposal.riskLevel === 'medium' ? 'Riesgo medio' : proposal.riskLevel === 'high' ? 'Riesgo alto' : 'Crítico'}</span><small>{proposal.patch.operations.length} cambios</small></div>
                    <h3>{compactTaskTitle(proposal.title)}</h3>
                    <p>{proposal.reason || 'Propuesta de contexto sin explicación adicional.'}</p>
                    {proposal.metadata?.clarification && <blockquote><b>Pregunta</b>{proposal.metadata.clarification}</blockquote>}
                  </div>
                  <div className="context-focus-item-actions">
                    <button type="button" className="primary-button compact" onClick={() => void handleAcceptPatch(proposal.id)}><Icon name="check" size={11} /> Validar</button>
                    <button type="button" className="secondary-button compact" onClick={() => void startProposalTask(proposal)}><Icon name="pipeline" size={11} /> Iniciar tarea</button>
                    <button type="button" className="text-button" onClick={() => handleEditPatch(proposal.id)}>Editar</button>
                    <button type="button" className="text-button" onClick={() => void handleRejectPatch(proposal.id)}>Descartar</button>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="context-focus-panel context-focus-tasks" aria-label="Tareas de contexto">
            <header><div><span>TAREAS</span><strong>Trabajo disponible</strong></div><b>{openTaskBranches.length}</b></header>
            <div className="context-focus-new-task">
              <input aria-label="Nombre de la nueva tarea" value={newBranchTitle} onChange={(event) => setNewBranchTitle(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void createTaskBranch(); }} placeholder="Nueva tarea…" />
              <button type="button" className="secondary-button compact" onClick={() => void createTaskBranch()} disabled={!newBranchTitle.trim()}><Icon name="plus" size={11} /> Crear</button>
            </div>
            <div className="context-focus-list">
              {openTaskBranches.length === 0 && <div className="context-focus-empty"><Icon name="context" size={20} /><strong>No hay tareas abiertas</strong><span>Crea una aquí o recopila las mencionadas en la conversación.</span></div>}
              {openTaskBranches.slice(0, 2).map((branch) => (
                <article key={branch.id} className="context-focus-task">
                  <button type="button" className="context-focus-task-copy" onClick={() => { setSelectedBranchId(branch.id); changeWorkbenchView('tasks'); }}>
                    <span className="task-context-branch-dot" data-status={branch.status} />
                    <span><strong>{compactTaskTitle(branch.title)}</strong><small>{branchStatus(branch)}</small><p>{branch.summary || 'Sin resumen.'}</p></span>
                  </button>
                  <div><button type="button" className="secondary-button compact" onClick={() => void startBranchTask(branch)}><Icon name="pipeline" size={11} /> Iniciar</button><button type="button" className="text-button" onClick={() => { setSelectedBranchId(branch.id); changeWorkbenchView('tasks'); }}>Abrir</button></div>
                </article>
              ))}
              {openTaskBranches.length > 2 && <button type="button" className="context-focus-show-all" onClick={() => changeWorkbenchView('tasks')}>Ver todas las tareas ({openTaskBranches.length}) <Icon name="arrowRight" size={11} /></button>}
            </div>
          </section>
        </div>

        <details className="context-focus-history">
          <summary><span><Icon name="evidence" size={12} /> Historial y receipts</span><small>{ctx.receipts.length} registros</small></summary>
          <ContextActivityTray proposals={ctx.proposals} receipts={ctx.receipts} defaultOpen onAcceptPatch={(id) => void handleAcceptPatch(id)} onRejectPatch={(id) => void handleRejectPatch(id)} onRevertPatch={(id) => void handleRevertPatch(id)} onEditPatch={handleEditPatch} onOpenRelated={openRelated} onStartTask={(proposal) => void startProposalTask(proposal)} />
        </details>
      </main>
      ) : workbenchView === 'tasks' ? (
      <div className="task-context-layout">
        <aside className="task-context-branches" aria-label="Ramas de tareas">
          <div className="task-context-panel-heading"><strong>Tareas</strong><b>{taskBranches.length}</b></div>
          <div className="task-context-new-branch">
            <input aria-label="Nombre de la nueva tarea" value={newBranchTitle} onChange={(event) => setNewBranchTitle(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void createTaskBranch(); }} placeholder="Nueva tarea o rama…" />
            <button type="button" aria-label="Crear nueva rama" onClick={() => void createTaskBranch()} disabled={!newBranchTitle.trim()}><Icon name="plus" size={13} /></button>
          </div>
          <div className="task-context-filters">
            <select aria-label="Filtrar ramas" value={branchFilter} onChange={(event) => setBranchFilter(event.target.value as typeof branchFilter)}>
              {([['all', 'Todas'], ['open', 'Abiertas'], ['closed', 'Cerradas'], ['questions', 'Preguntas'], ['proposals', 'Propuestas'], ['errors', 'Alertas']] as const).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
          <div className="task-context-branch-list">
            {filteredBranches.length === 0 && <div className="task-context-inline-empty">No hay ramas en este filtro.</div>}
            {filteredBranches.map((branch) => {
              const count = flatNodes.filter((node) => node.id !== branch.id && (node.sourceRefs.some((ref) => ref.id === branch.id) || node.parentId === branch.id)).length;
              return <button key={branch.id} type="button" className={`task-context-branch ${selectedBranch?.id === branch.id ? 'is-selected' : ''}`} onClick={() => setSelectedBranchId(branch.id)}>
                <span className="task-context-branch-dot" data-status={branch.status} /><span className="task-context-branch-copy"><strong>{compactTaskTitle(branch.title)}</strong><small>{branchStatus(branch)} · {count} elementos</small></span><Icon name="chevron" size={12} />
              </button>;
            })}
          </div>
          <div className="task-context-sidebar-note"><Icon name="lock" size={12} /><span>El modelo puede proponer cambios, pero no añade nada sin tu permiso.</span></div>
        </aside>

        <main className="task-context-main">
          {!selectedBranch ? (
            <section className="task-context-empty-main"><Icon name="context" size={28} /><h2>Empieza por una rama de tarea</h2><p>Escribe el nombre en la columna izquierda o usa Recopilar contexto para detectar trabajo abierto en el chat.</p><div className="task-context-empty-actions"><button type="button" className="secondary-button" onClick={openChat}><Icon name="chat" size={12} /> Ir al chat</button><button type="button" className="primary-button" onClick={openCollection}><Icon name="sparkle" size={12} /> Recopilar contexto</button></div></section>
          ) : (
            <>
              <section className="task-context-task-head">
                <div><span className="task-context-status" data-status={selectedBranch.status}>{branchStatus(selectedBranch)}</span><h2>{compactTaskTitle(selectedBranch.title)}</h2><p>ID: {selectedBranch.id}</p></div>
                <div className="task-context-task-actions"><button type="button" className="secondary-button compact" onClick={openChat}><Icon name="chat" size={12} /> Ver conversación</button><button type="button" className="primary-button compact" onClick={openCollection}><Icon name="sparkle" size={12} /> Recopilar de esta tarea</button>{selectedBranch.status === 'canon' || selectedBranch.status === 'archived' ? <button type="button" className="secondary-button compact" onClick={() => void reopenSelectedTask()}><Icon name="refresh" size={12} /> Reabrir tarea</button> : <button type="button" className="secondary-button compact" onClick={() => setCloseOpen((value) => !value)}><Icon name="check" size={12} /> Cerrar tarea</button>}</div>
              </section>
              {closeOpen && selectedBranch.status !== 'canon' && selectedBranch.status !== 'archived' && <section className="task-context-close-form"><strong>Cerrar esta rama</strong><span>Escribe qué se ha resuelto. Quedará guardado como conclusión y podrás reabrirla después.</span><textarea aria-label="Conclusión de la tarea" value={closeNote} onChange={(event) => setCloseNote(event.target.value)} placeholder="Conclusión o evidencia de cierre…" rows={3} /><div><button type="button" className="secondary-button compact" onClick={() => { setCloseOpen(false); setCloseNote(''); }}>Cancelar</button><button type="button" className="primary-button compact" disabled={!closeNote.trim()} onClick={() => void closeSelectedTask()}><Icon name="check" size={12} /> Confirmar cierre</button></div></section>}
              <section className="task-context-grid">
                <div className="task-context-card task-context-card-wide"><div className="task-context-card-title"><span>CONTENIDO DE LA RAMA</span><b>{selectedBranchNodes.length} elementos</b></div>
                  {selectedBranchNodes.length === 0 ? <div className="task-context-card-empty">Aún no hay decisiones, pantallas, archivos o evidencias en esta rama.</div> : <div className="task-context-items">{selectedBranchNodes.map((node) => <article key={node.id} className="task-context-item"><span className="task-context-item-type">{node.type}</span><div><strong>{node.title}</strong><p>{node.summary || 'Sin resumen todavía.'}</p>{node.sourceRefs[0]?.path && <button type="button" className="task-context-link" onClick={() => props.onOpenInWorkspace?.(String(node.sourceRefs[0].path))}>Abrir origen</button>}</div><span className="task-context-item-status">{node.status}</span></article>)}</div>}
                </div>
                <div className="task-context-card"><div className="task-context-card-title"><span>PROPUESTAS PENDIENTES</span><b>{pendingProposals.length}</b></div>{pendingProposals.length === 0 ? <div className="task-context-card-empty">No hay propuestas esperando permiso.</div> : <div className="task-context-proposals">{pendingProposals.slice(0, 4).map((proposal) => <button key={proposal.id} type="button" className="task-context-proposal" onClick={() => { setCollectionProposal(proposal); setCollectionOpen(true); }}><Icon name="sparkle" size={13} /><span><strong>{compactTaskTitle(proposal.title)}</strong><small>{proposal.patch.operations.length} cambios · requiere revisión</small></span><Icon name="chevron" size={12} /></button>)}</div>}</div>
                <div className="task-context-card"><div className="task-context-card-title"><span>PREGUNTAS PENDIENTES</span><b>{pendingProposals.filter((proposal) => Boolean(proposal.metadata?.clarification)).length}</b></div>{pendingProposals.filter((proposal) => Boolean(proposal.metadata?.clarification)).length === 0 ? <div className="task-context-card-empty">No hay aclaraciones pendientes.</div> : <div className="task-context-question-list">{pendingProposals.filter((proposal) => Boolean(proposal.metadata?.clarification)).slice(0, 4).map((proposal) => <button key={proposal.id} type="button" className="task-context-question" onClick={() => { setCollectionProposal(proposal); setCollectionOpen(true); }}><span>?</span><div><strong>{proposal.metadata?.clarification}</strong><small>Responder revisando la propuesta</small></div></button>)}</div>}</div>
                <div className="task-context-card"><div className="task-context-card-title"><span>CHAT RECIENTE</span><b>{ctx.bank.history.length}</b></div>{recentChat.length === 0 ? <div className="task-context-card-empty">Todavía no hay conversación disponible.</div> : <div className="task-context-chat-list">{recentChat.map((item, index) => <div key={`${item.id}-${index}`}><span>{String(item.raw?.role || 'chat')}</span><p>{String(item.raw?.content || item.raw?.text || item.title || '').slice(0, 180)}</p></div>)}</div>}</div>
                <div className="task-context-card task-context-card-wide"><div className="task-context-card-title"><span>HISTORIAL DE LA RAMA</span><b>{ctx.receipts.filter((receipt) => !receipt.nodeId || receipt.nodeId === selectedBranch.id || selectedBranchNodes.some((node) => node.id === receipt.nodeId)).length}</b></div>{ctx.receipts.length === 0 ? <div className="task-context-card-empty">Aún no hay actividad registrada.</div> : <div className="task-context-timeline">{ctx.receipts.filter((receipt) => !receipt.nodeId || receipt.nodeId === selectedBranch.id || selectedBranchNodes.some((node) => node.id === receipt.nodeId)).slice(0, 12).map((receipt) => <div key={receipt.id} className="task-context-timeline-item"><span className="task-context-timeline-dot" /><div><strong>{receipt.summary}</strong><small>{new Date(receipt.createdAt).toLocaleString()} · {receipt.createdBy}</small></div></div>)}</div>}</div>
              </section>
            </>
          )}
        </main>
      </div>
      ) : workbenchView === 'library' ? (
        <div className="context-library-view">
        <nav className="context-category-tabs" aria-label="Categorías de contexto">
          {CONTEXT_CATEGORIES.map((category) => (
            <button key={category.id} type="button" className={activeContextView === category.id ? 'is-active' : ''} onClick={() => { setActiveContextView(category.id); setFocusedCategoryNodeId(null); }}>
              {category.label}<span>{flatNodes.filter((node) => node.type === category.id && node.status !== 'archived').length}</span>
            </button>
          ))}
        </nav>
        <section className="context-category-workspace" aria-label={`Contexto: ${activeCategory?.label || activeContextView}`}>
          {!focusedCategoryNodeId ? <ContextCategoryExplorer nodes={categoryNodes} mode={contextDisplayMode} onModeChange={changeContextDisplayMode} onOpen={openCategoryNode} onCreate={() => void createCategoryNode()} /> : <main className="context-category-editor context-focus-editor">
            <header className="context-focus-head">
              <button type="button" className="text-button" onClick={() => setFocusedCategoryNodeId(null)}><Icon name="arrowLeft" size={12} /> Volver</button>
              <span data-review={String(selectedReview?.status || 'pending')}><Icon name={selectedReview?.status === 'validated' ? 'verified' : selectedReview?.status === 'conflict' ? 'conflict' : 'sparkle'} size={12} /> {selectedReview?.status === 'validated' ? 'Validado por el modelo' : selectedReview?.status === 'conflict' ? 'Conflicto detectado' : selectedReview?.status === 'warning' ? 'Requiere atención' : selectedReview?.status === 'unavailable' ? 'Revisión no disponible' : 'Revisión pendiente'}</span>
            </header>
            {reviewNotice && <div className={`context-category-notice ${reviewingNodeId ? 'is-busy' : ''}`}><Icon name={reviewingNodeId ? 'refresh' : 'context'} size={12} /> {reviewNotice}</div>}
            {selectedNode && <div className="context-category-editor-grid">
              <ContextInspector
                node={selectedNode}
                relatedNodes={flatNodes}
                treeName={ctx.tree.name}
                packName={ctx.activePack?.name}
                packStatus={ctx.activePack?.status || null}
                packNodeCount={ctx.activePack?.nodeIds.length || 0}
                packConflicts={ctx.activePack?.conflicts || 0}
                onChange={() => undefined}
                onSave={(patch) => void saveAndReviewCategoryNode(patch)}
                onSelectRelated={openCategoryNode}
                onOpenInWorkspace={props.onOpenInWorkspace}
                onCreatePlan={(summary) => void handleCreatePlan(summary)}
                onOpenInChat={(text) => { writeWorkspaceStorageValue(props.workspaceRoot, 'chat-draft', text); openChat(); }}
                hideIdentity
                hideTitle={selectedNode?.parentId === ctx.tree.rootId && selectedNode?.title === activeCategory?.label}
              />
              <details className={`context-review-card status-${String(selectedReview?.status || 'pending')}`}>
                <summary><span><small>REVISIÓN DEL MODELO</small><strong>{selectedReview?.status === 'validated' ? 'Coherente' : selectedReview?.status === 'conflict' ? 'Conflicto detectado' : selectedReview?.status === 'warning' ? 'Requiere atención' : selectedReview?.status === 'unavailable' ? 'No disponible' : 'Pendiente'}</strong></span><Icon name="chevron" size={13} /></summary>
                {!selectedReview ? <p>Al guardar, BAGO conserva el contenido y consulta el modelo activo para detectar omisiones o contradicciones.</p> : <>
                  <p>{selectedReview.summary || 'Sin resumen de revisión.'}</p>
                  {(selectedReview.provider || selectedReview.model) && <small>{[selectedReview.provider, selectedReview.model].filter(Boolean).join(' · ')}</small>}
                  {reviewFindings.length > 0 && <ul>{reviewFindings.map((finding, index) => <li key={`${finding.field}-${index}`} data-severity={finding.severity}><strong>{finding.field}</strong><span>{finding.message}</span>{finding.suggestion && <small>{finding.suggestion}</small>}</li>)}</ul>}
                  {selectedReview.reviewedAt && <time>{new Date(selectedReview.reviewedAt).toLocaleString()}</time>}
                </>}
              </details>
            </div>}
          </main>}
        </section>
        </div>
      ) : (
        <FlowShell title="Flujo avanzado" subtitle="Fuentes → estructura → pack → compilación → destino" stages={flowStages} activeStage={activeStage} onStageChange={(stage) => { const next = stage as ContextFlowStage; if (!isStageLocked(next)) setActiveStage(next); }}>
          {activeStage === 'sources' && <ContextStageSources bank={ctx.bank} loading={ctx.bankLoading} treeNodes={flatNodes} onOpenRelatedNode={(id) => { openRelated(id); setActiveStage('structure'); }} sourceDirectories={ctx.sourceDirectories} sourceDirectoriesLoading={ctx.sourceDirectoriesLoading} onReloadBank={() => void refreshBank()} onAddToTree={(item) => void handleAddBankItem(item)} onAddToPack={(item) => void handleAddBankToPack(item)} onAddManualItem={async (path, kind) => { await ctx.addManualBankItem(path, kind); }} onRemoveManualItem={ctx.removeManualBankItem} onAddSourceDirectory={async (path) => { await ctx.addSourceDirectory(path); }} onRemoveSourceDirectory={ctx.removeSourceDirectory} onRefreshSourceDirectoryFiles={ctx.refreshSourceDirectoryFiles} onToggleSourceFileInclude={ctx.toggleSourceFileInclude} onSetSourceFileBranch={ctx.setSourceFileBranch} onLinkSourceDirectoryToTree={async (id) => { await ctx.linkSourceDirectoryToTree(id); }} />}
          {activeStage === 'structure' && <ContextStageStructure tree={ctx.tree} selectedNodeId={selectedNodeId} expanded={expanded} packNodeIds={ctx.activePack?.nodeIds || []} hasSelectedNode={Boolean(selectedNode)} onSelectNode={setSelectedNodeId} onToggleExpand={toggleExpand} onMoveNode={(id, parent) => void ctx.moveNode(id, parent)} onExcludeNode={(id) => void ctx.excludeNode(id)} onRestoreNode={(id) => void ctx.restoreNode(id)} onToggleCanon={(id) => void ctx.toggleCanon(id)} onAddChild={handleAddChild} onToggleInPack={(id) => void ctx.toggleNodeInPack(id)} onOpenInWorkspace={props.onOpenInWorkspace} onCopyId={handleCopyId} onOpenInspectorDrawer={() => setInspectorDrawerOpen(true)} onContinueToPack={() => setActiveStage('pack')} canContinueToPack={hasStructuredNodes} />}
          {activeStage === 'pack' && <ContextStagePack pack={ctx.activePack} packBlockedReason={packBlockedReason} packNodes={packNodes} selectableNodes={selectableNodes} onToggleNodeInPack={(id) => void ctx.toggleNodeInPack(id)} onCompile={() => void ctx.compileActivePack()} onSendToChat={() => void sendToChat()} onSendToPipeline={() => void sendToPipeline()} onShowCompiled={showCompiledRaw} onCopyPack={() => void copyPack()} />}
          {activeStage === 'compile' && <ContextStageCompile pack={ctx.activePack} proposals={ctx.proposals} receipts={ctx.receipts} compiledMarkdown={ctx.activePack?.markdown} onAcceptPatch={(id) => void handleAcceptPatch(id)} onRejectPatch={(id) => void handleRejectPatch(id)} onRevertPatch={(id) => void handleRevertPatch(id)} onEditPatch={handleEditPatch} onOpenRelated={openRelated} onCompile={() => void ctx.compileActivePack()} />}
          {activeStage === 'destination' && <ContextStageDestination pack={ctx.activePack} packBlockedReason={packBlockedReason} onCompile={() => void ctx.compileActivePack()} onSendToChat={() => void sendToChat()} onSendToPipeline={() => void sendToPipeline()} onShowCompiled={showCompiledRaw} onCopyPack={() => void copyPack()} />}
        </FlowShell>
      )}

      <ContextCollectionDialog open={collectionOpen} busy={collectionBusy} proposal={collectionProposal} sourceSummary={`${ctx.bank.history.length} mensajes del chat disponibles; se analizará el historial de esta tarea`} notice={collectionNotice} onClose={() => { if (!collectionBusy) setCollectionOpen(false); }} onCollect={collectFromChat} onAccept={acceptCollection} onAcceptOperations={acceptCollectionOperations} onReject={rejectCollection} />
      {editingPatch && <ContextPatchPreview patch={editingPatch} onCancel={() => setEditingPatch(null)} onApply={(operations) => void handleApplyEdited(operations)} />}
      <Drawer open={inspectorDrawerOpen} title="Inspector de contexto" subtitle={selectedNode?.title} onClose={() => setInspectorDrawerOpen(false)}>
        <ContextInspector node={selectedNode} relatedNodes={flatNodes} treeName={ctx.tree.name} packName={ctx.activePack?.name} packStatus={ctx.activePack?.status || null} packNodeCount={packNodeCount} packConflicts={ctx.activePack?.conflicts || 0} onChange={() => undefined} onSave={(patch) => void handleSaveNode(patch)} onSelectRelated={openRelated} onOpenInWorkspace={props.onOpenInWorkspace} onCreatePlan={(summary) => void handleCreatePlan(summary)} onOpenInChat={(text) => { writeWorkspaceStorageValue(props.workspaceRoot, 'chat-draft', text); openChat(); }} />
      </Drawer>
      {newChildDraft && <div className="task-context-dialog-backdrop" role="dialog" aria-modal="true" aria-label="Crear nodo"><section className="task-context-dialog context-compact-dialog"><header className="task-context-dialog-header"><div><span className="surface-eyebrow">Estructura</span><h3>Crear nodo hijo</h3></div><button type="button" className="task-context-close" onClick={() => setNewChildDraft(null)}><Icon name="close" size={12} /></button></header><label className="first-run-field"><span>Título</span><input autoFocus value={newChildDraft.title} onChange={(event) => setNewChildDraft({ ...newChildDraft, title: event.target.value })} onKeyDown={(event) => { if (event.key === 'Enter') void submitNewChild(); }} /></label><div className="task-context-dialog-actions"><button type="button" className="secondary-button compact" onClick={() => setNewChildDraft(null)}>Cancelar</button><button type="button" className="primary-button compact" disabled={!newChildDraft.title.trim()} onClick={() => void submitNewChild()}>Crear</button></div></section></div>}
      {compiledModal && <div className="task-context-dialog-backdrop" role="dialog" aria-modal="true" aria-label="Pack compilado"><section className="task-context-dialog context-compiled-dialog"><header className="task-context-dialog-header"><div><span className="surface-eyebrow">Pack compilado</span><h3>{ctx.activePack?.name}</h3></div><button type="button" className="task-context-close" onClick={() => setCompiledModal(null)}><Icon name="close" size={12} /></button></header><pre className="context-compiled-markdown">{compiledModal}</pre><div className="task-context-dialog-actions"><button type="button" className="secondary-button compact" onClick={() => void copyPack()} disabled={exportingPack}>Copiar</button><button type="button" className="primary-button compact" onClick={() => setCompiledModal(null)}>Cerrar</button></div></section></div>}
    </div>
  );
}

export function buildContextSelection(node: ContextNode): SelectionRecord {
  return {
    id: node.id,
    kind: 'context-tree-node',
    targetKind: 'context.item' as ContextTargetKind,
    title: node.title,
    summary: node.summary,
    detail: [
      `type: ${node.type}`,
      `status: ${node.status}`,
      `priority: ${node.priority}`,
      `weight: ${typeof node.weightTokens === 'number' ? `${node.weightTokens}t` : 'unknown'}`
    ],
    raw: safeJson(node)
  };
}
