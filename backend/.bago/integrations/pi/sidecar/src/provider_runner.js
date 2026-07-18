"use strict";

/**
 * provider_runner.js -- local mock provider for Fase 1.
 *
 * This is NOT a real provider. It exists to demonstrate the protocol
 * surface and the attestation flow. No network. No filesystem writes.
 * No tools. No skills. No extensions. No packages.
 */

function createMockProvider(
  provider,
  model,
  endpoint,
  piPackageVersion,
  piLockfileHash,
  sidecarArtifactHash,
  configEffective,
) {
  return {
    identity() {
      return {
        provider,
        model,
        endpoint,
        adapter: "mock",
        pi_package_version: piPackageVersion,
        pi_lockfile_hash: piLockfileHash,
        sidecar_artifact_hash: sidecarArtifactHash,
        fallback_used: false,
        auto_selection_used: false,
        config_effective: configEffective,
      };
    },
    call(req) {
      const sysLen = (req.system || "").length;
      const msgLen = JSON.stringify(req.messages || []).length;
      const input_tokens = Math.max(1, Math.floor((sysLen + msgLen) / 4));
      const content = `mock-reply: provider=${provider} model=${model}`;
      const output_tokens = Math.max(1, Math.floor(content.length / 4));
      return {
        content,
        finish_reason: "stop",
        usage: {
          input_tokens,
          output_tokens,
          total_tokens: input_tokens + output_tokens,
        },
      };
    },
  };
}

module.exports = { createMockProvider };
