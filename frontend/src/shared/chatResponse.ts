export type ChatResponseState = 'done' | 'needs_confirmation' | 'failed' | 'blocked' | 'validating';

export interface NormalizedChatResponse {
  text: string;
  state: ChatResponseState;
  contract?: Record<string, unknown>;
  clarification?: Record<string, unknown>;
}

function list(value: unknown, limit = 4): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    if (typeof item === 'string') return item.trim();
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>;
      return String(record.message || record.summary || record.path || record.key || '').trim();
    }
    return String(item || '').trim();
  }).filter(Boolean).slice(0, limit);
}

function parseObject(text: string): Record<string, unknown> | null {
  const clean = text.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  if (!clean.startsWith('{')) return null;
  try {
    const value = JSON.parse(clean);
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

export function normalizeChatResponse(text: string, stateHint?: unknown): NormalizedChatResponse {
  const clean = String(text || '').trim();
  if (clean.startsWith('__BAGO_CLARIFY__')) {
    const clarification = parseObject(clean.slice('__BAGO_CLARIFY__'.length));
    return {
      text: String(clarification?.question || 'Necesito que confirmes cómo quieres continuar.'),
      state: 'needs_confirmation',
      clarification: clarification || undefined
    };
  }

  const contract = parseObject(clean);
  const required = ['intent', 'objective', 'facts', 'evidence', 'confidence'];
  if (contract && required.every((key) => key in contract)) {
    const objective = String(contract.objective || '').trim();
    const missing = list(contract.missing_information);
    const changes = list(contract.proposed_changes);
    const validation = list(contract.validation_actions);
    const lines = [objective || 'La respuesta anterior no concretó un objetivo ejecutable.'];
    if (missing.length) lines.push(`Necesito confirmar: ${missing.join('; ')}`);
    if (changes.length) lines.push(`Cambios propuestos: ${changes.join('; ')}`);
    if (validation.length) lines.push(`Validación: ${validation.join('; ')}`);
    return {
      text: lines.join('\n\n'),
      state: objective && (changes.length || validation.length || list(contract.evidence).length) && !missing.length ? 'done' : 'needs_confirmation',
      contract
    };
  }

  const allowed = new Set<ChatResponseState>(['done', 'needs_confirmation', 'failed', 'blocked', 'validating']);
  const hinted = String(stateHint || 'done') as ChatResponseState;
  return { text: clean, state: allowed.has(hinted) ? hinted : 'done' };
}
