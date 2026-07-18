export type SystemState = 'confirmed' | 'loading' | 'degraded' | 'error' | 'unknown' | 'blocked';
export type GlobalMode = 'normal' | 'focus' | 'review';
export type ChatMode = 'live' | 'trace';
export type InspectorLevel = 'summary' | 'detail' | 'raw';
export type ActiveSection = 'home' | 'chat' | 'workspace' | 'graph' | 'pipeline' | 'evidence' | 'context' | 'system';

export type ContextTargetKind =
  | 'screen.home'
  | 'screen.chat'
  | 'workspace.file'
  | 'workspace.directory'
  | 'workspace.source'
  | 'pipeline.step'
  | 'pipeline.surface'
  | 'evidence.item'
  | 'context.item'
  | 'graph.node'
  | 'system.router'
  | 'system.provider'
  | 'system.surface'
  | 'screen.other'
  | 'unknown';

export interface BackendHealth {
  ok?: boolean;
  detail?: string;
  latency_ms?: number;
  [key: string]: unknown;
}

export interface BackendReceipt {
  envelope_id?: string;
  receipt_id?: string;
  status?: string;
  state?: string;
  [key: string]: unknown;
}

export interface BackendContextCertification {
  status?: string;
  [key: string]: unknown;
}

export interface BackendErrorEnvelope {
  ok?: boolean;
  state?: 'ok' | 'failed' | 'blocked' | 'degraded' | 'unknown';
  error_code?: string;
  message?: string;
  evidence?: Array<Record<string, unknown>>;
  execution_id?: string;
  receipt_id?: string;
  [key: string]: unknown;
}

export interface ContextEnvelope {
  envelope_id?: string;
  session_id?: string;
  workspace_id?: string;
  context_revision?: number | string;
  input?: Record<string, unknown>;
  selected_files?: string[];
  tools?: string[];
  [key: string]: unknown;
}

export interface ContextReceipt {
  receipt_id?: string;
  envelope_id?: string;
  execution_id?: string;
  context_revision?: number | string;
  state?: 'confirmed' | 'partial' | 'stale' | 'blocked' | 'unknown';
  evidence?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface EvidenceItem {
  id?: string;
  claim_id?: string;
  receipt_id?: string;
  execution_id?: string;
  type?: string;
  state?: string;
  message?: string;
  [key: string]: unknown;
}

export interface JobStep {
  step_id?: string;
  label?: string;
  status?: string;
  started_at?: string;
  ended_at?: string;
  evidence_id?: string;
  receipt_id?: string;
  [key: string]: unknown;
}

export interface JobItem {
  execution_id?: string;
  status?: string;
  started_at?: string;
  updated_at?: string;
  receipt_id?: string;
  error_code?: string;
  steps?: JobStep[];
  evidence?: EvidenceItem[];
  [key: string]: unknown;
}

export interface CodeTaskPlanContract {
  read_files?: string[];
  edit_files?: string[];
  create_files?: string[];
  verify_steps?: string[];
  finish_message?: string;
  requires_model_review?: boolean;
  notes?: string[];
}

export interface CodeTaskContractSnapshot {
  task_id?: string;
  operation?: string;
  language?: string;
  objective?: string;
  target_files?: string[];
  allowed_files?: string[];
  forbidden_paths?: string[];
  constraints?: string[];
  acceptance?: string[];
  classification_reasons?: string[];
  plan?: CodeTaskPlanContract;
  refused?: boolean;
  refusal_reason?: string;
  extra?: Record<string, unknown>;
}

export interface CodeTaskSnapshot {
  classification?: Record<string, unknown>;
  contract?: CodeTaskContractSnapshot;
  context?: Record<string, unknown>;
}

export interface CapabilityMap {
  can_chat?: boolean;
  can_run_command?: boolean;
  can_initialize_workspace?: boolean;
  can_link_workspace?: boolean;
  can_repair_workspace?: boolean;
  can_read_files?: boolean;
  can_write_files?: boolean;
  can_retry_pipeline?: boolean;
  can_stop_pipeline?: boolean;
  can_view_raw?: boolean;
  [key: string]: boolean | undefined;
}

export interface UiAction {
  id: string;
  label: string;
  kind: 'navigate' | 'command' | 'mutation' | 'inspect' | 'danger';
  enabled: boolean;
  visible: boolean;
  reasonDisabled?: string;
  confirmation?: {
    required: boolean;
    title?: string;
    description?: string;
  };
  payload?: Record<string, unknown>;
}

export interface BackendMenuState {
  activeCenter?: 'Inicio' | 'Trabajo' | 'Workspace' | 'Control' | 'Sistema' | string;
  currentScreen?: string;
  operationState?: string;
  recommendedAction?: string;
  allowedActions?: string[];
  secondaryActions?: string[];
  blockedActions?: string[];
  blockedReasons?: Record<string, string>;
  pendingWork?: string;
  latestResult?: string;
  version?: string;
  [key: string]: unknown;
}

export interface UiBootstrapSnapshot {
  system: {
    state: SystemState;
    backendAvailable: boolean;
    version?: string;
    apiVersion?: string;
    contractVersion?: string;
    schemaVersion?: string;
    healthDetail?: string;
    healthLatencyMs?: number;
    bindingReason?: string;
    objective?: string;
    activeAgent?: string;
    activeBridges?: string[];
    errorCode?: string;
  };
  framework: {
    root?: string;
    version?: string;
    confirmed: boolean;
  };
  project: {
    root?: string;
    state: 'confirmed' | 'not_detected' | 'invalid' | 'legacy_detected' | 'unknown';
  };
  workspace: {
    id?: string;
    root?: string;
    scopeRoot?: string;
    mirrorRoot?: string;
    contextRoot?: string;
    authorizedRoot?: string;
    repoRoot?: string;
    repoBranch?: string;
    bindingReason?: string;
    mirrorReady?: boolean;
    manifestState: 'valid' | 'invalid' | 'missing' | 'legacy' | 'unknown';
    linkedToSession: boolean;
    seedSuggested?: boolean;
    seedReason?: string;
  };
  session: {
    id?: string;
    state: 'valid' | 'recoverable' | 'missing' | 'blocked' | 'unknown';
    activeAgent?: string;
  };
  model: {
    provider?: string;
    adapter?: string;
    runtime?: string;
    configuredModel?: string;
    effectiveModel?: string;
    state: 'confirmed' | 'degraded' | 'unknown' | 'error';
  };
  context: {
    state: 'confirmed' | 'partial' | 'stale' | 'blocked' | 'unknown';
    revision?: number | string;
    occupied?: number;
    available?: number;
    limit?: number;
    reserve?: number;
    limitingFactor?: string;
    receiptId?: string;
    certificationStatus?: string;
  };
  permissions: {
    canChat: boolean;
    canInitializeWorkspace: boolean;
    canLinkWorkspace: boolean;
    canRepairWorkspace: boolean;
    canSeedWorkspace: boolean;
    canRunTools: boolean;
    canInspectContext: boolean;
    canViewEvidence: boolean;
    canStopPipeline: boolean;
    canRetryPipeline: boolean;
  };
  capabilities?: CapabilityMap;
  error?: BackendErrorEnvelope | null;
  evidence?: EvidenceItem[];
  jobs?: JobItem[];
  codeTask?: CodeTaskSnapshot;
  recommendedActions: UiAction[];
  menuState?: BackendMenuState;
}

export interface BackendStatus {
  [key: string]: unknown;
  session_id?: string;
  provider?: string;
  model?: string;
  contract_version?: string;
  api_version?: string;
  schema_version?: string;
  project_root?: string;
  workspace_state_root?: string;
  workspace_scope_root?: string;
  workspace_mirror_root?: string;
  workspace_context_root?: string;
  workspace_work_root?: string;
  workspace_mirror_ready?: boolean;
  workspace_mirror_error?: string;
  workspace_mirror_required_bytes?: number;
  workspace_mirror_free_bytes?: number;
  workspace_id?: string;
  framework_root?: string;
  framework_version?: string;
  binding_confirmed?: boolean;
  binding_reason?: string;
  repo_root?: string;
  repo_branch?: string;
  authorized_root?: string;
  objective?: string;
  context_revision?: number | string;
  health?: BackendHealth;
  last_receipt?: BackendReceipt | null;
  context_certification?: BackendContextCertification | null;
  context_measure?: Record<string, unknown> | null;
  context_benchmark?: Record<string, unknown> | null;
  active_agent?: string;
  active_bridges?: string[];
  capabilities?: CapabilityMap;
  model_catalog_mode?: string;
  model_state?: string;
  context_state?: string;
  active_center?: string;
  current_screen?: string;
  operation_state?: string;
  recommended_action?: string;
  allowed_actions?: string[];
  secondary_actions?: string[];
  blocked_actions?: string[];
  blocked_reasons?: Record<string, string>;
  pending_work?: string;
  latest_result?: string;
  menu_state?: BackendMenuState;
}

export interface BackendSession {
  [key: string]: unknown;
  session_id?: string;
  provider?: string;
  model?: string;
  status?: BackendStatus;
  workspace_state?: Record<string, unknown>;
  welcome_state?: Record<string, unknown>;
  menu_state?: BackendMenuState;
  binding?: Record<string, unknown>;
  active_agent?: string;
  tool_calling?: boolean;
  model_catalog_mode?: string;
}

export interface BackendProviders {
  providers?: Array<Record<string, unknown>>;
  mode?: string;
}

export interface BackendRouterEntry {
  provider?: string;
  model_id?: string;
  wire_name?: string;
  context_tokens?: number;
  best_for?: string;
  available?: boolean;
  selected?: boolean;
  key?: string;
  [key: string]: unknown;
}

export interface BackendRouterList {
  entries?: BackendRouterEntry[];
  selected_count?: number;
  auto_switch?: boolean;
  last_pick?: string;
  last_pick_at?: string;
  [key: string]: unknown;
}

export interface BackendRouterPolicy extends BackendRouterList {
  ok?: boolean;
  state_root?: string;
  selected?: string[];
}

export interface BackendMenu {
  [key: string]: unknown;
  sections?: Array<Record<string, unknown>>;
  visible_sections?: string[];
}

export interface BackendRoutes {
  ok?: boolean;
  routes?: Array<Record<string, unknown>>;
  count?: number;
  api_prefixes?: string[];
  auth?: string;
}

export interface BackendHistory {
  session_id?: string;
  messages?: Array<Record<string, unknown>>;
  count?: number;
}

export interface BackendFileSourceRoot {
  key?: string;
  label?: string;
  path?: string;
  kind?: string;
  read_only?: boolean | string;
  [key: string]: unknown;
}

export interface BackendCommandResult {
  ok?: boolean;
  state?: 'ok' | 'done' | 'failed' | 'blocked' | 'degraded' | 'unknown';
  message?: string;
  action?: string;
  execution_id?: string;
  session_id?: string;
  provider?: string;
  model?: string;
  data?: unknown;
  plan?: unknown;
  receipt_id?: string;
  context_receipt?: ContextReceipt | null;
  evidence?: EvidenceItem[];
  error_code?: string;
  warnings?: string[];
}

export interface ChatTurn {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'command';
  text: string;
  status?: 'sending' | 'running' | 'validating' | 'done' | 'failed' | 'blocked';
  receipt?: Record<string, unknown> | null;
  raw?: unknown;
  timestamp: string;
}

export interface SelectionRecord {
  id: string;
  kind: string;
  targetKind?: ContextTargetKind;
  title: string;
  summary: string;
  detail: string[];
  raw: unknown;
}

export interface OpeningDecision {
  id:
    | 'enter_directly'
    | 'show_recovery'
    | 'show_workspace_link'
    | 'show_workspace_repair'
    | 'show_workspace_init'
    | 'show_legacy_migration'
    | 'show_blocked_state';
  label: string;
  reason: string;
  actionLabel: string;
  targetSection: ActiveSection;
}

export interface UiBootData {
  status?: BackendStatus;
  session?: BackendSession;
  providers?: BackendProviders;
  menu?: BackendMenu;
  routes?: BackendRoutes;
  history?: BackendHistory;
  files?: Record<string, unknown>;
  evidence?: Record<string, unknown>;
  jobs?: Record<string, unknown>;
  schedule?: Record<string, unknown>;
  sources?: Record<string, unknown>;
  router_list?: BackendRouterList;
  router_policy?: BackendRouterPolicy;
}
