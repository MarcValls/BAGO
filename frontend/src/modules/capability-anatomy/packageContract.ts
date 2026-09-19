export type CapabilityFieldType = 'string' | 'number' | 'integer' | 'boolean';

export interface CapabilityFieldDefinition {
  type: CapabilityFieldType;
  title: string;
  description?: string;
  default?: unknown;
  enum?: unknown[];
}

export interface CapabilityObjectSchema {
  type: 'object';
  properties: Record<string, CapabilityFieldDefinition>;
  required: string[];
  additionalProperties?: boolean;
}

export interface CapabilityPackageRecord {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  enabled: boolean;
  available: boolean;
  error: string;
  permissions: string[];
  runtime?: { kind?: string; entrypoint?: string; timeout_s?: number };
  configuration_schema?: CapabilityObjectSchema;
  input_schema?: CapabilityObjectSchema;
  config?: Record<string, unknown>;
  digest: string;
  installed_at: string;
  last_run_at: string | null;
  last_status: string;
  last_receipt_id: string | null;
  tags: string[];
  kind?: 'capability' | 'pipeline';
  execution_mode?: 'declarative' | 'executable';
  signature_state?: 'unsigned' | 'unknown_key' | 'verified' | 'invalid';
  digest_state?: string;
  legacy_source?: boolean;
  trust_state?: 'untrusted' | 'trusted';
  trusted_permissions?: string[];
  warnings?: string[];
  compatibility?: Record<string, unknown>;
  dependencies?: Array<{ id: string; version: string }>;
  files?: Array<{ path: string; size: number; sha256: string }>;
  schedule_defaults?: Array<{ name: string; schedule_type: 'interval' | 'cron'; interval_s?: number; cron_expr?: string; timezone: string }>;
}

export interface PackageInspection {
  ok: boolean;
  identity?: { id: string; name: string; version: string; description: string; author: string };
  kind?: 'capability' | 'pipeline';
  execution_mode?: 'declarative' | 'executable';
  files?: Array<{ path: string; size: number; sha256: string }>;
  schedule_defaults?: Array<{ name: string; schedule_type: 'interval' | 'cron'; interval_s?: number; cron_expr?: string; timezone: string }>;
  compatibility?: Record<string, unknown>;
  dependencies?: Array<{ id: string; version: string }>;
  permissions?: string[];
  digest_state?: string;
  signature_state?: string;
  legacy_source?: boolean;
  warnings?: string[];
  errors?: Array<{ code?: string; message?: string }>;
}

export interface CapabilityReceipt {
  receipt_id: string;
  execution_id: string;
  capability_id: string;
  capability_version: string;
  pipeline_id?: string;
  status: string;
  started_at: string;
  finished_at: string;
  duration_ms: number;
  exit_code: number | null;
  result: unknown;
  stderr: string;
  error: string;
  permissions: string[];
}

export interface CapabilityPackagesResponse {
  ok: boolean;
  packages: CapabilityPackageRecord[];
}

export interface CapabilityReceiptsResponse {
  ok: boolean;
  receipts: CapabilityReceipt[];
}

export interface CapabilityPackageResponse {
  ok: boolean;
  already_installed?: boolean;
  package: CapabilityPackageRecord;
}

export interface AuthorizationChallenge {
  challenge_id: string;
  state: 'pending' | 'approved' | 'expired';
  interaction_id: string;
  session_id: string;
  capability_id: string;
  permissions: string[];
  operation_fingerprint: string;
  issued_at: string;
  expires_at: string;
}

export interface UserAuthorizationProof {
  proof_id: string;
  principal_id: string;
  authenticated_session_id: string;
  interaction_id: string;
  operation_fingerprint: string;
  user_decision: 'approve';
  issued_at: string;
  expires_at: string;
  provenance: { kind: string; channel: string; contract: string };
}

export interface AuthorizationDecision {
  decision_id: string;
  result: 'allow';
  proof_id: string;
  operation_fingerprint: string;
  reason: string;
  decided_at: string;
}

export interface AuthorizationPermit {
  permit_id: string;
  token: string;
  decision_id: string;
  proof_id: string;
  operation_fingerprint: string;
  session_id: string;
  issued_at: string;
  expires_at: string;
}

export interface CapabilityExecutionAuthorization {
  state: 'challenge' | 'authorized' | 'consumed';
  challenge?: AuthorizationChallenge;
  proof?: UserAuthorizationProof;
  decision?: AuthorizationDecision;
  permit?: AuthorizationPermit;
  permit_id?: string;
  decision_id?: string;
  proof_id?: string;
  operation_fingerprint?: string;
}

export interface CapabilityExecutionResponse {
  ok: boolean;
  receipt?: CapabilityReceipt;
  authorization?: CapabilityExecutionAuthorization;
}
