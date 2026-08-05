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
  runtime: { kind?: string; entrypoint?: string; timeout_s?: number };
  configuration_schema: CapabilityObjectSchema;
  input_schema: CapabilityObjectSchema;
  config: Record<string, unknown>;
  digest: string;
  installed_at: string;
  last_run_at: string | null;
  last_status: string;
  last_receipt_id: string | null;
  tags: string[];
}

export interface CapabilityReceipt {
  receipt_id: string;
  execution_id: string;
  capability_id: string;
  capability_version: string;
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

export interface CapabilityExecutionResponse {
  ok: boolean;
  receipt: CapabilityReceipt;
}
