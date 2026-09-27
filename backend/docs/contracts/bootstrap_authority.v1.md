# BAGO clean-machine bootstrap authority v1 (proposal)

Status: `PROPOSED` / `NOT_CANON` / `NOT_IMPLEMENTED`.

This document defines the minimum contract needed to close the installer P0
without creating a second `AuthorizationBoundary` or treating NSIS as an
implicit Permit. It is a design input for implementation and verification;
it does not authorize production changes by itself.

## Problem boundary

The normal maintenance route is already:

```text
AuthorizationBoundary
  -> consumed direct-user Permit
  -> ExecutionGateway
  -> system.install.apply / SystemInstallEffectAdapter
  -> one-use helper ticket
  -> materializer
```

A clean machine has no BAGO session or ledger before an installer starts. The
bootstrap must therefore establish a trusted authority host before the first
BAGO-controlled material effect. Passing a checksum, clicking an installer,
or launching a child PowerShell process is not a Permit.

## Non-negotiable invariants

1. There is one canonical `AuthorizationBoundary` and one `ExecutionGateway`.
2. The bootstrap host may be externally trusted by the operating system or a
   release signature, but it must not mint a parallel BAGO Permit format.
3. Every material operation is represented by the canonical
   `system.install.apply` request, including package extraction, target
   replacement, registry/shortcut registration, rollback, finalize and
   uninstall where applicable.
4. The operation identity binds at least:
   `session_id`, `effect_id`, action, source/package digest, helper digest,
   destination identity, destination-state fingerprint, requested options,
   rollback identity and policy version.
5. The first material effect occurs only after the operation has been accepted
   by the canonical boundary or by an explicitly documented external trust
   handoff that is itself bound to the same operation identity.
6. A child helper can consume one ticket only once. A ticket for extraction
   cannot authorize registry writes, shortcuts, uninstall or another target.
7. Reparse substitution, destination drift, helper/package replacement,
   replay and concurrent target use fail closed before materialization.
8. Installer and helper sinks remain visible to the inventory. No exclusion,
   lowered confidence or scanner-only reclassification is permitted.

## Required request shape

The bootstrap preparation must produce a canonical request equivalent to:

```json
{
  "effect_id": "system.install.apply",
  "scope": "system",
  "action": "bootstrap-install",
  "source_package_sha256": "<sha256>",
  "helper_sha256": "<sha256>",
  "target_root": "<canonical target>",
  "target_state_fingerprint": "<absent-or-tree-fingerprint>",
  "rollback_identity": "<new-or-existing rollback identity>",
  "options": {},
  "policy_version": "<current registry policy>"
}
```

The exact field names must be reconciled with `install_plan.py` before
implementation. This example is deliberately not a second contract object.

## Trust handoff options

Only one option may be selected and implemented after review:

### A. Externally trusted bootstrap host

The signed installer invokes a small host whose only responsibility is to load
the canonical BAGO authority implementation and create the bootstrap session.
The host must prove its own artifact identity, expose the canonical request,
and hand the consumed operation to the existing owner. Its loading and
temporary staging effects need an explicit trust classification and tests.

### B. Pre-provisioned authority runtime

The installer is allowed to operate only when a trusted BAGO authority runtime
already exists. This reuses the existing maintenance owner but does not satisfy
first-install clean-machine support; it would be a deliberate product-scope
restriction and would leave the standalone installer out of closure.

### C. Native installer adapter

The installer host itself implements the canonical adapter boundary. This is
acceptable only if it is the same owner and protocol as the Python gateway,
with no second Permit issuer or divergent identity rules. A merely signed NSIS
script is not sufficient.

No option is selected by this proposal. Option A is the only candidate that
could preserve clean-machine installation while keeping the boundary unique,
but it requires a separate trust/startup spike and an independent review.

## Verification matrix before implementation closure

- first-effect trace on a clean machine;
- forged, absent, expired and replayed ticket;
- changed package/helper/target after approval;
- target reparse substitution and destination drift;
- two concurrent installs targeting one root;
- crash before ticket claim, after claim and before finalize;
- rollback and uninstall with unrelated or prior successful permits;
- no second Permit issuer and no duplicate registered owner;
- complete inventory retains every installer sink;
- `--strict-classification` and `--strict-runtime` on the same committed
  candidate;
- full backend suite and independent final verification.

Until this matrix is implemented and passes, the P0 remains open and
`UNIQUE_EXECUTION_BOUNDARY` must remain `NOT_YET`.
