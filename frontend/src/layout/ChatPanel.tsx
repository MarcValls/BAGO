import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent as ReactMouseEvent } from 'react';
import type {
  ActiveSection,
  BackendRouterEntry,
  BackendHistory,
  BackendConversations,
  ChatMode,
  ChatTurn,
  ContextTargetKind,
  InspectorLevel,
  SelectionRecord,
  UiBootstrapSnapshot,
  BackendCommandResult
} from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { quietStatus } from '@/shared/quiet-status';
import { friendlyErrorMessage } from '@/shared/friendly-error';
import { ContextPatchValidationCard } from '@/features/context-tree/ContextPatchValidationCard';
import type { ContextPatchRequest } from '@/features/context-tree/contextTreeTypes';
import { buildChatModelOptions } from '@/layout/chatModelOptions';
import { groupTechnicalTurns, presentChatTurn } from '@/shared/chatPresentation';

export interface ContextPatchDisplay {
  patch: ContextPatchRequest;
  turnId: string;
  status: 'pending' | 'accepted' | 'rejected' | 'edited' | 'failed' | 'reverted' | 'review_requested';
  errorMessage?: string;
  appliedAt?: string;
  receiptId?: string;
}

interface Props {
  snapshot: UiBootstrapSnapshot | null;
  turns: ChatTurn[];
  drafts: Record<string, string>;
  chatMode: ChatMode;
  history: BackendHistory | null;
  conversations: BackendConversations | null;
  canChat: boolean;
  routerEntries: BackendRouterEntry[];
  sessionModel: string | null;
  activeProvider: string | null;
  activeModels: Set<string>;
  onSetChatMode: (mode: ChatMode) => void;
  onDraftChange: (key: string, text: string) => void;
  onSendChat: (message: string) => Promise<void>;
  onInspect: (eventOrSelection: SelectionRecord | ReactMouseEvent<HTMLElement>, hint?: InspectorLevel | { x: number; y: number }) => void;
  onRunCommand: (command: string) => Promise<BackendCommandResult | null>;
  onRunContextCommand: (command: string) => Promise<void>;
  onNavigate: (section: ActiveSection) => void;
  onSetSessionModel: (modelKey: string | null) => Promise<void>;
  reasoningDepth: string;
  onSetReasoningDepth: (depth: string) => Promise<void>;
  // CANON[CTX-011]: patches del árbol de contexto que aparecieron
  // en cada turno del chat. El panel los muestra como tarjeta inline
  // para validación. Las acciones se delegan al módulo de contexto.
  contextPatches?: ContextPatchDisplay[];
  onAcceptContextPatch?: (patchId: string) => void;
  onRejectContextPatch?: (patchId: string) => void;
  onEditContextPatch?: (patchId: string) => void;
  onRevertContextPatch?: (patchId: string) => void;
  onReviewContextPatch?: (patchId: string) => void;
  onOpenContextInTree?: (patchId: string) => void;
  startScreen?: boolean;
  recentProjects?: Array<{ id: string; title: string; summary: string; updatedAt: string; status: string }>;
  onStartNew?: () => void;
  onContinue?: () => void;
  onChooseRecent?: (id: string) => void;
  onRefresh?: () => void;
  onCreateConversation?: () => Promise<void>;
  onSwitchConversation?: (conversationId: string) => Promise<void>;
  onRenameConversation?: (conversationId: string, title: string) => Promise<void>;
  onArchiveConversation?: (conversationId: string) => Promise<void>;
  // CANON[CHAT-DOCK]: cuando se monta dentro del dock lateral (junto
  // a otra sección) `isDocked` deshabilita el start screen, oculta
  // tabs contextuales y reduce padding. Sin esta prop el panel se
  // comporta como pantalla completa.
  isDocked?: boolean;
}

function summarize(message: Record<string, unknown>): string {
  return String(message.content || message.text || message.message || '').trim();
}

function statusTone(status: string): string {
  const value = status.toLowerCase();
  if (['done', 'confirmed', 'valid', 'certified', 'ok'].some((e) => value.includes(e))) return 'confirmed';
  if (['running', 'pending', 'loading', 'partial', 'stale'].some((e) => value.includes(e))) return 'running';
  if (['failed', 'error', 'invalid', 'rejected'].some((e) => value.includes(e))) return 'error';
  if (['blocked', 'missing', 'legacy', 'needs_confirmation'].some((e) => value.includes(e))) return 'blocked';
  return 'unknown';
}

function StatusBadge({ status }: { status: string }) {
  const text = quietStatus(status);
  if (!text) {
    return <span className={`status-badge state-${statusTone(status)}`}><span className="status-dot" /></span>;
  }
  return (
    <span className={`status-badge state-${statusTone(status)}`}>
      <span className="status-dot" />
      {text}
    </span>
  );
}


function openContextMenuFromElement(event: ReactMouseEvent<HTMLElement>, selection: SelectionRecord, onInspect: Props['onInspect']) {
  event.preventDefault();
  event.stopPropagation();
  onInspect(selection, { x: event.clientX, y: event.clientY });
}

function inspectMenuAttrs(selection: SelectionRecord, onInspect: Props['onInspect']) {
  return {
    onContextMenu: (event: ReactMouseEvent<HTMLElement>) => openContextMenuFromElement(event, selection, onInspect),
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if ((event.shiftKey && event.key === 'F10') || event.key === 'ContextMenu') {
        event.preventDefault();
        event.stopPropagation();
        const rect = event.currentTarget.getBoundingClientRect();
        onInspect(selection, { x: rect.left + 12, y: rect.bottom + 6 });
      }
    },
    'aria-haspopup': 'dialog' as const,
    title: 'Abrir acciones para este mensaje'
  };
}

interface TurnArticleProps {
  turn: ChatTurn;
  contextPatches: ContextPatchDisplay[];
  onInspect: Props['onInspect'];
  onSendChat: Props['onSendChat'];
  onAcceptContextPatch?: Props['onAcceptContextPatch'];
  onRejectContextPatch?: Props['onRejectContextPatch'];
  onEditContextPatch?: Props['onEditContextPatch'];
  onRevertContextPatch?: Props['onRevertContextPatch'];
  onReviewContextPatch?: Props['onReviewContextPatch'];
  onOpenContextInTree?: Props['onOpenContextInTree'];
  onNavigate: Props['onNavigate'];
}

type TechnicalPresentation = Extract<ReturnType<typeof presentChatTurn>, { kind: 'activity' | 'error' }>;

function TurnArticle(props: TurnArticleProps) {
  const { turn } = props;
  const turnSelection: SelectionRecord = {
    id: turn.id,
    kind: 'chat-turn',
    targetKind: 'screen.chat' as ContextTargetKind,
    title: turn.role === 'user' ? 'Mensaje del usuario' : turn.role === 'command' ? 'Comando' : 'Respuesta de BAGO',
    summary: turn.text.slice(0, 240),
    detail: [
      `status: ${turn.status || 'done'}`,
      `timestamp: ${turn.timestamp}`,
      `receipt: ${turn.receipt ? 'available' : 'none'}`,
      `provider: ${turn.provider || 'unknown'}`,
      `model: ${turn.model || 'unknown'}`
    ],
    raw: turn.raw || turn
  };
  const turnPatches = props.contextPatches.filter((entry) => entry.turnId === turn.id);
  const clarificationOptions = Array.isArray(turn.clarification?.options)
    ? turn.clarification.options as Array<Record<string, unknown>>
    : [];

  return <article
    className={`chat-message role-${turn.role} status-${turn.status || 'done'}`}
    {...inspectMenuAttrs(turnSelection, props.onInspect)}
    onClick={() => props.onInspect(turnSelection)}
  >
    <div className="message-avatar">{turn.role === 'user' ? 'TÚ' : turn.role === 'command' ? '/' : 'B'}</div>
    <div className="message-body">
      <div className="message-meta">
        <strong>{turn.role === 'user' ? 'Tú' : turn.role === 'command' ? 'Comando' : 'BAGO'}</strong>
        <span>{new Date(turn.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        {turn.role === 'assistant' && (turn.provider || turn.model) && <span>{[turn.provider, turn.model].filter(Boolean).join(' · ')}</span>}
        {turn.status && <StatusBadge status={turn.status} />}
      </div>
      <div className="message-text">{turn.text || (turn.status === 'running' ? '...' : '')}</div>
      {clarificationOptions.length > 0 && <div className="message-patches" onClick={(event) => event.stopPropagation()}>
        {clarificationOptions.map((option, index) => <button
          key={String(option.id || index)}
          type="button"
          className="secondary-button compact"
          onClick={() => void props.onSendChat(`${String(option.prefix || option.label || '').trim()}: ${String(turn.clarification?.original || '').trim()}`)}
        >{String(option.label || option.id || 'Continuar')}</button>)}
      </div>}
      {turnPatches.length > 0 && <div className="message-patches" onClick={(event) => event.stopPropagation()}>
        {turnPatches.map((entry) => <ContextPatchValidationCard
          key={entry.patch.id}
          patch={entry.patch}
          status={entry.status}
          errorMessage={entry.errorMessage}
          appliedAt={entry.appliedAt}
          receiptId={entry.receiptId}
          onAccept={(id) => props.onAcceptContextPatch?.(id)}
          onReject={(id) => props.onRejectContextPatch?.(id)}
          onEdit={(id) => props.onEditContextPatch?.(id)}
          onRevert={(id) => props.onRevertContextPatch?.(id)}
          onReview={(id) => props.onReviewContextPatch?.(id)}
          onOpenInTree={(id) => { props.onOpenContextInTree?.(id); props.onNavigate('context'); }}
        />)}
      </div>}
    </div>
  </article>;
}

export function ChatPanel(props: Props) {
  const [modelChanging, setModelChanging] = useState(false);
  const [modelError, setModelError] = useState('');
  const [modelQuery, setModelQuery] = useState('');
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [modelPickerPos, setModelPickerPos] = useState<{ top: number; right: number; maxHeight: number } | null>(null);
  const modelPickerRootRef = useRef<HTMLDivElement>(null);
  const [reasoningChanging, setReasoningChanging] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(Boolean(props.startScreen && !props.isDocked));
  const [conversationBusy, setConversationBusy] = useState('');
  const [conversationError, setConversationError] = useState('');
  const [renamingId, setRenamingId] = useState('');
  const [renameTitle, setRenameTitle] = useState('');
  const timelineRef = useRef<HTMLElement>(null);
  const draft = props.drafts.chat || '';
  const canChat = props.canChat;
  const historyMessages = Array.isArray(props.history?.messages) ? props.history.messages : [];
  const modelOptions = useMemo(
    () => buildChatModelOptions(props.routerEntries, props.activeProvider, props.activeModels, props.sessionModel),
    [props.routerEntries, props.activeProvider, props.activeModels, props.sessionModel]
  );
  const timelineGroups = useMemo(() => groupTechnicalTurns(props.turns), [props.turns]);
  const filteredModelOptions = useMemo(() => {
    const query = modelQuery.trim().toLocaleLowerCase();
    return query ? modelOptions.filter((option) => `${option.provider} ${option.model} ${option.key}`.toLocaleLowerCase().includes(query)) : modelOptions;
  }, [modelOptions, modelQuery]);
  const modelProviders = useMemo(() => Array.from(new Set(filteredModelOptions.map((option) => option.provider))), [filteredModelOptions]);
  const currentModel = modelOptions.find((option) => option.key === props.sessionModel) || null;
  const automaticModel = [props.activeProvider, props.snapshot?.model.effectiveModel || props.snapshot?.model.configuredModel].filter(Boolean).join('/') || 'router del sistema';
  const showWelcome = welcomeOpen;
  const conversationItems = props.conversations?.conversations || [];
  const activeConversationId = props.conversations?.active_conversation_id || props.history?.conversation_id || '';
  const activeConversation = conversationItems.find((item) => item.conversation_id === activeConversationId) || null;
  useEffect(() => {
    if (timelineRef.current) timelineRef.current.scrollTop = 0;
  }, [props.history?.conversation_id]);

  const closeModelPicker = useCallback(() => {
    setModelPickerOpen(false);
    setModelPickerPos(null);
    setModelQuery('');
  }, []);

  const openModelPicker = useCallback((event: ReactMouseEvent<HTMLElement>) => {
    if (modelChanging) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const spaceAbove = rect.top - 16;
    const spaceBelow = window.innerHeight - rect.bottom - 16;
    const openAbove = spaceAbove >= spaceBelow || spaceAbove >= 200;
    const maxHeight = Math.min(430, Math.max(200, openAbove ? spaceAbove : spaceBelow));
    setModelPickerPos({
      top: openAbove ? Math.max(8, rect.top - maxHeight - 6) : rect.bottom + 6,
      right: Math.max(8, window.innerWidth - rect.right),
      maxHeight
    });
    setModelPickerOpen((current) => !current);
  }, [modelChanging]);

  useEffect(() => {
    if (!modelPickerOpen) return;
    const close = (event: MouseEvent) => {
      if (!modelPickerRootRef.current?.contains(event.target as Node)) closeModelPicker();
    };
    const closeForViewportChange = () => closeModelPicker();
    document.addEventListener('mousedown', close);
    window.addEventListener('resize', closeForViewportChange);
    window.addEventListener('scroll', closeForViewportChange, true);
    return () => {
      document.removeEventListener('mousedown', close);
      window.removeEventListener('resize', closeForViewportChange);
      window.removeEventListener('scroll', closeForViewportChange, true);
    };
  }, [closeModelPicker, modelPickerOpen]);
  const chatSelection: SelectionRecord = {
    id: 'screen-chat',
    kind: 'screen-chat',
    targetKind: 'screen.chat' as ContextTargetKind,
    title: 'Chat',
    summary: `${props.turns.length} turnos · ${props.canChat ? 'autorizado' : 'bloqueado'}`,
    detail: [
      `mode: ${props.chatMode}`,
      `session model: ${props.sessionModel || 'auto'}`
    ],
    raw: { turns: props.turns, draft, mode: props.chatMode }
  };

  const onComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (canChat && draft.trim()) void props.onSendChat(draft);
    }
  };

  const onModelChange = async (nextModel: string | null) => {
    setModelChanging(true);
    setModelError('');
    try {
      await props.onSetSessionModel(nextModel);
    } catch (error) {
      setModelError(friendlyErrorMessage(error, 'No se pudo cambiar el modelo'));
    } finally {
      setModelChanging(false);
    }
  };

  const onReasoningChange = async (depth: string) => {
    setReasoningChanging(true);
    setModelError('');
    try {
      await props.onSetReasoningDepth(depth);
    } catch (error) {
      setModelError(friendlyErrorMessage(error, 'No se pudo cambiar la profundidad'));
    } finally {
      setReasoningChanging(false);
    }
  };

  const runConversationAction = async (key: string, action: () => Promise<void>) => {
    setConversationBusy(key);
    setConversationError('');
    try {
      await action();
      setWelcomeOpen(false);
    } catch (error) {
      setConversationError(friendlyErrorMessage(error, 'No se pudo actualizar la conversación.'));
    } finally {
      setConversationBusy('');
    }
  };

  return (
    <div className={`chat-panel ${props.isDocked ? 'is-docked' : 'is-full'} ${showWelcome && !props.isDocked ? 'is-start-screen' : ''}`} {...inspectMenuAttrs(chatSelection, props.onInspect)}>
      <header className="chat-panel-header">
        <div className="chat-panel-header-title">
          <Icon name="chat" size={14} />
          <span>{activeConversation?.title || 'Chat'}</span>
        </div>
        <div className="chat-panel-header-actions">
          {conversationItems.length > 0 && <details className="chat-conversation-menu">
            <summary title="Abrir historial de conversaciones"><Icon name="history" size={12} /> Historial <span>{conversationItems.length}</span></summary>
            <div className="chat-conversation-popover">
              <header><strong>Conversaciones</strong><small>Persistentes en esta sesión</small></header>
              <div className="chat-conversation-list">
                {conversationItems.map((item) => <article key={item.conversation_id} className={item.active ? 'is-active' : ''}>
                  {renamingId === item.conversation_id ? (
                    <form onSubmit={(event) => {
                      event.preventDefault();
                      const title = renameTitle.trim();
                      if (!title || !props.onRenameConversation) return;
                      void runConversationAction(`rename:${item.conversation_id}`, () => props.onRenameConversation!(item.conversation_id, title)).then(() => setRenamingId(''));
                    }}>
                      <input aria-label="Título de conversación" value={renameTitle} maxLength={80} autoFocus onChange={(event) => setRenameTitle(event.target.value)} />
                      <button type="submit" disabled={!renameTitle.trim() || Boolean(conversationBusy)}>Guardar</button>
                      <button type="button" onClick={() => setRenamingId('')}>Cancelar</button>
                    </form>
                  ) : (
                    <>
                      <button type="button" className="chat-conversation-open" disabled={item.active || Boolean(conversationBusy)} onClick={() => props.onSwitchConversation && void runConversationAction(`switch:${item.conversation_id}`, () => props.onSwitchConversation!(item.conversation_id))}>
                        <strong>{item.title}</strong>
                        <small>{item.message_count} mensajes{item.preview ? ` · ${item.preview}` : ''}</small>
                      </button>
                      <div>
                        <button type="button" aria-label={`Renombrar ${item.title}`} onClick={() => { setRenamingId(item.conversation_id); setRenameTitle(item.title); }}><Icon name="prompt" size={11} /></button>
                        <button type="button" aria-label={`Archivar ${item.title}`} disabled={conversationItems.length < 2 || Boolean(conversationBusy)} onClick={() => props.onArchiveConversation && void runConversationAction(`archive:${item.conversation_id}`, () => props.onArchiveConversation!(item.conversation_id))}><Icon name="tray" size={11} /></button>
                      </div>
                    </>
                  )}
                </article>)}
              </div>
            </div>
          </details>}
          <button className="secondary-button chat-new-button" type="button" disabled={Boolean(conversationBusy)} onClick={() => props.onCreateConversation && void runConversationAction('create', props.onCreateConversation)} title="Crear un chat nuevo y persistente en esta sesión">
            <Icon name="plus" size={12} /> {conversationBusy === 'create' ? 'Creando…' : 'Nuevo chat'}
          </button>
          <div className="segmented-control" role="group" aria-label="Modo de chat">
            <button
              className={props.chatMode === 'live' ? 'is-active' : ''}
              type="button"
              onClick={() => props.onSetChatMode('live')}
              title="Modo live"
            >
              <Icon name="live" size={13} /> Live
            </button>
            <button
              className={props.chatMode === 'trace' ? 'is-active' : ''}
              type="button"
              onClick={() => props.onSetChatMode('trace')}
              title="Modo traza"
            >
              <Icon name="trace" size={13} /> Trace
            </button>
          </div>
          <button
            className="icon-button"
            type="button"
            title="Acciones de chat"
            aria-label="Acciones de chat"
            onClick={(event) => {
              const rect = event.currentTarget.getBoundingClientRect();
              props.onInspect(chatSelection, { x: rect.left, y: rect.bottom + 6 });
            }}
          >
            <Icon name="more" size={14} />
          </button>
        </div>
      </header>
      {conversationError && <div className="chat-conversation-error" role="alert">{conversationError}</div>}

      <div className="chat-surface">
        <section ref={timelineRef} className="chat-timeline" aria-live="polite">
          {welcomeOpen || props.turns.length === 0 ? (
            <div className={`chat-empty ${welcomeOpen ? 'is-home-start' : ''}`}>
              {welcomeOpen ? (
                <div className="start-chat-home">
                  <header className="start-chat-welcome">
                    <span className="chat-empty-icon"><Icon name="chat" size={24} /></span>
                    <div>
                      <h2>¿Qué quieres hacer ahora?</h2>
                      <p>Empieza un objetivo nuevo o recupera el contexto de un trabajo anterior. BAGO conservará cada conversación y su evidencia.</p>
                    </div>
                  </header>

                  <div className="start-chat-paths" aria-label="Formas de empezar">
                    <button type="button" className="start-chat-path is-primary" disabled={conversationBusy === 'create'} onClick={() => {
                      const begin = props.onCreateConversation
                        ? runConversationAction('create', props.onCreateConversation)
                        : Promise.resolve().then(() => setWelcomeOpen(false));
                      void begin.then(() => props.onStartNew?.());
                    }}>
                      <span className="start-chat-path-icon"><Icon name="plus" size={18} /></span>
                      <span><strong>{conversationBusy === 'create' ? 'Creando conversación…' : 'Empezar algo nuevo'}</strong><small>Abre una conversación limpia para describir el objetivo.</small></span>
                      <Icon name="chevron" size={14} />
                    </button>
                    <button type="button" className="start-chat-path" onClick={props.onContinue}>
                      <span className="start-chat-path-icon"><Icon name="context" size={18} /></span>
                      <span><strong>Continuar un trabajo</strong><small>Recupera contexto, tareas y decisiones existentes.</small></span>
                      <Icon name="chevron" size={14} />
                    </button>
                  </div>

                  <div className="start-chat-home-grid">
                    <RuntimeStatus snapshot={props.snapshot} onRefresh={props.onRefresh} />
                    <section className="start-chat-recent" aria-label="Trabajos recientes">
                      <div className="start-chat-recent-head"><strong>Trabajos recientes</strong><span>{props.recentProjects?.length ? 'Selecciona uno para abrirlo' : 'Aún no hay actividad'}</span></div>
                      {props.recentProjects?.length ? (
                        <div className="start-chat-recent-list">
                          {props.recentProjects.map((project) => (
                            <button key={project.id} type="button" className="start-chat-recent-item" onClick={() => props.onChooseRecent?.(project.id)}>
                              <span className="start-chat-recent-state" data-status={project.status} />
                              <span><strong>{project.title}</strong><small>{project.summary || project.status}</small></span>
                              <Icon name="chevron" size={13} />
                            </button>
                          ))}
                        </div>
                      ) : (
                        <div className="start-chat-no-recent"><Icon name="history" size={16} /><span>Los trabajos que abras o crees aparecerán aquí.</span></div>
                      )}
                    </section>
                  </div>
                </div>
              ) : (
                <><span className="chat-empty-icon"><Icon name="chat" size={26} /></span><h3>Empieza por la tarea</h3><p>Pregunta, describe un objetivo o solicita una acción. El chat es una pantalla más del workspace.</p></>
              )}
            </div>
          ) : timelineGroups.map((group) => {
            if (group.kind === 'turn') {
              return <TurnArticle key={group.id} {...props} turn={group.turns[0]} contextPatches={props.contextPatches || []} />;
            }
            const entries = group.turns.map((turn) => ({ turn, presentation: presentChatTurn(turn.text, turn.status) }));
            const technical = entries.filter((entry): entry is { turn: ChatTurn; presentation: TechnicalPresentation } => entry.presentation.kind !== 'message');
            const finalMessages = entries.filter((entry) => entry.presentation.kind === 'message');
            const failed = technical.some((entry) => entry.presentation.kind === 'error');
            return <section key={group.id} className={`chat-execution-group ${failed ? 'has-error' : ''}`} aria-label="Actividad técnica de BAGO">
              <details>
                <summary>
                  <span className="chat-execution-icon"><Icon name={failed ? 'warning' : 'command'} size={14} /></span>
                  <span><strong>{failed ? 'Acción no completada' : 'Actividad de BAGO'}</strong><small>{technical.length} {technical.length === 1 ? 'paso técnico' : 'pasos técnicos'} · detalle plegado</small></span>
                  <Icon name="chevron" size={12} />
                </summary>
                <div className="chat-execution-details">
                  {technical.map(({ turn, presentation }) => <article key={turn.id} className={`chat-execution-entry kind-${presentation.kind}`}>
                    <div><strong>{presentation.title}</strong><span>{new Date(turn.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span></div>
                    <p>{presentation.summary}</p>
                    {presentation.technicalDetail && <details><summary>Ver detalle técnico</summary><pre>{presentation.technicalDetail}</pre></details>}
                  </article>)}
                </div>
              </details>
              {finalMessages.map(({ turn }) => <TurnArticle key={turn.id} {...props} turn={turn} contextPatches={props.contextPatches || []} />)}
            </section>;
          })}
        </section>

        <footer className="chat-composer">
          <div className="chat-composer-shell">
            <div className="chat-composer-topbar">
              <span className="chat-composer-title">Mensaje a BAGO</span>
              <div className="chat-model-control">
                <label className="chat-reasoning-control">
                  <span>Profundidad</span>
                  <select aria-label="Profundidad de pensamiento" value={props.reasoningDepth} disabled={reasoningChanging} onChange={(event) => void onReasoningChange(event.target.value)}>
                    <option value="auto">Automática</option>
                    <option value="normal">Normal</option>
                    <option value="media">Media</option>
                    <option value="alta">Alta</option>
                    <option value="maxima">Máxima</option>
                  </select>
                </label>
                <div className="chat-model-picker" ref={modelPickerRootRef}>
                  <button type="button" className="chat-model-selector" aria-label="Modelo de esta sesión" aria-expanded={modelPickerOpen} aria-disabled={modelChanging} onClick={openModelPicker}>
                    <span>Modelo</span><strong>{currentModel?.model || (props.sessionModel ? props.sessionModel.split('/').pop() : 'Automático')}</strong><Icon name="chevron" size={11} />
                  </button>
                  {modelPickerOpen && modelPickerPos && <div className="chat-model-popover" style={{ position: 'fixed', top: modelPickerPos.top, right: modelPickerPos.right, maxHeight: modelPickerPos.maxHeight }}>
                    <label className="chat-model-search"><Icon name="search" size={12} /><input value={modelQuery} onChange={(event) => setModelQuery(event.target.value)} placeholder="Buscar modelo…" aria-label="Buscar modelo" /></label>
                    <div className="chat-model-options" role="listbox" aria-label="Modelos disponibles">
                      <button type="button" className={!props.sessionModel ? 'is-selected' : ''} role="option" aria-selected={!props.sessionModel} onClick={() => { void onModelChange(null); closeModelPicker(); }}>
                        <span><strong>Automático</strong><small>{automaticModel}</small></span>{!props.sessionModel && <Icon name="check" size={12} />}
                      </button>
                      {modelProviders.map((provider) => <section key={provider} className="chat-model-provider">
                        <header>{provider}</header>
                        {filteredModelOptions.filter((option) => option.provider === provider).map((option) => <button key={option.key} type="button" className={[props.sessionModel === option.key ? 'is-selected' : '', option.unavailable ? 'is-unavailable' : ''].filter(Boolean).join(' ')} role="option" aria-selected={props.sessionModel === option.key} aria-disabled={option.unavailable} onClick={() => { if (!option.unavailable) { void onModelChange(option.key); closeModelPicker(); } }}>
                          <span><strong>{option.model}</strong><small>{option.unavailable ? `${option.provider} · no configurado` : option.provider}</small></span>{props.sessionModel === option.key && <Icon name="check" size={12} />}
                        </button>)}
                      </section>)}
                      {filteredModelOptions.length === 0 && <p className="chat-model-empty">No hay modelos que coincidan.</p>}
                    </div>
                    <footer>{modelOptions.length} modelos en catálogo</footer>
                  </div>}
                </div>
              </div>
            </div>
            {modelError && <div className="chat-model-error" role="alert">No se pudo cambiar: {modelError}</div>}
            <textarea
              id="bago-chat-composer"
              className="chat-composer-textarea"
              value={draft}
              onChange={(e) => props.onDraftChange('chat', e.target.value)}
              onKeyDown={onComposerKeyDown}
              placeholder={canChat ? 'Escribe un mensaje, comando /, o describe una tarea...' : 'Chat inactivo'}
              disabled={!canChat}
              rows={2}
              maxLength={12000}
            />
            <div className="chat-composer-bottombar">
              <div className="chat-composer-tools">
                <span className="chat-composer-counter">
                  {draft.length.toLocaleString()} / 12.000
                </span>
                {!canChat && <span className="chat-composer-blocked-hint">{chatBlockedHint(props.snapshot)}</span>}
              </div>
              <button
                className="primary-button chat-send-button"
                type="button"
                disabled={!canChat || !draft.trim()}
                onClick={() => props.onSendChat(draft)}
                title={canChat ? 'Enviar mensaje (Enter)' : chatBlockedHint(props.snapshot)}
              >
                <span>Enviar</span>
                <Icon name="send" size={14} />
              </button>
            </div>
          </div>
        </footer>
      </div>
    </div>
  );
}

function chatBlockedHint(snapshot: UiBootstrapSnapshot | null): string {
  if (!snapshot) return 'Esperando datos del backend...';
  if (!snapshot.system.backendAvailable) return 'No hay conexión con el backend. Comprueba que BAGO está ejecutándose.';
  if (!snapshot.workspace.linkedToSession) return 'Selecciona o activa un workspace para poder chatear.';
  if (snapshot.workspace.manifestState !== 'valid') return 'El workspace necesita ser sembrado o reparado.';
  if (snapshot.model.state !== 'confirmed') return 'Configura un proveedor/modelo en el panel Sistema.';
  return 'El chat está temporalmente desactivado.';
}

function RuntimeStatus({ snapshot, onRefresh }: { snapshot: UiBootstrapSnapshot | null; onRefresh?: () => void }) {
  const backend = snapshot?.system.backendAvailable ? snapshot.system.state : 'error';
  const provider = snapshot?.model.provider && snapshot.model.effectiveModel
    ? `${snapshot.model.provider} · ${snapshot.model.effectiveModel}` : 'not_configured';
  const workspace = snapshot?.workspace.linkedToSession
    ? (snapshot.workspace.manifestState === 'valid' ? 'valid' : snapshot.workspace.manifestState)
    : 'unlinked';
  const context = snapshot?.context.state || 'unknown';
  const session = snapshot?.session.state || 'missing';
  const version = snapshot?.system.version || snapshot?.framework.version || 'not_observed';
  return <section className="start-chat-runtime-status" aria-label="Estado real de BAGO">
    <div className="start-chat-runtime-head"><strong>Estado real de BAGO</strong><span>Leído del backend activo</span>{onRefresh && <button type="button" className="text-button" onClick={onRefresh}>Actualizar</button>}</div>
    <div className="start-chat-runtime-grid">
      <RuntimeStatusItem label="Backend" value={quietStatus(backend) || 'Operativo'} ok={backend === 'confirmed' || backend === 'degraded'} raw={backend} />
      <RuntimeStatusItem label="Sesión" value={quietStatus(session) || 'Activa'} ok={session === 'valid' || session === 'recoverable'} raw={session} />
      <RuntimeStatusItem label="Proveedor / modelo" value={quietStatus(provider) || `${snapshot?.model.provider} · ${snapshot?.model.effectiveModel}`} ok={snapshot?.model.state === 'confirmed' || snapshot?.model.state === 'degraded'} raw={provider} />
      <RuntimeStatusItem label="Workspace" value={workspace === 'valid' ? 'Vinculado y válido' : quietStatus(workspace)} ok={workspace === 'valid'} raw={workspace} />
      <RuntimeStatusItem label="Contexto" value={quietStatus(context) || 'Confirmado'} ok={context === 'confirmed' || context === 'partial'} raw={context} />
      <RuntimeStatusItem label="Versión runtime" value={quietStatus(version) || version} ok={version !== 'not_observed'} raw={version} />
    </div>
  </section>;
}

function RuntimeStatusItem({ label, value, ok, raw }: { label: string; value: string; ok: boolean; raw: string }) {
  return <div className={`start-chat-runtime-item ${ok ? 'is-ok' : 'is-pending'}`}><span className="start-chat-runtime-dot" /><div><small>{label}</small><strong title={raw}>{value}</strong></div></div>;
}
