import { useMemo, useState, type ChangeEvent, type KeyboardEvent, type MouseEvent as ReactMouseEvent } from 'react';
import type {
  ActiveSection,
  BackendConversations,
  BackendSessions,
  BackendRouterEntry,
  BackendHistory,
  ChatMode,
  ChatTurn,
  ContextTargetKind,
  InspectorLevel,
  SelectionRecord,
  UiBootstrapSnapshot,
  BackendCommandResult,
  OpeningDecision
} from '@/contracts/backend';
import { Icon } from '@/shared/Icon';
import { quietStatus } from '@/shared/quiet-status';
import { ContextPatchValidationCard } from '@/features/context-tree/ContextPatchValidationCard';
import type { ContextPatchRequest } from '@/features/context-tree/contextTreeTypes';
import { buildChatModelOptions } from '@/layout/chatModelOptions';
import { groupTechnicalTurns, presentChatTurn, type ChatPresentation } from '@/shared/chatPresentation';
import { Modal } from '@/lib/Modal';

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
  opening: OpeningDecision;
  turns: ChatTurn[];
  drafts: Record<string, string>;
  chatMode: ChatMode;
  history: BackendHistory | null;
  conversations: BackendConversations | null;
  sessions: BackendSessions | null;
  canChat: boolean;
  routerEntries: BackendRouterEntry[];
  sessionModel: string | null;
  activeProvider: string | null;
  activeModels: Set<string>;
  onSetChatMode: (mode: ChatMode) => void;
  onDraftChange: (key: string, text: string) => void;
  onSendChat: (message: string) => Promise<void>;
  onCreateConversation: () => Promise<void>;
  onSwitchConversation: (conversationId: string) => Promise<void>;
  onCreateSession: () => Promise<boolean>;
  onSwitchSession: (sessionId: string) => Promise<boolean>;
  onRenameSession: (sessionId: string, title: string) => Promise<boolean>;
  onArchiveSession: (sessionId: string) => Promise<boolean>;
  onRestoreSession: (sessionId: string) => Promise<boolean>;
  sessionBusy: boolean;
  chatInProgress: boolean;
  conversationBusy: boolean;
  onInspect: (eventOrSelection: SelectionRecord | ReactMouseEvent<HTMLElement>, hint?: InspectorLevel | { x: number; y: number }) => void;
  onRunCommand: (command: string) => Promise<BackendCommandResult | null>;
  onRunContextCommand: (command: string) => Promise<void>;
  onNavigate: (section: ActiveSection) => void;
  onSetSessionModel: (modelKey: string | null) => Promise<void>;
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

type ArchivedSessionOrder = 'recent' | 'oldest' | 'name';

const sessionDateFormatter = new Intl.DateTimeFormat('es-ES', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit'
});

function formatSessionDate(value?: string): string {
  if (!value) return 'Fecha desconocida';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Fecha desconocida' : sessionDateFormatter.format(date);
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
    'aria-haspopup': 'menu' as const,
    title: 'Click derecho o Shift+F10 para acciones contextuales'
  };
}

export function ChatPanel(props: Props) {
  const [modelChanging, setModelChanging] = useState(false);
  const [modelError, setModelError] = useState('');
  const [sessionDialogOpen, setSessionDialogOpen] = useState(false);
  const [sessionTitleDraft, setSessionTitleDraft] = useState('');
  const [sessionActionBusy, setSessionActionBusy] = useState(false);
  const [sessionActionError, setSessionActionError] = useState('');
  const [archivedSessionQuery, setArchivedSessionQuery] = useState('');
  const [archivedSessionOrder, setArchivedSessionOrder] = useState<ArchivedSessionOrder>('recent');
  const [welcomeOpen, setWelcomeOpen] = useState(Boolean(props.startScreen));
  const draft = props.drafts.chat || '';
  const canChat = props.canChat;
  const historyMessages = Array.isArray(props.history?.messages) ? props.history.messages : [];
  const conversationItems = props.conversations?.conversations || [];
  const sessionItems = props.sessions?.sessions || [];
  const archivedSessionItems = props.sessions?.archived_sessions || [];
  const activeSessionId = props.sessions?.active_session_id || props.history?.session_id || '';
  const activeSession = sessionItems.find((session) => session.session_id === activeSessionId);
  const activeConversationId = props.conversations?.active_conversation_id || props.history?.conversation_id || 'main';
  const modelOptions = useMemo(
    () => buildChatModelOptions(props.routerEntries, props.activeProvider, props.activeModels, props.sessionModel),
    [props.routerEntries, props.activeProvider, props.activeModels, props.sessionModel]
  );
  const timelineGroups = useMemo(() => groupTechnicalTurns(props.turns), [props.turns]);
  const visibleArchivedSessions = useMemo(() => {
    const query = archivedSessionQuery.trim().toLocaleLowerCase('es');
    const matches = query
      ? archivedSessionItems.filter((session) => [session.title, session.session_id, session.workspace_name, session.preview]
        .some((value) => String(value || '').toLocaleLowerCase('es').includes(query)))
      : archivedSessionItems;
    const ordered = [...matches];
    ordered.sort((left, right) => {
      if (archivedSessionOrder === 'name') return left.title.localeCompare(right.title, 'es', { sensitivity: 'base' });
      const leftTime = Date.parse(left.archived_at || left.updated_at || left.created_at || '') || 0;
      const rightTime = Date.parse(right.archived_at || right.updated_at || right.created_at || '') || 0;
      return archivedSessionOrder === 'oldest' ? leftTime - rightTime : rightTime - leftTime;
    });
    return ordered;
  }, [archivedSessionItems, archivedSessionOrder, archivedSessionQuery]);
  const showWelcome = welcomeOpen && props.turns.length === 0 && conversationItems.length <= 1 && sessionItems.length <= 1;
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

  const onModelChange = async (event: ChangeEvent<HTMLSelectElement>) => {
    const nextModel = event.target.value || null;
    setModelChanging(true);
    setModelError('');
    try {
      await props.onSetSessionModel(nextModel);
    } catch (error) {
      setModelError(error instanceof Error ? error.message : 'No se pudo cambiar el modelo');
    } finally {
      setModelChanging(false);
    }
  };

  const openSessionDialog = () => {
    setSessionTitleDraft(activeSession?.title || `Sesión ${activeSessionId}`);
    setSessionActionError('');
    setSessionDialogOpen(true);
  };

  const renameActiveSession = async () => {
    const title = sessionTitleDraft.trim();
    if (!activeSessionId || !title) return;
    setSessionActionBusy(true);
    setSessionActionError('');
    try {
      if (await props.onRenameSession(activeSessionId, title)) setSessionDialogOpen(false);
    } catch (error) {
      setSessionActionError(error instanceof Error ? error.message : 'No se pudo renombrar la sesión');
    } finally {
      setSessionActionBusy(false);
    }
  };

  const archiveActiveSession = async () => {
    if (!activeSessionId) return;
    setSessionActionBusy(true);
    setSessionActionError('');
    try {
      if (await props.onArchiveSession(activeSessionId)) setSessionDialogOpen(false);
    } catch (error) {
      setSessionActionError(error instanceof Error ? error.message : 'No se pudo archivar la sesión');
    } finally {
      setSessionActionBusy(false);
    }
  };

  const restoreArchivedSession = async (sessionId: string) => {
    setSessionActionBusy(true);
    setSessionActionError('');
    try {
      if (await props.onRestoreSession(sessionId)) setSessionDialogOpen(false);
    } catch (error) {
      setSessionActionError(error instanceof Error ? error.message : 'No se pudo restaurar la sesión');
    } finally {
      setSessionActionBusy(false);
    }
  };

  return (
    <div className={`chat-panel is-full ${showWelcome ? 'is-start-screen' : ''}`} {...inspectMenuAttrs(chatSelection, props.onInspect)}>
      <header className="chat-panel-header">
        <div className="chat-panel-header-title">
          <Icon name="chat" size={14} />
          <span>Chat</span>
        </div>
        <div className="chat-panel-header-actions">
          <div className="chat-session-control">
            <span className="chat-scope-label">Sesión</span>
            <label className="visually-hidden" htmlFor="bago-session-select">Sesión activa</label>
            <select
              id="bago-session-select"
              aria-label="Sesión activa"
              value={activeSessionId}
              disabled={props.sessionBusy}
              onChange={(event) => void props.onSwitchSession(event.target.value)}
            >
              {sessionItems.length ? sessionItems.map((session) => (
                <option key={session.session_id} value={session.session_id}>
                  {session.title}{session.workspace_name ? ` · ${session.workspace_name}` : ''}
                </option>
              )) : <option value={activeSessionId}>{activeSessionId || 'Sesión actual'}</option>}
            </select>
            <button
              className="icon-button"
              type="button"
              disabled={props.sessionBusy}
              title="Nueva sesión en este workspace"
              aria-label="Nueva sesión"
              onClick={() => void props.onCreateSession()}
            >
              <Icon name="plus" size={13} />
            </button>
            <button
              className="icon-button"
              type="button"
              disabled={props.sessionBusy || !activeSessionId}
              title="Renombrar o archivar la sesión activa"
              aria-label="Gestionar sesión"
              onClick={openSessionDialog}
            >
              <Icon name="more" size={13} />
            </button>
          </div>
          <div className="chat-conversation-control">
            <span className="chat-scope-label">Chat</span>
            <label className="visually-hidden" htmlFor="bago-conversation-select">Conversación activa</label>
            <select
              id="bago-conversation-select"
              aria-label="Conversación activa"
              value={activeConversationId}
              disabled={props.conversationBusy}
              onChange={(event) => void props.onSwitchConversation(event.target.value)}
            >
              {conversationItems.length ? conversationItems.map((conversation) => (
                <option key={conversation.conversation_id} value={conversation.conversation_id}>
                  {conversation.title} · {conversation.message_count}
                </option>
              )) : <option value="main">Principal · {props.turns.length}</option>}
            </select>
            <button
              className="icon-button"
              type="button"
              disabled={props.conversationBusy}
              title="Nueva conversación en esta sesión"
              aria-label="Nueva conversación"
              onClick={() => void props.onCreateConversation()}
            >
              <Icon name="plus" size={13} />
            </button>
          </div>
          <div className="segmented-control" role="group" aria-label="Modo de chat">
            <button
              className={props.chatMode === 'live' ? 'is-active' : ''}
              type="button"
              onClick={() => props.onSetChatMode('live')}
              title="Modo directo"
            >
              <Icon name="live" size={13} /> Directo
            </button>
            <button
              className={props.chatMode === 'trace' ? 'is-active' : ''}
              type="button"
              onClick={() => props.onSetChatMode('trace')}
              title="Modo traza"
            >
              <Icon name="trace" size={13} /> Traza
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

      <Modal
        open={sessionDialogOpen}
        onClose={() => { if (!sessionActionBusy) setSessionDialogOpen(false); }}
        title="Gestionar sesión"
        subtitle={`${activeSessionId} · ${archivedSessionItems.length} archivadas`}
        width={680}
        footer={(
          <>
            <button type="button" className="secondary-button session-archive-button" disabled={sessionActionBusy} onClick={() => void archiveActiveSession()}>
              Archivar
            </button>
            <span className="modal-footer-spacer" />
            <button type="button" className="secondary-button" disabled={sessionActionBusy} onClick={() => setSessionDialogOpen(false)}>Cancelar</button>
            <button type="submit" form="bago-session-rename-form" className="primary-button" disabled={sessionActionBusy || !sessionTitleDraft.trim()}>Guardar nombre</button>
          </>
        )}
      >
        <form id="bago-session-rename-form" className="session-manage-form" onSubmit={(event) => { event.preventDefault(); void renameActiveSession(); }}>
          <label htmlFor="bago-session-title">Nombre de la sesión</label>
          <input
            id="bago-session-title"
            data-autofocus
            value={sessionTitleDraft}
            maxLength={80}
            disabled={sessionActionBusy}
            onChange={(event) => setSessionTitleDraft(event.target.value)}
          />
          <small>{activeSession?.message_count || 0} mensajes · {activeSession?.conversation_count || 1} chats{props.chatInProgress ? ' · respuesta en curso' : ''}</small>
        </form>
        <section className="archived-sessions-section" aria-labelledby="archived-sessions-title">
          <div className="archived-sessions-heading">
            <div>
              <strong id="archived-sessions-title">Archivadas</strong>
              <small>Se conservan completas hasta que decidas restaurarlas.</small>
            </div>
            <span className="archived-sessions-count">{archivedSessionItems.length}</span>
          </div>
          {archivedSessionItems.length > 0 ? (
            <>
              <div className="archived-sessions-toolbar">
                <label>
                  <span className="visually-hidden">Buscar sesiones archivadas</span>
                  <input
                    type="search"
                    value={archivedSessionQuery}
                    placeholder="Buscar por nombre, workspace o ID"
                    disabled={sessionActionBusy}
                    onChange={(event) => setArchivedSessionQuery(event.target.value)}
                    aria-label="Buscar sesiones archivadas"
                  />
                </label>
                <label>
                  <span className="visually-hidden">Ordenar sesiones archivadas</span>
                  <select
                    value={archivedSessionOrder}
                    disabled={sessionActionBusy}
                    onChange={(event) => setArchivedSessionOrder(event.target.value as ArchivedSessionOrder)}
                    aria-label="Ordenar sesiones archivadas"
                  >
                    <option value="recent">Más recientes</option>
                    <option value="oldest">Más antiguas</option>
                    <option value="name">Por nombre</option>
                  </select>
                </label>
              </div>
              {visibleArchivedSessions.length > 0 ? (
                <ul className="archived-sessions-list">
                  {visibleArchivedSessions.map((session) => (
                    <li key={session.session_id} className="archived-session-item">
                      <div className="archived-session-copy">
                        <strong>{session.title}</strong>
                        <span>{session.workspace_name || 'Sin workspace'} · {session.message_count} mensajes · {session.conversation_count} chats</span>
                        <small>{formatSessionDate(session.archived_at || session.updated_at)} · {session.session_id}</small>
                      </div>
                      <button
                        type="button"
                        className="secondary-button compact"
                        disabled={sessionActionBusy}
                        onClick={() => void restoreArchivedSession(session.session_id)}
                        aria-label={`Restaurar ${session.title}`}
                      >
                        Restaurar
                      </button>
                    </li>
                  ))}
                </ul>
              ) : <p className="archived-sessions-empty">No hay coincidencias.</p>}
            </>
          ) : <p className="archived-sessions-empty">No hay sesiones archivadas.</p>}
        </section>
        {sessionActionError && <p className="session-action-error" role="alert">{sessionActionError}</p>}
      </Modal>

      <div className="chat-surface">
        {props.opening.id !== 'enter_directly' && (
          <section className={`chat-opening-state state-${props.opening.id === 'show_blocked_state' || props.opening.id === 'show_workspace_repair' ? 'blocked' : 'running'}`} role={props.opening.id === 'show_blocked_state' ? 'alert' : 'status'} data-opening-state={props.opening.id}>
            <div>
              <span>Estado de apertura</span>
              <strong>{props.opening.label}</strong>
              <p>{props.opening.reason}</p>
            </div>
            <button type="button" className="secondary-button compact" onClick={() => props.opening.targetSection === 'home' ? props.onRefresh?.() : props.onNavigate(props.opening.targetSection)}>
              {props.opening.actionLabel}
            </button>
          </section>
        )}
        <section className="chat-timeline" aria-live="polite">
          {props.turns.length === 0 ? (
            <div className="chat-empty">
              <span className="chat-empty-icon"><Icon name="chat" size={26} /></span>
              {welcomeOpen ? (
                <>
                  <span className="start-chat-eyebrow">INICIO · CHAT</span>
                  <h3>Hola, bienvenido. Soy BAGO.</h3>
                  <p>¿Vas a trabajar en algo nuevo o quieres continuar?</p>
                  <div className="start-chat-actions">
                    <button type="button" className="primary-button" onClick={() => { setWelcomeOpen(false); props.onStartNew?.(); }}><span className="start-chat-key">1</span> Nuevo</button>
                    <button type="button" className="secondary-button" onClick={props.onContinue}><span className="start-chat-key">2</span> Continuar</button>
                  </div>
                  <RuntimeStatus snapshot={props.snapshot} onRefresh={props.onRefresh} />
                  {props.recentProjects?.length ? (
                    <section className="start-chat-recent" aria-label="Cinco proyectos recientes">
                      <div className="start-chat-recent-head"><strong>3 · Proyectos recientes</strong><span>Elige uno para continuar</span></div>
                      <div className="start-chat-recent-list">
                        {props.recentProjects.map((project, index) => (
                          <button key={project.id} type="button" className="start-chat-recent-item" onClick={() => props.onChooseRecent?.(project.id)}>
                            <span className="start-chat-recent-number">{index + 1}</span>
                            <span><strong>{project.title}</strong><small>{project.summary || project.status}</small></span>
                            <Icon name="chevron" size={13} />
                          </button>
                        ))}
                      </div>
                    </section>
                  ) : (
                    <p className="start-chat-no-recent">Todavía no hay proyectos recientes. Al crear uno aparecerá aquí.</p>
                  )}
                </>
              ) : (
                <><h3>Empieza por la tarea</h3><p>Pregunta, describe un objetivo o solicita una acción. El chat es una pantalla más del workspace.</p></>
              )}
            </div>
          ) : timelineGroups.map((group) => (
            <section key={group.id} className={group.kind === 'execution' ? 'chat-execution-group' : 'chat-turn-group'} aria-label={group.kind === 'execution' ? 'Ejecución de BAGO' : undefined}>
            {group.turns.map((turn) => {
            const presentation = presentChatTurn(turn.text, turn.status);
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
            const turnPatches = (props.contextPatches || []).filter((entry) => entry.turnId === turn.id);
            const clarificationOptions = Array.isArray(turn.clarification?.options)
              ? turn.clarification.options as Array<Record<string, unknown>>
              : [];
            return (
            <article
              key={turn.id}
              className={`chat-message role-${turn.role} status-${turn.status || 'done'}`}
              {...inspectMenuAttrs(turnSelection, props.onInspect)}
              onClick={() => props.onInspect(turnSelection)}
            >
              <div className="message-avatar">
                {turn.role === 'user' ? 'TÚ' : turn.role === 'command' ? '/' : 'B'}
              </div>
              <div className="message-body">
                <div className="message-meta">
                  <strong>{turn.role === 'user' ? 'Tú' : turn.role === 'command' ? 'Comando' : 'BAGO'}</strong>
                  <span>{new Date(turn.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                  {turn.role === 'assistant' && (turn.provider || turn.model) && <span>{[turn.provider, turn.model].filter(Boolean).join(' · ')}</span>}
                  {turn.status && <StatusBadge status={turn.status} />}
                </div>
                <MessageContent presentation={turn.status === 'running' && !turn.text ? { kind: 'message', text: '…' } : presentation} />
                {clarificationOptions.length > 0 && (
                  <div className="message-patches" onClick={(event) => event.stopPropagation()}>
                    {clarificationOptions.map((option, index) => (
                      <button
                        key={String(option.id || index)}
                        type="button"
                        className="secondary-button compact"
                        onClick={() => void props.onSendChat(`${String(option.prefix || option.label || '').trim()}: ${String(turn.clarification?.original || '').trim()}`)}
                      >
                        {String(option.label || option.id || 'Continuar')}
                      </button>
                    ))}
                  </div>
                )}
                {turnPatches.length > 0 && (
                  <div className="message-patches" onClick={(event) => event.stopPropagation()}>
                    {turnPatches.map((entry) => (
                      <ContextPatchValidationCard
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
                        onOpenInTree={(id) => {
                          props.onOpenContextInTree?.(id);
                          props.onNavigate('context');
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            </article>
            );
            })}
            </section>
          ))}
        </section>

        <footer className="chat-composer">
          <div className="chat-composer-shell">
            <div className="chat-composer-topbar">
              <span className="chat-composer-title">Mensaje a BAGO</span>
              <div className="chat-model-control">
                <label htmlFor="bago-chat-model">Modelo</label>
                <select
                  id="bago-chat-model"
                  className="chat-model-selector"
                  aria-label="Modelo de esta sesión"
                  value={props.sessionModel || ''}
                  disabled={modelChanging || modelOptions.length === 0}
                  onChange={(event) => void onModelChange(event)}
                >
                  <option value="">Automático · router · {[props.activeProvider, props.snapshot?.model.effectiveModel || props.snapshot?.model.configuredModel].filter(Boolean).join('/') || 'sin modelo'}</option>
                  {modelOptions.map((option) => (
                    <option key={option.key} value={option.key}>{option.label}</option>
                  ))}
                </select>
                <span className="chat-model-selector-count" title="Modelos disponibles">{modelOptions.length}</span>
              </div>
            </div>
            {modelError && <div className="chat-model-error" role="alert">No se pudo cambiar: {modelError}</div>}
            <textarea
              id="bago-chat-composer"
              className="chat-composer-textarea"
              value={draft}
              onChange={(e) => props.onDraftChange('chat', e.target.value)}
              onKeyDown={onComposerKeyDown}
              placeholder={canChat ? 'Escribe un mensaje, comando /, o describe una tarea...' : 'Chat bloqueado por el estado del backend'}
              disabled={!canChat}
              rows={2}
              maxLength={12000}
            />
            <div className="chat-composer-bottombar">
              <div className="chat-composer-tools">
                <span className="chat-composer-counter">
                  {draft.length.toLocaleString()} / 12.000
                </span>
              </div>
              <button
                className="primary-button chat-send-button"
                type="button"
                disabled={!canChat || !draft.trim()}
                onClick={() => props.onSendChat(draft)}
                title="Enviar mensaje (Enter)"
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

function MessageContent({ presentation }: { presentation: ChatPresentation }) {
  if (presentation.kind === 'message') {
    return <div className="message-text">{presentation.text}</div>;
  }
  return (
    <section className={`message-activity is-${presentation.kind}`} role={presentation.kind === 'error' ? 'alert' : 'status'}>
      <div className="message-activity-icon"><Icon name={presentation.kind === 'error' ? 'warning' : 'command'} size={14} /></div>
      <div className="message-activity-copy">
        <strong>{presentation.title}</strong>
        <p>{presentation.summary}</p>
        {presentation.technicalDetail && (
          <details onClick={(event) => event.stopPropagation()}>
            <summary>Ver detalle técnico</summary>
            <pre>{presentation.technicalDetail}</pre>
          </details>
        )}
      </div>
    </section>
  );
}

function RuntimeStatus({ snapshot, onRefresh }: { snapshot: UiBootstrapSnapshot | null; onRefresh?: () => void }) {
  const backend = snapshot?.system.backendAvailable ? snapshot.system.state : 'error';
  const provider = snapshot?.model.provider && snapshot.model.effectiveModel
    ? `${snapshot.model.provider} · ${snapshot.model.effectiveModel}` : 'No configurado';
  const workspace = snapshot?.workspace.linkedToSession
    ? `Vinculado · ${snapshot.workspace.manifestState}` : 'No vinculado';
  const context = snapshot?.context.state || 'unknown';
  const session = snapshot?.session.state || 'missing';
  return <section className="start-chat-runtime-status" aria-label="Estado real de BAGO">
    <div className="start-chat-runtime-head"><strong>Estado real de BAGO</strong><span>Leído del backend activo</span>{onRefresh && <button type="button" className="text-button" onClick={onRefresh}>Actualizar</button>}</div>
    <div className="start-chat-runtime-grid">
      <RuntimeStatusItem label="Backend" value={backend} ok={backend === 'confirmed' || backend === 'degraded'} />
      <RuntimeStatusItem label="Sesión" value={session} ok={session === 'valid' || session === 'recoverable'} />
      <RuntimeStatusItem label="Proveedor / modelo" value={provider} ok={snapshot?.model.state === 'confirmed' || snapshot?.model.state === 'degraded'} />
      <RuntimeStatusItem label="Workspace" value={workspace} ok={Boolean(snapshot?.workspace.linkedToSession && snapshot.workspace.manifestState === 'valid')} />
      <RuntimeStatusItem label="Contexto" value={context} ok={context === 'confirmed' || context === 'partial'} />
      <RuntimeStatusItem label="Versión runtime" value={snapshot?.system.version || snapshot?.framework.version || 'No observada'} ok={Boolean(snapshot?.system.version || snapshot?.framework.version)} />
    </div>
  </section>;
}

function RuntimeStatusItem({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return <div className={`start-chat-runtime-item ${ok ? 'is-ok' : 'is-pending'}`}><span className="start-chat-runtime-dot" /><div><small>{label}</small><strong title={value}>{value}</strong></div></div>;
}
