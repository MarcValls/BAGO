export type CapabilityAvailability = 'available' | 'conditional' | 'blocked' | 'unavailable';

export interface CapabilitySummary {
  id: string;
  name: string;
  description: string;
  availability: CapabilityAvailability;
  definition_state: 'proposed' | 'prepared' | 'verified' | 'deprecated';
  piece_count: number;
  route_count: number;
  revision: number;
  etag: string;
}

export interface CapabilityPiece {
  id: string;
  name: string;
  type: string;
  purpose: string;
  definition_state: string;
  availability: CapabilityAvailability;
  implementation: { kind: string; ref: string | null; owner: string | null };
  requires: string[];
  produces: string[];
  authorization: { mode: string; permissions: string[]; approval_required: boolean };
  evidence_expected: string[];
  fallback_piece_id: string | null;
  block_reason: string | null;
}

export interface CapabilityRoute {
  id: string;
  name: string;
  description: string;
  priority: number;
  condition: string;
  steps: string[];
  availability: CapabilityAvailability;
  block_reason: string | null;
  fallback_route_id: string | null;
  evidence_expected: string[];
}

export interface CapabilitySnapshot {
  schema_version: '0.2';
  contract_version: 'bago.capability/v0.2';
  revision: number;
  etag: string;
  source: { authority: 'backend' | 'conversation' | 'fixture'; provenance: string; generated_at: string | null };
  capability: CapabilitySummary & { version: string; tags: string[] };
  pieces: CapabilityPiece[];
  routes: CapabilityRoute[];
  governance: {
    authority: { decision: string; execution: 'backend'; verification: 'backend' };
    recommended_route_id: string | null;
    action_policy: { allowed: Array<{ id: string; kind: string; label: string }>; blocked: Array<{ id: string; kind: string; label: string; reason: string }> };
  };
  runtime_snapshot: { source: 'none' | 'backend'; run_state: string; selected_piece_id: string | null; active_route_id: string | null; execution_id: string | null; receipt_id: string | null; observed_at: string | null };
  host_binding: { host: 'BAGO'; surface: 'graph' | 'pipeline'; mode: 'read_only' | 'disabled'; feature_flag: string; persistence_root: 'none' | 'backend_resolved'; expected_contract_version: string };
  evidence: Array<Record<string, unknown>>;
}

export interface CapabilityListResponse {
  ok: boolean;
  feature_flag: string;
  mode: 'read_only';
  capabilities: CapabilitySummary[];
}

export class CapabilityContractError extends Error {}

export function validateCapabilitySnapshot(value: unknown): CapabilitySnapshot {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new CapabilityContractError('Respuesta de capacidad no válida.');
  const data = value as Partial<CapabilitySnapshot>;
  if (data.schema_version !== '0.2' || data.contract_version !== 'bago.capability/v0.2') throw new CapabilityContractError('Versión de capacidad no compatible.');
  if (!Array.isArray(data.pieces) || data.pieces.length < 2 || !Array.isArray(data.routes)) throw new CapabilityContractError('El contrato no contiene piezas o rutas válidas.');
  if (data.source?.authority !== 'backend') throw new CapabilityContractError('La capacidad no procede del backend autorizado.');
  if (data.host_binding?.mode !== 'read_only') throw new CapabilityContractError('La vista solo admite contratos de lectura.');
  const ids = new Set(data.pieces.map((piece) => piece.id));
  for (const route of data.routes) {
    if (route.steps.some((step) => !ids.has(step))) throw new CapabilityContractError(`Ruta con referencia desconocida: ${route.id}`);
  }
  if (data.runtime_snapshot?.run_state === 'succeeded' && (!data.runtime_snapshot.execution_id || !data.runtime_snapshot.receipt_id || !data.evidence?.length)) {
    throw new CapabilityContractError('El backend afirma éxito sin receipt y evidencia.');
  }
  return data as CapabilitySnapshot;
}

