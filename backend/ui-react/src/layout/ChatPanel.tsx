import { useState, type KeyboardEvent, type MouseEvent as ReactMouseEvent } from 'react';
import type {
  ActiveSection,
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
  routerEntries: Array<Record<string, unknown>>;
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

function ModelSelector(props: {
  entries: Array<Record<string, unknown>>;
  sessionModel: string | null;
  activeProvider: string | null;
  activeModels: Set<string>;
  disabled: boolean;
  onChange: (key: string | null) => void;
}) {
  // Lógica de filtrado:
  //   1) Si el usuario guardó active_models para el provider activo,
  //      esos son los candidatos. El router marca available pero no
  //      garantiza que estén todos.
  //   2) Si no hay active_models guardados, fallback al filtro del
  //      router (available + selected).
  const hasFilter = props.activeModels.size > 0;
  let candidates: Array<Record<string, unknown>>;
  if (hasFilter) {
    // Construir candidatos a partir de activeModels + entries del router
    // Si un modelo está en activeModels pero no en entries, creamos
    // una entrada sintética para que aparezca en el desplegable.
    const routerByModelId = new Map<string, Record<string, unknown>>();
    for (const e of props.entries) {
      const mid = String(e.model_id || e.wire_name || '');
      if (mid) routerByModelId.set(mid, e);
    }
    candidates = Array.from(props.activeModels).map((modelId) => {
      const fromRouter = routerByModelId.get(modelId);
      if (fromRouter) return fromRouter;
      // Entrada sintética: provider activo + model_id del active set
      return {
        key: `${props.activeProvider || '?'}/${modelId}`,
        provider: props.activeProvider || '?',
        model_id: modelId,
        wire_name: modelId,
        available: true,
        selected: true
      };
    });
    // Ordenar por nombre
    candidates.sort((a, b) => {
      const an = String(a.model_id || a.wire_name || '');
      const bn = String(b.model_id || b.wire_name || '');
      return an.localeCompare(bn);
    });
  } else {
    candidates = props.entries.filter((e) => Boolean(e.available !== false) && Boolean(e.selected));
  }
  const current = props.sessionModel || '';
  const currentLabel = (() => {
    if (!current) return 'Auto (router)';
    const hit = props.entries.find((e) => String(e.key || `${e.provider}/${e.model_id}`) === current);
    if (hit) return `${String(hit.provider || '?')} · ${String(hit.model_id || hit.wire_name || '?')}`;
    return current;
  })();
  return (
    <>
      <select
        className="chat-model-selector"
        value={current}
        onChange={(e) => props.onChange(e.target.value === '' ? null : e.target.value)}
        disabled={props.disabled}
        title={
          hasFilter
            ? `Modelos activos del provider ${props.activeProvider || '?'} (${props.activeModels.size})`
            : 'Modelo para esta sesión'
        }
        aria-label="Modelo de la sesión"
      >
        <option value="">Auto (router)</option>
        {candidates.map((entry, idx) => {
          const key = String(entry.key || `${entry.provider}/${entry.model_id}` || `entry-${idx}`);
          const label = `${String(entry.provider || '?')} · ${String(entry.model_id || entry.wire_name || key)}`;
          return <option key={key} value={key}>{label}</option>;
        })}
      </select>
      {hasFilter && (
        <span className="chat-model-selector-count" aria-hidden="true">
          {props.activeModels.size}
        </span>
      )}
    </>
  );
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
  const lastCommand = [...props.turns].reverse().find((t) => t.role === 'command');
  const canChat = props.canChat;
  const historyMessages = Array.isArray(props.history?.messages) ? props.history.messages : [];
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
        <div className="chat-toolbar">
          <span className="context-hint"><Icon name="more" size={14} /> Click derecho en el panel o en un mensaje para adjuntar contexto, preparar comandos, abrir evidencia o copiar raw.</span>
          {lastCommand && <span className="chat-toolbar-last-command">Último comando disponible</span>}
        </div>

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
          <div className="chat-prompt-chips" aria-label="Acciones contextuales">
            <span className="context-hint"><Icon name="more" size={14} /> Botón derecho: Plan, Medir, Proyecto, Auditoría, Adjuntar o Último comando.</span>
          </div>
          <div className="chat-composer-shell">
            <div className="chat-composer-topbar">
              <span className="chat-composer-title">Mensaje a BAGO</span>
              <ModelSelector
                entries={props.routerEntries}
                sessionModel={props.sessionModel}
                activeProvider={props.activeProvider}
                activeModels={props.activeModels}
                disabled={!canChat}
                onChange={(key) => void props.onSetSessionModel(key)}
              />
            </div>
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
                <span className="context-hint"><Icon name="more" size={14} /> Acciones secundarias en botón derecho</span>
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
