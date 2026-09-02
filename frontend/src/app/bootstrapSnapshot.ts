import type { UiAction, UiBootstrapSnapshot } from '@/contracts/backend';
import { readRecord, readText, toStringList } from '@/shared/unknownValue';

function toNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function toBoolean(value: unknown): boolean | undefined {
  return typeof value === 'boolean' ? value : undefined;
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value)
    ? value.filter((entry) => entry && typeof entry === 'object' && !Array.isArray(entry)) as Array<Record<string, unknown>>
    : [];
}

function extractRecordArray(value: unknown, keys: string[]): Array<Record<string, unknown>> {
  if (Array.isArray(value)) return asRecordArray(value);
  const data = readRecord(value);
  for (const key of keys) {
    if (Array.isArray(data[key])) return asRecordArray(data[key]);
  }
  return [];
}

function readReceiptId(receipt: unknown): string | undefined {
  const data = readRecord(receipt);
  return readText(data.envelope_id || data.id || data.receipt_id);
}

function readCertificationStatus(value: unknown): string | undefined {
  const data = readRecord(value);
  return readText(data.status || data.state);
}

function readStringRecord(value: unknown): Record<string, string> {
  return Object.fromEntries(
    Object.entries(readRecord(value)).map(([key, entry]) => [key, String(entry || '')])
  );
}

function readMenuStateValue(raw: any): Record<string, unknown> {
  return readRecord(raw?.menu_state || raw?.session?.menu_state || raw?.status?.menu_state);
}

function readMenuStateText(value: unknown): string {
  return String(value || '').trim();
}

function normalizeActions(snapshot: UiBootstrapSnapshot): UiAction[] {
  const actions: UiAction[] = [];
  const enabled = snapshot.permissions.canChat;
  actions.push({
    id: 'open-chat', label: 'Abrir Inicio', kind: 'navigate', enabled, visible: true,
    reasonDisabled: enabled ? undefined : 'El workspace no autoriza el chat', payload: { section: 'home' }
  });
  actions.push({
    id: 'inspect-system', label: 'Comprobar sistema', kind: 'inspect', enabled: true, visible: true,
    payload: { command: '/status' }
  });
  if (snapshot.permissions.canInspectContext) {
    actions.push({
      id: 'inspect-context', label: 'Comprobar contexto', kind: 'inspect', enabled: true, visible: true,
      payload: { command: '/context inspect' }
    });
  }
  if (snapshot.permissions.canViewEvidence) {
    actions.push({
      id: 'view-evidence', label: 'Revisar evidencia', kind: 'navigate', enabled: true, visible: true,
      payload: { section: 'evidence' }
    });
  }
  if (snapshot.workspace.manifestState === 'missing') {
    actions.push({
      id: 'workspace-init', label: 'Preparar workspace', kind: 'mutation',
      enabled: snapshot.permissions.canInitializeWorkspace, visible: true,
      reasonDisabled: snapshot.permissions.canInitializeWorkspace ? undefined : 'El backend no permite inicializarlo',
      payload: { endpoint: 'project:init' }
    });
  }
  if (snapshot.permissions.canLinkWorkspace && snapshot.workspace.root) {
    actions.push({
      id: 'workspace-link', label: 'Vincular workspace', kind: 'mutation', enabled: true, visible: true,
      payload: { endpoint: 'project:link', root: snapshot.project.root || snapshot.workspace.repoRoot || snapshot.workspace.root }
    });
  }
  if (snapshot.workspace.manifestState === 'invalid') {
    actions.push({
      id: 'workspace-repair', label: 'Reparar workspace', kind: 'danger',
      enabled: snapshot.permissions.canRepairWorkspace, visible: true,
      reasonDisabled: snapshot.permissions.canRepairWorkspace ? undefined : 'La reparación no está autorizada',
      payload: { endpoint: 'project:init' }
    });
  }
  return actions;
}

export function buildSnapshot(raw: any): UiBootstrapSnapshot | null {
  if (!raw) return null;
  const status = raw.status || {};
  const session = raw.session || {};
  const menuStateRaw = readMenuStateValue(raw);
  const workspaceMeta = raw.workspace || {};
  const workspaceBinding = readRecord(workspaceMeta.binding);
  const workspaceStatus = readRecord(workspaceMeta.status);
  const binding = session.binding || {};
  const statusWorkspaceState = readRecord(status.workspace_state);
  const sessionWorkspaceState = readRecord(session.workspace_state);
  const projectRoot = String(
    status.project_root || status.repo_root || workspaceMeta.root || workspaceBinding.project_root
    || workspaceStatus.project_root || binding.project_root || ''
  );
  // `root` is the user project scope. `.gabo` remains an internal state root
  // and must never become the conversation workspace.
  const scopeRoot = String(
    status.workspace_scope_root || workspaceMeta.scope_root || workspaceBinding.workspace_scope_root
    || workspaceStatus.workspace_scope_root || binding.workspace_scope_root || projectRoot || ''
  );
  const workspaceRoot = scopeRoot;
  const mirrorRoot = String(status.workspace_mirror_root || binding.workspace_mirror_root || '');
  const contextRoot = String(status.workspace_context_root || binding.workspace_context_root || '');
  const authorizedRoot = String(status.authorized_root || binding.authorized_root || scopeRoot || '');
  const repoRoot = String(status.repo_root || binding.repo_root || projectRoot || '');
  const repoBranch = String(status.repo_branch || binding.repo_branch || '');
  const activeBridges = toStringList(status.active_bridges || session.active_bridges);
  const bindingConfirmed = toBoolean(statusWorkspaceState.binding_confirmed)
    ?? toBoolean(sessionWorkspaceState.binding_confirmed)
    ?? toBoolean(binding.binding_confirmed)
    ?? toBoolean(status.binding_confirmed)
    ?? false;
  const bindingReason = String(
    statusWorkspaceState.binding_reason ?? sessionWorkspaceState.binding_reason
    ?? binding.binding_reason ?? status.binding_reason ?? ''
  );
  // NOTE: bindingReason intentionally uses ?? (nullish) not || so an explicitly
  // empty authoritative reason does not fall through to a stale legacy value.
  const workspaceState = String(
    statusWorkspaceState.workspace_state || statusWorkspaceState.state
    || sessionWorkspaceState.workspace_state || sessionWorkspaceState.state
    || (typeof status.workspace_state === 'string' ? status.workspace_state : '')
    || (typeof session.workspace_state === 'string' ? session.workspace_state : '')
  );
  const seedSuggested = Boolean(workspaceMeta.seed_suggested);
  const seedReason = String(workspaceMeta.seed_reason || '');
  const manifestState: UiBootstrapSnapshot['workspace']['manifestState'] = workspaceState.includes('legacy')
    ? 'legacy' : workspaceState.includes('invalid') ? 'invalid' : workspaceState.includes('missing')
      ? 'missing' : bindingConfirmed ? 'valid' : workspaceRoot ? 'unknown' : 'missing';
  const health = status.health || {};
  const healthDetail = readText(health.detail);
  const healthLatencyMs = toNumber(health.latency_ms);
  const objective = String(status.objective || binding.objective || '');
  const activeAgent = String(status.active_agent || session.active_agent || '');
  const lastEnvelope = readRecord(raw.last_envelope);
  const lastEnvelopeMeta = readRecord(lastEnvelope.metadata);
  const lastReceipt = readRecord(raw.last_receipt);
  const lastReceiptMeta = readRecord(lastReceipt.metadata);
  const codeTaskClassification = readRecord(status.code_task || lastEnvelopeMeta.code_task || lastReceiptMeta.code_task);
  const codeTaskContract = readRecord(status.code_task_contract || lastEnvelopeMeta.code_task_contract || lastReceiptMeta.code_task_contract);
  const codeTaskContext = readRecord(lastEnvelopeMeta.code_context || lastReceiptMeta.code_context);
  const lastReceiptId = readReceiptId(status.last_receipt);
  const certificationStatus = readCertificationStatus(status.context_certification);
  const menuState = {
    activeCenter: readMenuStateText(menuStateRaw.activeCenter || status.active_center || session.active_center),
    currentScreen: readMenuStateText(menuStateRaw.currentScreen || status.current_screen || session.current_screen),
    operationState: readMenuStateText(menuStateRaw.operationState || status.operation_state || session.operation_state),
    recommendedAction: readMenuStateText(menuStateRaw.recommendedAction || status.recommended_action || session.recommended_action),
    allowedActions: toStringList(menuStateRaw.allowedActions || status.allowed_actions || session.allowed_actions),
    secondaryActions: toStringList(menuStateRaw.secondaryActions || status.secondary_actions || session.secondary_actions),
    blockedActions: toStringList(menuStateRaw.blockedActions || status.blocked_actions || session.blocked_actions),
    blockedReasons: readStringRecord(menuStateRaw.blockedReasons || status.blocked_reasons || session.blocked_reasons),
    pendingWork: readMenuStateText(menuStateRaw.pendingWork || status.pending_work || session.pending_work),
    latestResult: readMenuStateText(menuStateRaw.latestResult || status.latest_result || session.latest_result),
    version: readMenuStateText(menuStateRaw.version || status.contract_version || status.schema_version || raw.version)
  };
  const rawPermissions = readRecord(raw.permissions);
  const systemState: UiBootstrapSnapshot['system']['state'] = health.ok === false
    ? 'error' : bindingConfirmed ? 'confirmed' : bindingReason || ['invalid', 'legacy', 'missing'].includes(manifestState)
      ? 'blocked' : !raw.status ? 'loading' : 'unknown';
  const contextRevision = status.context_revision ?? session.status?.context_revision;
  const contextState: UiBootstrapSnapshot['context']['state'] = certificationStatus === 'CERTIFIED'
    ? 'confirmed' : contextRevision && lastReceiptId ? 'partial' : contextRevision ? 'stale'
      : bindingConfirmed ? 'unknown' : 'blocked';
  const explicitModelState = String(status.model_state || '').toLowerCase();
  const modelState: UiBootstrapSnapshot['model']['state'] = explicitModelState === 'error'
    ? 'error' : explicitModelState === 'degraded' ? 'degraded'
      : (status.provider || session.provider) && (status.model || session.model || status.effective_model)
        ? 'confirmed' : 'unknown';
  const effectiveProvider = String(status.provider || session.provider || '');
  const effectiveModel = String(status.model || session.model || status.effective_model || '');
  const permissions = {
    canChat: toBoolean(rawPermissions.canChat) ?? (bindingConfirmed && Boolean(effectiveProvider) && Boolean(effectiveModel)),
    canInitializeWorkspace: toBoolean(rawPermissions.canInitializeWorkspace) ?? !workspaceRoot,
    canLinkWorkspace: toBoolean(rawPermissions.canLinkWorkspace) ?? (Boolean(workspaceRoot) && !bindingConfirmed),
    canRepairWorkspace: toBoolean(rawPermissions.canRepairWorkspace) ?? (Boolean(workspaceRoot) && /manifest|workspace root|scope|legacy|invalid/i.test(bindingReason || workspaceState)),
    canSeedWorkspace: toBoolean(rawPermissions.canSeedWorkspace) ?? Boolean(workspaceRoot),
    canRunTools: toBoolean(rawPermissions.canRunTools) ?? (bindingConfirmed && activeBridges.length > 0),
    canInspectContext: toBoolean(rawPermissions.canInspectContext) ?? (bindingConfirmed && Boolean(contextRevision || lastReceiptId)),
    canViewEvidence: toBoolean(rawPermissions.canViewEvidence) ?? Boolean(lastReceiptId || (Array.isArray(raw.history?.messages) && raw.history.messages.length)),
    canStopPipeline: toBoolean(rawPermissions.canStopPipeline) ?? Boolean(objective || contextRevision),
    canRetryPipeline: toBoolean(rawPermissions.canRetryPipeline) ?? Boolean(objective || lastReceiptId || contextRevision)
  };
  const sessionState: UiBootstrapSnapshot['session']['state'] = session.session_id
    ? bindingConfirmed ? 'valid' : /manifest|workspace root|scope|legacy|invalid/i.test(bindingReason) ? 'blocked' : 'recoverable'
    : 'missing';
  const codeTask = Object.keys(codeTaskClassification).length || Object.keys(codeTaskContract).length || Object.keys(codeTaskContext).length
    ? ({
      classification: Object.keys(codeTaskClassification).length ? codeTaskClassification : undefined,
      contract: Object.keys(codeTaskContract).length ? codeTaskContract : undefined,
      context: Object.keys(codeTaskContext).length ? codeTaskContext : undefined
    } as UiBootstrapSnapshot['codeTask'])
    : undefined;

  const snapshot: UiBootstrapSnapshot = {
    system: {
      state: systemState, backendAvailable: true,
      version: String(status.framework_version || status.version || ''),
      apiVersion: String(status.api_version || ''), contractVersion: String(status.contract_version || ''),
      schemaVersion: String(status.schema_version || ''), healthDetail: healthDetail || undefined,
      healthLatencyMs, bindingReason: bindingReason || undefined, objective: objective || undefined,
      activeAgent: activeAgent || undefined, activeBridges: activeBridges.length ? activeBridges : undefined,
      errorCode: readText(status.error_code || status.health?.error_code || '')
    },
    framework: { root: String(status.framework_root || ''), version: String(status.framework_version || status.version || ''), confirmed: Boolean(status.framework_root) },
    project: { root: projectRoot || undefined, state: projectRoot ? bindingConfirmed ? 'confirmed' : 'invalid' : 'not_detected' },
    workspace: {
      id: String(status.workspace_id || session.binding?.workspace_id || ''), root: workspaceRoot || undefined,
      scopeRoot: scopeRoot || undefined, mirrorRoot: mirrorRoot || undefined, contextRoot: contextRoot || undefined,
      authorizedRoot: authorizedRoot || undefined, repoRoot: repoRoot || undefined, repoBranch: repoBranch || undefined,
      bindingReason: bindingReason || undefined, mirrorReady: Boolean(status.workspace_mirror_ready), manifestState,
      linkedToSession: bindingConfirmed, seedSuggested, seedReason: seedReason || undefined
    },
    session: { id: String(status.session_id || session.session_id || ''), state: sessionState, activeAgent: activeAgent || undefined },
    model: {
      provider: String(status.provider || session.provider || ''), adapter: String(status.adapter || ''),
      runtime: String(status.runtime || status.model_runtime || ''), configuredModel: String(status.model || session.model || ''),
      effectiveModel: String(status.effective_model || status.model || session.model || ''), state: modelState
    },
    context: {
      state: contextState, revision: contextRevision || undefined,
      occupied: typeof status.context_occupied === 'number' ? status.context_occupied : undefined,
      available: typeof status.context_available === 'number' ? status.context_available : undefined,
      limit: typeof status.context_limit === 'number' ? status.context_limit : undefined,
      reserve: typeof status.context_reserve === 'number' ? status.context_reserve : undefined,
      limitingFactor: String(status.context_limiting_factor || ''), receiptId: lastReceiptId || undefined,
      certificationStatus: certificationStatus || undefined
    },
    permissions: { ...permissions }, capabilities: (status.capabilities as UiBootstrapSnapshot['capabilities']) || undefined,
    error: raw.error && typeof raw.error === 'object' ? raw.error : undefined,
    evidence: extractRecordArray(raw.evidence, ['items', 'receipts', 'claims', 'latest']),
    jobs: extractRecordArray(raw.jobs, ['jobs', 'items']), codeTask, recommendedActions: [], menuState
  };
  snapshot.recommendedActions = normalizeActions(snapshot);
  return snapshot;
}
