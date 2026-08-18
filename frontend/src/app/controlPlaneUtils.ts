import type { BackendHistory, ChatTurn, UiBootstrapSnapshot } from '@/contracts/backend';
import { normalizeChatResponse } from '@/shared/chatResponse';
import { readRecord } from '@/shared/unknownValue';

export type WorkspaceSelectionResult = {
  ok?: boolean;
  canceled?: boolean;
  path?: string;
  filePath?: string;
  filePaths?: string[];
  message?: string;
};

export function nowStamp(): string {
  return new Date().toISOString();
}

export function hashString(input: string): string {
  let hash = 5381;
  for (let index = 0; index < input.length; index += 1) {
    hash = ((hash << 5) + hash) + input.charCodeAt(index);
    hash &= 0x7fffffff;
  }
  return hash.toString(36);
}

export function shouldOfferSeed(snapshot: UiBootstrapSnapshot | null, selectedRoot: string): boolean {
  const cleanRoot = selectedRoot.trim();
  if (!cleanRoot || !snapshot) return false;
  const currentRoot = String(snapshot.project.root || snapshot.workspace.repoRoot || snapshot.workspace.root || '').trim();
  if (currentRoot && currentRoot === cleanRoot && snapshot.workspace.linkedToSession && snapshot.workspace.manifestState === 'valid') {
    return false;
  }
  return Boolean(
    snapshot.workspace.seedSuggested
    || snapshot.workspace.manifestState !== 'valid'
    || !snapshot.workspace.linkedToSession
    || currentRoot !== cleanRoot
  );
}

export function getElectronBridge() {
  return typeof window === 'undefined' ? undefined : window.bagoElectron;
}

export function readSelectedWorkspace(result: WorkspaceSelectionResult | null | undefined): string {
  if (!result || result.canceled === true) return '';
  return String(result.path || result.filePath || (Array.isArray(result.filePaths) ? result.filePaths[0] : '') || '').trim();
}

export function normalizeWorkspaceHint(value: string): string {
  const clean = String(value || '').trim().replace(/[\\/]+$/, '');
  if (!clean) return '';
  const normalized = clean.replace(/\//g, '\\');
  const lower = normalized.toLowerCase();
  if (lower.endsWith('\\.gabo') || lower.endsWith('\\.bago')) {
    return normalized.slice(0, normalized.lastIndexOf('\\'));
  }
  if (lower === '.gabo' || lower === '.bago') return '';
  return clean;
}

export function commandKey(command: string): string {
  return command.trim().replace(/^\/+/, '').replace(/[^\w]+/g, '_').replace(/^_+|_+$/g, '') || 'command';
}

export function historyToTurns(history: BackendHistory | undefined): ChatTurn[] {
  if (!Array.isArray(history?.messages)) return [];
  return history.messages.slice(-30).map((message, index) => {
    const roleValue = String(message.role || 'assistant');
    const role: ChatTurn['role'] = roleValue === 'user' || roleValue === 'system' || roleValue === 'command' ? roleValue : 'assistant';
    const metadata = readRecord(message.metadata);
    const normalized = normalizeChatResponse(
      String(message.content || message.text || message.message || ''),
      metadata.response_state
    );
    return {
      id: String(message.id || `history-${index}`),
      role,
      text: normalized.text,
      status: normalized.state,
      receipt: (message.receipt || message.context_receipt || null) as Record<string, unknown> | null,
      provider: String(message.provider || metadata.provider || ''),
      model: String(message.model || metadata.model || ''),
      clarification: normalized.clarification,
      raw: message,
      timestamp: String(message.timestamp || message.created_at || nowStamp())
    };
  });
}
