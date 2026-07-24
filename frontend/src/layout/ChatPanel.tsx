import { useMemo, useState, type ChangeEvent, type KeyboardEvent, type MouseEvent as ReactMouseEvent } from 'react';
import type {
  ActiveSection,
  BackendRouterEntry,
  BackendHistory,
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
import { ContextPatchValidationCard } from '@/features/context-tree/ContextPatchValidationCard';
import type { ContextPatchRequest } from '@/features/context-tree/contextTreeTypes';
import { buildChatModelOptions } from '@/layout/chatModelOptions';

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
}

function summarize(message: Record<string, unknown>): string {
  return String(message.content || message.text || message.message || '').trim();
}

function statusTone(status: string): string {
  const value = status.toLowerCase();
  if (['done', 'confirmed', 'valid', 'certified', 'ok'].some((e) => value.includes(e))) return 'confirmed';
  if (['running', 'pending', 'loading', 'partial', 'stale'].some((e) => value.includes(e))) return 'running';
  if (['failed', 'error', 'invalid', 'rejected'].some((e) => value.includes(e))) return 'error';
  if (['blocked', 'missing', 'legacy'].some((e) => value.includes(e))) return 'blocked';
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
    'aria-haspopup': 'menu' as const,
    title: 'Click derecho o Shift+F10 para acciones contextuales'
  };
}

export function ChatPanel(props: Props) {
  const draft = props.drafts.chat || '';
  const canChat = props.canChat;
  const [modelChanging, setModelChanging] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);
  const historyMessages = Array.isArray(props.history?.messages) ? props.history.messages : [];
  const modelOptions = useMemo(
    () => buildChatModelOptions(props.routerEntries, props.activeProvider, props.activeModels, props.sessionModel),
    [props.routerEntries, props.activeProvider, props.activeModels, props.sessionModel]
  );
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

  return (
    <div className="chat-panel is-full" {...inspectMenuAttrs(chatSelection, props.onInspect)}>
      <header className="chat-panel-header">
        <div className="chat-panel-header-title">
          <Icon name="chat" size={14} />
          <span>Chat</span>
        </div>
        <div className="chat-panel-header-actions">
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

      <div className="chat-surface">
        <section className="chat-timeline" aria-live="polite">
          {props.turns.length === 0 ? (
            <div className="chat-empty">
              <span className="chat-empty-icon"><Icon name="chat" size={26} /></span>
              <h3>Empieza por la tarea</h3>
              <p>Pregunta, describe un objetivo o solicita una acción. El chat es una pantalla más del workspace.</p>
            </div>
          ) : props.turns.map((turn) => {
            const turnSelection: SelectionRecord = {
              id: turn.id,
              kind: 'chat-turn',
              targetKind: 'screen.chat' as ContextTargetKind,
              title: turn.role === 'user' ? 'Mensaje del usuario' : turn.role === 'command' ? 'Comando' : 'Respuesta de BAGO',
              summary: turn.text.slice(0, 240),
              detail: [
                `status: ${turn.status || 'done'}`,
                `timestamp: ${turn.timestamp}`,
                `receipt: ${turn.receipt ? 'available' : 'none'}`
              ],
              raw: turn.raw || turn
            };
            const turnPatches = (props.contextPatches || []).filter((entry) => entry.turnId === turn.id);
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
                  {turn.status && <StatusBadge status={turn.status} />}
                </div>
                <div className="message-text">{turn.text || (turn.status === 'running' ? '...' : '')}</div>
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
                  onChange={(event) => {
                    const nextModel = event.target.value || null;
                    setModelChanging(true);
                    setModelError(null);
                    void props.onSetSessionModel(nextModel)
                      .catch((error) => setModelError(error instanceof Error ? error.message : String(error)))
                      .finally(() => setModelChanging(false));
                  }}
                >
                  <option value="">Automático · router</option>
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
                <label className="chat-model-control">
                  <select
                    className="chat-model-selector"
                    value={props.sessionModel || ''}
                    onChange={(event) => void onModelChange(event)}
                    disabled={modelChanging || modelOptions.length === 0}
                    aria-label="Modelo de la sesión"
                    aria-describedby={modelError ? 'chat-model-error' : undefined}
                    title="Elegir modelo para esta sesión"
                  >
                    <option value="">{modelChanging ? 'Cambiando modelo…' : 'Automático'}</option>
                    {modelOptions.map((option) => (
                      <option key={option.key} value={option.key}>{option.label}</option>
                    ))}
                  </select>
                  <span className="chat-model-selector-count" aria-hidden="true">{modelOptions.length}</span>
                </label>
                {modelError && <span id="chat-model-error" className="chat-model-error" role="alert">{modelError}</span>}
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
