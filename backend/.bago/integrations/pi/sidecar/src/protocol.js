"use strict";

/**
 * protocol.js -- parity with backend/.bago/integrations/pi/protocol.py
 *
 * Single source of truth for the JSONL protocol. Any drift MUST be
 * caught by tests/integrations/pi/test_sidecar_contract.py.
 */

const BRIDGE_PROTOCOL_VERSION = "0.1.0";

const ALLOWED_TOOLS = new Set(["read", "ls", "grep", "find"]);

const ALLOWED_NETWORK_MODES = new Set([
  "none",
  "provider_endpoints_only",
  "disabled",
]);

const F0 = new Set([
  "runtime_attested",
  "provider_attested",
  "model_output_delta",
  "usage_reported",
  "pi_finished",
]);

const ALLOWED_EVENTS_BY_PHASE = Object.freeze({
  0: F0,
  1: F0,
  2: new Set([
    ...F0,
    "tool_requested",
    "tool_policy_decided",
    "tool_result_attached",
  ]),
  3: new Set([
    ...F0,
    "tool_requested",
    "tool_policy_decided",
    "tool_result_attached",
    "agent_step_started",
    "agent_step_finished",
  ]),
});

const MAX_EVENT_BYTES = 256 * 1024;
const MAX_EVENTS_TOTAL = 4096;
const MAX_FIELDS_PER_EVENT = 32;

const ALLOWED_EVENT_FIELDS = new Set([
  "execution_id",
  "sequence_number",
  "event_id",
  "event_type",
  "timestamp",
  "payload",
  "previous_event_hash",
  "event_hash",
  "redaction_applied",
  "source",
]);

const ALLOWED_REQUEST_FIELDS = new Set([
  "protocol_version",
  "bridge_request_id",
  "execution_id",
  "correlation_id",
  "request_nonce",
  "issued_at",
  "deadline",
  "session_id",
  "session_revision",
  "workspace_id",
  "project_root",
  "workspace_root",
  "workspace_scope_root",
  "context_envelope_id",
  "context_envelope_digest",
  "policy_profile",
  "policy_digest",
  "capability_claims",
  "requested_provider",
  "requested_adapter",
  "requested_runtime",
  "requested_model",
  "credential_ref",
  "input",
  "output_limits",
]);

const OPTIONAL_REQUEST_FIELDS = new Set([
  "requested_adapter",
  "requested_runtime",
]);

class ProtocolError extends Error {
  constructor(code, message) {
    super(`${code}: ${message}`);
    this.code = code;
    this.name = "ProtocolError";
  }
}

class UnknownEventError extends ProtocolError {
  constructor(eventType, phase) {
    super("PI_UNKNOWN_EVENT", `event_type not in allowlist: ${eventType} (phase=${phase})`);
    this.name = "UnknownEventError";
  }
}

class BridgeProtocolViolation extends ProtocolError {
  constructor(message) {
    super("BRIDGE_PROTOCOL_VIOLATION", message);
    this.name = "BridgeProtocolViolation";
  }
}

class OutputLimitExceeded extends ProtocolError {
  constructor(message) {
    super("OUTPUT_LIMIT_EXCEEDED", message);
    this.name = "OutputLimitExceeded";
  }
}

function validateRequest(raw) {
  if (typeof raw !== "object" || raw === null) {
    throw new BridgeProtocolViolation("request must be an object");
  }
  for (const key of Object.keys(raw)) {
    if (!ALLOWED_REQUEST_FIELDS.has(key)) {
      throw new BridgeProtocolViolation(`unknown request field: ${key}`);
    }
  }
  for (const required of ALLOWED_REQUEST_FIELDS) {
    if (OPTIONAL_REQUEST_FIELDS.has(required)) continue;
    if (!(required in raw)) {
      throw new BridgeProtocolViolation(`missing required field: ${required}`);
    }
  }
  if (raw.protocol_version !== BRIDGE_PROTOCOL_VERSION) {
    throw new BridgeProtocolViolation(
      `protocol_version mismatch: expected ${BRIDGE_PROTOCOL_VERSION}, got ${String(raw.protocol_version)}`,
    );
  }
  return raw;
}

function validateEventType(eventType, phase) {
  const allowed = ALLOWED_EVENTS_BY_PHASE[phase];
  if (!allowed) {
    throw new BridgeProtocolViolation(`invalid phase: ${phase}`);
  }
  if (!allowed.has(eventType)) {
    throw new UnknownEventError(eventType, phase);
  }
}

function checkEventSize(line) {
  const bytes = Buffer.byteLength(line, "utf-8");
  if (bytes > MAX_EVENT_BYTES) {
    throw new OutputLimitExceeded(
      `event exceeds ${MAX_EVENT_BYTES} bytes (got ${bytes})`,
    );
  }
}

module.exports = {
  BRIDGE_PROTOCOL_VERSION,
  ALLOWED_TOOLS,
  ALLOWED_NETWORK_MODES,
  ALLOWED_EVENTS_BY_PHASE,
  MAX_EVENT_BYTES,
  MAX_EVENTS_TOTAL,
  MAX_FIELDS_PER_EVENT,
  ALLOWED_EVENT_FIELDS,
  ALLOWED_REQUEST_FIELDS,
  OPTIONAL_REQUEST_FIELDS,
  ProtocolError,
  UnknownEventError,
  BridgeProtocolViolation,
  OutputLimitExceeded,
  validateRequest,
  validateEventType,
  checkEventSize,
};
