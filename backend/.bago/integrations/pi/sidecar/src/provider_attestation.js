"use strict";

/**
 * provider_attestation.js -- reports the effective provider identity.
 *
 * In Fase 1 the sidecar is wired to a local mock provider (no network).
 * The report is what the bridge compares with the requested identity.
 * The credential_ref stays in BAGO; the sidecar never receives the
 * token. It only reports the (opaque) reference.
 */

function attest(
  requestedProvider,
  requestedModel,
  effective,
  credentialRef,
  bridgeVersion,
) {
  const result =
    effective.provider === requestedProvider && effective.model === requestedModel
      ? "MATCH"
      : "MISMATCH";
  return {
    requested_provider: requestedProvider,
    effective_provider: effective.provider,
    requested_model: requestedModel,
    effective_model: effective.model,
    endpoint_normalized: effective.endpoint,
    adapter: effective.adapter,
    bridge_version: bridgeVersion,
    pi_package_version: effective.pi_package_version,
    pi_lockfile_hash: effective.pi_lockfile_hash,
    sidecar_artifact_hash: effective.sidecar_artifact_hash,
    credential_ref: credentialRef,
    fallback_used: effective.fallback_used,
    auto_selection_used: effective.auto_selection_used,
    config_effective: effective.config_effective,
    result,
  };
}

module.exports = { attest };
