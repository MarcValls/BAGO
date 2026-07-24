// ContextTreeModule: componente raíz del módulo de arquitectura de
// contexto. Junta Toolbar + Banco + Canvas + Inspector + Bandeja +
// Pack bar. Reemplaza la antigua pantalla pasiva de métricas.
import { useEffect, useMemo, useState } from 'react';
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
import { ContextPatchPreview } from './ContextPatchPreview';
import { ContextCollectionDialog } from './ContextCollectionDialog';
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
import { BagoClient, safeJson } from '@/api/client';
import {
  buildCollectionPrompt,
  collectionOperationToPatch,
  parseStructuredCollection,
  type CollectionHistoryItem
} from './contextCollection';

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

export function ContextTreeModule(props: Props) {
  const ctx = props.ctx;
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
  }, [ctx.tree?.id, ctx.ready, props.bankPending?.length]);

  const selectedNode = useMemo(() => {
    if (!selectedNodeId || !ctx.tree) return null;
    return ctx.tree.nodes[selectedNodeId] || null;
  }, [ctx.tree, selectedNodeId]);

  const flatNodes = useMemo(() => ctx.tree ? Object.values(ctx.tree.nodes) : [], [ctx.tree]);

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

  const handleCreatePlan = async (summary: string) => {
    await props.onCreatePlan('Tarea desde Árbol de Contexto', summary);
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
      const treePaths = Object.values(ctx.tree.nodes)
        .filter((node) => node.parentId && node.status !== 'archived')
        .map((node) => node.title)
        .slice(0, 100);
      const historyText = history.length ? `${history.length} mensajes completos` : 'No hay mensajes disponibles en el historial.';
      let modelText = '';
      let structured = null;
      let modelError = '';
      try {
        const collector = new BagoClient(props.apiBase, props.apiToken);
        const response = await collector.sendChat(buildCollectionPrompt(question, history, treePaths));
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
      const fallbackArea = fallbackUi ? 'UI' : 'Tarea activa';
      const fallbackOperations = [{
        op: 'create' as const,
        parent_path: fallbackUi ? ['UI', 'Pantallas'] : ['Tarea activa'],
        type: 'pending' as const,
        title: fallbackUi ? 'Pantalla o tarea detectada en el chat' : 'Contexto recopilado del chat',
        summary: history.map((item) => item.text).join(' ').slice(0, 320),
        priority: 'medium' as const
      }];
      const proposalData = structured || {
        summary: historyText,
        clarification: question.trim() || 'Confirma si la rama y la tarea detectadas representan correctamente el trabajo actual.',
        operations: fallbackOperations
      };
      const operations: ContextPatchOp[] = [];
      const nodeByPath = new Map<string, string>();
      for (const node of Object.values(ctx.tree.nodes)) {
        const segments: string[] = [];
        let current: typeof node | undefined = node;
        while (current && current.parentId) {
          segments.unshift(current.title);
          current = ctx.tree.nodes[current.parentId];
        }
        if (segments.length) nodeByPath.set(segments.join('/').toLowerCase(), node.id);
      }
      for (const [index, operation] of proposalData.operations.entries()) {
        const path = (operation.parent_path || []).map((part) => String(part).trim()).filter(Boolean).slice(0, 5);
        let parentId = ctx.tree.rootId;
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
      window.alert(result.error || 'No se pudo aplicar la propuesta.');
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

  const handleCopyId = (id: string) => {
    navigator.clipboard?.writeText(id);
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
      window.alert(result.error);
    }
  };
  const handleRejectPatch = async (patchId: string) => {
    if (!window.confirm('¿Rechazar el patch? El árbol no se modificará.')) return;
    await ctx.rejectPatch(patchId);
  };
  const handleEditPatch = (patchId: string) => {
    const patch = ctx.proposals.find((p) => p.id === patchId);
    if (patch) setEditingPatch(patch);
  };
  const handleApplyEdited = async (operations: ContextPatchOp[]) => {
    if (!editingPatch) return;
    const result = await ctx.applyPatchedEdited(editingPatch.id, operations);
    if (!result.ok) {
      window.alert(result.error || 'No se pudo aplicar el patch.');
    }
    setEditingPatch(null);
  };
  const handleRevertPatch = async (patchId: string) => {
    if (!window.confirm('¿Revertir este cambio? Volverá al snapshot previo.')) return;
    const result = await ctx.revertPatch(patchId);
    if (!result.ok && result.error) {
      window.alert(result.error);
    }
  };
  const handleOpenInTree = (patchId: string) => {
    const patch = ctx.proposals.find((p) => p.id === patchId);
    if (!patch) return;
    if (patch.targetNodeId) {
      openRelated(patch.targetNodeId);
    }
  };
  const handleReviewPatch = (patchId: string) => {
    if (!window.confirm('Marcar el patch como revisión CRIT. Se creará una nueva versión y se rechazará el patch actual. ¿Continuar?')) return;
    // Para CRIT: no aplicamos. Sugerimos crear nueva versión (no-op por ahora).
    void ctx.rejectPatch(patchId);
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

  useEffect(() => {
    if (stageIndex(activeStage) < stageIndex(nextStage)) {
      setActiveStage(nextStage);
    }
  }, [activeStage, nextStage]);

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

  if (ctx.error) {
    return (
      <div className="context-tree-module" data-error="true">
        <div className="context-tree-error">
          <Icon name="warning" size={20} />
          <h3>No se pudo cargar el árbol de contexto</h3>
          <p>{ctx.error}</p>
          <button type="button" className="primary-button compact" onClick={() => void ctx.refresh()}>
            <Icon name="refresh" size={12} /> Reintentar
          </button>
        </div>
      </div>
    );
  }

  if (!ctx.ready) {
    return (
      <div className="context-tree-module" data-loading="true">
        <div className="context-tree-loading">
          <Icon name="refresh" size={18} />
          <p>Cargando árbol de contexto…</p>
        </div>
      </div>
    );
  }

  if (!ctx.tree) {
    return (
      <div className="context-tree-module">
        <div className="context-tree-empty">
          <Icon name="tree" size={28} />
          <h3>No hay árbol de contexto para este workspace</h3>
          <p>Empieza creando un árbol con la estructura recomendada: intención, fuentes, decisiones, reglas, riesgos, pendientes, evidencias, actividad del chat y pack.</p>
          <button type="button" className="primary-button" onClick={() => void ctx.createDefaultTree()}>
            <Icon name="plus" size={12} /> Crear árbol
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="context-tree-module">
      <div className="context-collection-toolbar">
        <div>
          <strong>Contexto vivo del proyecto</strong>
          <span>Las tareas permanecen abiertas como ramas hasta que se cierran con evidencia.</span>
        </div>
        <button type="button" className="primary-button compact" onClick={openCollection}>
          <Icon name="sparkle" size={12} /> Recopilar contexto
        </button>
      </div>
      <FlowShell
        title="Flujo"
        subtitle={`Paso recomendado: ${FLOW_STAGES.find((item) => item.id === nextStage)?.label || 'Fuentes'}`}
        stages={flowStages}
        activeStage={activeStage}
        onStageChange={(stageId) => setActiveStage(stageId as ContextFlowStage)}
      >
        {activeStage === 'sources' && (
          <ContextStageSources
            bank={ctx.bank}
            loading={ctx.bankLoading}
            treeNodes={flatNodes}
            onOpenRelatedNode={openRelated}
            sourceDirectories={ctx.sourceDirectories}
            sourceDirectoriesLoading={ctx.sourceDirectoriesLoading}
            onReloadBank={() => void refreshBank()}
            onAddToTree={(item) => void handleAddBankItem(item)}
            onAddToPack={(item) => void handleAddBankToPack(item)}
            onAddManualItem={async (path, kind) => { await ctx.addManualBankItem(path, kind); }}
            onRemoveManualItem={async (id) => { await ctx.removeManualBankItem(id); }}
            onAddSourceDirectory={async (path) => { await ctx.addSourceDirectory(path); }}
            onRemoveSourceDirectory={async (id) => { await ctx.removeSourceDirectory(id); }}
            onRefreshSourceDirectoryFiles={async (id) => { await ctx.refreshSourceDirectoryFiles(id); }}
            onToggleSourceFileInclude={async (id, filePath, include) => { await ctx.toggleSourceFileInclude(id, filePath, include); }}
            onSetSourceFileBranch={async (id, filePath, branch) => { await ctx.setSourceFileBranch(id, filePath, branch); }}
            onLinkSourceDirectoryToTree={async (id) => { await ctx.linkSourceDirectoryToTree(id); }}
          />
        )}

        {activeStage === 'structure' && (
          <ContextStageStructure
            tree={ctx.tree}
            selectedNodeId={selectedNodeId}
            expanded={expanded}
            packNodeIds={ctx.activePack?.nodeIds || []}
            hasSelectedNode={Boolean(selectedNode)}
            onSelectNode={setSelectedNodeId}
            onToggleExpand={toggleExpand}
            onMoveNode={(nodeId, newParentId) => void ctx.moveNode(nodeId, newParentId)}
            onExcludeNode={(nodeId) => void ctx.excludeNode(nodeId)}
            onRestoreNode={(nodeId) => void ctx.restoreNode(nodeId)}
            onToggleCanon={(nodeId) => void ctx.toggleCanon(nodeId)}
            onAddChild={handleAddChild}
            onToggleInPack={(nodeId) => void ctx.toggleNodeInPack(nodeId)}
            onOpenInWorkspace={props.onOpenInWorkspace}
            onCopyId={handleCopyId}
            onOpenInspectorDrawer={() => setInspectorDrawerOpen(true)}
            onContinueToPack={() => setActiveStage('pack')}
            canContinueToPack={hasStructuredNodes}
          />
        )}

        {activeStage === 'pack' && (
          <ContextStagePack
            pack={ctx.activePack}
            packBlockedReason={packBlockedReason}
            packNodes={packNodes}
            selectableNodes={selectableNodes}
            onToggleNodeInPack={(nodeId) => void ctx.toggleNodeInPack(nodeId)}
            onCompile={() => void ctx.compileActivePack()}
            onSendToChat={() => void sendToChat()}
            onSendToPipeline={() => void sendToPipeline()}
            onShowCompiled={showCompiledRaw}
            onCopyPack={() => void copyPack()}
          />
        )}

        {activeStage === 'compile' && (
          <ContextStageCompile
            pack={ctx.activePack}
            proposals={ctx.proposals}
            receipts={ctx.receipts}
            compiledMarkdown={ctx.activePack?.markdown || null}
            onAcceptPatch={(id) => void handleAcceptPatch(id)}
            onRejectPatch={(id) => void handleRejectPatch(id)}
            onRevertPatch={(id) => void handleRevertPatch(id)}
            onEditPatch={handleEditPatch}
            onOpenRelated={openRelated}
            onClear={() => {
              if (window.confirm('¿Cerrar los patches resueltos de la bandeja? Se mantienen en disco.')) {
                // No eliminamos nada: solo colapsamos la bandeja.
              }
            }}
            onCompile={() => void ctx.compileActivePack()}
          />
        )}

        {activeStage === 'destination' && (
          <ContextStageDestination
            pack={ctx.activePack}
            packBlockedReason={packBlockedReason}
            onCompile={() => void ctx.compileActivePack()}
            onSendToChat={() => void sendToChat()}
            onSendToPipeline={() => void sendToPipeline()}
            onShowCompiled={showCompiledRaw}
            onCopyPack={() => void copyPack()}
          />
        )}
      </FlowShell>

      <Drawer
        open={inspectorDrawerOpen && Boolean(selectedNode)}
        onClose={() => setInspectorDrawerOpen(false)}
        title={selectedNode?.title || 'Inspector'}
        subtitle={selectedNode?.summary || 'Selecciona un nodo para ver el detalle.'}
        width={520}
      >
        <ContextInspector
          node={selectedNode}
          relatedNodes={flatNodes}
          treeName={ctx.tree?.name}
          packName={ctx.activePack?.name}
          packStatus={ctx.activePack?.status || null}
          packNodeCount={ctx.activePack?.nodeIds.length}
          packConflicts={ctx.activePack?.conflicts}
          onChange={() => undefined}
          onSave={handleSaveNode}
          onSelectRelated={openRelated}
          onOpenInWorkspace={props.onOpenInWorkspace}
          onCreatePlan={handleCreatePlan}
          onOpenInChat={(text) => props.onRunContextCommand(text)}
          onCreateTree={async () => { await ctx.createDefaultTree(); }}
          onCompilePack={async () => { await ctx.compileActivePack(); }}
        />
      </Drawer>

      {editingPatch && (
        <div className="context-patch-preview-backdrop" role="presentation">
          <ContextPatchPreview
            patch={editingPatch}
            onCancel={() => setEditingPatch(null)}
            onApply={(ops) => void handleApplyEdited(ops)}
          />
        </div>
      )}

      {newChildDraft && (
        <div className="context-patch-preview-backdrop" role="presentation">
          <div className="context-patch-preview" role="dialog" aria-modal="true" aria-label="Añadir nodo hijo">
            <header className="context-patch-preview-header">
              <h3><Icon name="plus" size={14} /> Añadir nodo hijo</h3>
              <button type="button" className="icon-button" onClick={() => setNewChildDraft(null)} aria-label="Cerrar">
                <Icon name="close" size={14} />
              </button>
            </header>
            <p className="context-patch-preview-hint">
              El nuevo nodo se creará dentro de la rama seleccionada con el tipo por defecto.
            </p>
            <div className="context-new-child-form">
              <label>
                <small>Tipo</small>
                <select
                  value={newChildDraft.type}
                  onChange={(event) => setNewChildDraft({ ...newChildDraft, type: event.target.value as ContextNodeType })}
                >
                  {ROOT_TYPES.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              </label>
              <label>
                <small>Título</small>
                <input
                  autoFocus
                  value={newChildDraft.title}
                  onChange={(event) => setNewChildDraft({ ...newChildDraft, title: event.target.value })}
                  onKeyDown={(event) => { if (event.key === 'Enter') void submitNewChild(); }}
                  placeholder="Nombre del nodo"
                />
              </label>
            </div>
            <footer className="context-patch-preview-actions">
              <button type="button" className="secondary-button" onClick={() => setNewChildDraft(null)}>Cancelar</button>
              <button type="button" className="primary-button" onClick={() => void submitNewChild()}>
                <Icon name="check" size={12} /> Crear nodo
              </button>
            </footer>
          </div>
        </div>
      )}

      {compiledModal && (
        <div className="context-patch-preview-backdrop" role="presentation" onClick={() => setCompiledModal(null)}>
          <div className="context-patch-preview context-compiled-modal" role="dialog" aria-modal="true" aria-label="Pack compilado" onClick={(event) => event.stopPropagation()}>
            <header className="context-patch-preview-header">
              <h3><Icon name="pack" size={14} /> Pack compilado</h3>
              <button type="button" className="icon-button" onClick={() => setCompiledModal(null)} aria-label="Cerrar">
                <Icon name="close" size={14} />
              </button>
            </header>
            <pre className="context-compiled-markdown">{compiledModal}</pre>
          </div>
        </div>
      )}

      <ContextCollectionDialog
        open={collectionOpen}
        busy={collectionBusy}
        proposal={collectionProposal}
        sourceSummary={`${ctx.bank.history.length} mensajes del historial disponibles; se envía el contenido completo acotado para la propuesta`}
        notice={collectionNotice}
        onClose={() => { if (!collectionBusy) setCollectionOpen(false); }}
        onCollect={collectFromChat}
        onAccept={acceptCollection}
        onReject={rejectCollection}
      />
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
