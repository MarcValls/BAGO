"use strict";

/**
 * tool_rpc.js -- Fase 2: tool request emitter.
 *
 * En Fase 2 el sidecar **no** llama directamente al backend. El
 * sidecar formula la solicitud como un evento `tool_requested` y la
 * entrega al bridge, que ejecuta la tool dentro del proceso BAGO.
 * Esto preserva la autoridad BAGO: ninguna tool se ejecuta fuera del
 * backend.
 *
 * El RPC cliente→BAGO queda fuera de alcance: en producción el sidecar
 * enviaría el tool request por IPC (HTTP localhost o named pipe) al
 * endpoint `/integrations/pi/tools/...` que el bridge expone. En el
 * mock de Fase 2 el sidecar **solo emite el evento**; el bridge lo
 * recoge y ejecuta localmente.
 */

const { ALLOWED_TOOLS } = require("./protocol.js");

class ToolNotAllowedError extends Error {
  constructor(tool) {
    super(`tool not in allowlist: ${tool}`);
    this.code = "TOOL_NOT_ALLOWED";
    this.tool = tool;
  }
}

function validateToolName(tool) {
  if (!ALLOWED_TOOLS.has(tool)) {
    throw new ToolNotAllowedError(tool);
  }
}

function buildToolRequestedEvent(
  executionId,
  seq,
  previousHash,
  toolCallId,
  tool,
  args,
) {
  validateToolName(tool);
  return {
    execution_id: executionId,
    sequence_number: seq,
    event_id: toolCallId,
    event_type: "tool_requested",
    timestamp: new Date().toISOString(),
    payload: {
      tool_call_id: toolCallId,
      tool,
      arguments: args,
    },
    previous_event_hash: previousHash,
    event_hash: "pending-bridge-computes",
    redaction_applied: false,
    source: "pi_sidecar",
  };
}

module.exports = {
  validateToolName,
  buildToolRequestedEvent,
  ToolNotAllowedError,
  ALLOWED_TOOLS,
};
