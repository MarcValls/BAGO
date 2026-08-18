"use strict";

/**
 * main.js -- sidecar entry point.
 *
 * Reads ONE BridgeRequest line from stdin. Emits a stream of
 * BridgeEvent lines on stdout. Refuses everything else.
 *
 * The sidecar is intentionally minimal: it does NOT load any SDK
 * at boot. It only imports the local mock provider. Wiring a real
 * provider happens in Fase 2+ under explicit CRIT approval.
 */

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const {
  BRIDGE_PROTOCOL_VERSION,
  ProtocolError,
  validateEventType,
  validateRequest,
} = require("./protocol.js");
const { attest } = require("./provider_attestation.js");
const { createMockProvider } = require("./provider_runner.js");
const { buildReport } = require("./runtime_guard.js");

const SIDECAR_VERSION = "0.1.0";
const PHASE = Number(process.env.BAGO_BRIDGE_PHASE) || 3;
const PKG_JSON = path.join(__dirname, "..", "package.json");
const PKG_LOCK = path.join(__dirname, "..", "package-lock.json");

function sha256File(p) {
  try {
    const data = fs.readFileSync(p);
    return crypto.createHash("sha256").update(data).digest("hex").slice(0, 16);
  } catch {
    return "";
  }
}

function hashEvent(prev) {
  // Stable: sort keys, then sha256 of the JSON string.
  const sorted = Object.keys(prev).sort();
  const stable = {};
  for (const k of sorted) stable[k] = prev[k];
  return crypto
    .createHash("sha256")
    .update(JSON.stringify(stable))
    .digest("hex");
}

class Streamer {
  constructor(executionId) {
    this.executionId = executionId;
    this.seq = 0;
    this.prev = "0".repeat(16);
  }

  emit(eventType, payload) {
    validateEventType(eventType, PHASE);
    this.seq += 1;
    const eventId = `sidecar-${this.seq}`;
    const timestamp = new Date().toISOString();
    const pre = {
      execution_id: this.executionId,
      sequence_number: this.seq,
      event_id: eventId,
      event_type: eventType,
      timestamp,
      payload,
      previous_event_hash: this.prev,
      redaction_applied: false,
      source: "pi_sidecar",
    };
    const eventHash = hashEvent(pre);
    const ev = { ...pre, event_hash: eventHash };
    process.stdout.write(JSON.stringify(ev) + "\n");
    this.prev = eventHash;
  }
}

function die(code, message) {
  process.stderr.write(`${code}: ${message}\n`);
  process.exit(1);
}

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf-8");
}

async function main() {
  const raw = (await readStdin()).trim();
  if (!raw) {
    die("BRIDGE_PROTOCOL_VIOLATION", "no request on stdin");
  }
  let parsed;
  try {
    parsed = JSON.parse(raw.split("\n")[0]);
  } catch (e) {
    die("BRIDGE_PROTOCOL_VIOLATION", `invalid json: ${e.message}`);
  }
  let req;
  try {
    req = validateRequest(parsed);
  } catch (e) {
    if (e instanceof ProtocolError) {
      die(e.code, e.message);
    }
    throw e;
  }

  const streamer = new Streamer(req.execution_id);
  const sidecarArtifactHash = sha256File(PKG_JSON);
  const piLockfileHash = sha256File(PKG_LOCK);
  const piPackageVersion = "0.0.0-mock";

  // 1. runtime_attested
  const report = buildReport(
    req.workspace_scope_root,
    SIDECAR_VERSION,
    piLockfileHash,
  );
  streamer.emit("runtime_attested", report);

  // 2. provider_attested
  const mock = createMockProvider(
    req.requested_provider,
    req.requested_model,
    "mock://bago-pi-sidecar/" + req.requested_provider,
    piPackageVersion,
    piLockfileHash,
    sidecarArtifactHash,
    { network_mode: "none" },
  );
  const identity = mock.identity();
  const att = attest(
    req.requested_provider,
    req.requested_model,
    identity,
    req.credential_ref,
    SIDECAR_VERSION,
  );
  streamer.emit("provider_attested", att);

  // 3. inference via mock
  const input = req.input || {};
  const messages = Array.isArray(input.messages) ? input.messages : [];
  const system = typeof input.system === "string" ? input.system : "";
  const reply = mock.call({
    messages,
    model: req.requested_model,
    system,
    temperature: 0.0,
    max_tokens: null,
  });
  streamer.emit("model_output_delta", { delta: reply.content });
  streamer.emit("usage_reported", reply.usage);

  // 4. tool requests (Fase 2)
  // Si el input declara `tool_requests`, el sidecar emite un
  // `tool_requested` por cada uno, encadenado al log actual. El
  // bridge ejecuta la tool y emite `tool_policy_decided` +
  // `tool_result_attached` con su `ToolReceipt`.
  if (Array.isArray(input.tool_requests)) {
    for (const tr of input.tool_requests) {
      const tool = String(tr.tool || "");
      const args = (tr.arguments && typeof tr.arguments === "object") ? tr.arguments : {};
      const toolCallId = String(tr.tool_call_id || `tc-${streamer.seq + 1}`);
      // El sidecar **firma** este evento: lo encadena al log y le
      // calcula el hash. El bridge verifica la cadena y procesa.
      streamer.emit("tool_requested", {
        tool_call_id: toolCallId,
        tool,
        arguments: args,
      });
    }
  }

  streamer.emit("pi_finished", { finish_reason: reply.finish_reason });
}

if (BRIDGE_PROTOCOL_VERSION !== "0.1.0") {
  die("BRIDGE_PROTOCOL_VIOLATION", "sidecar BRIDGE_PROTOCOL_VERSION drift");
}

main().catch((e) => {
  if (e instanceof ProtocolError) {
    die(e.code, e.message);
  }
  die("BRIDGE_PROTOCOL_VIOLATION", e.message);
});
