# Goal: Close clean-machine bootstrap authority P0

Status: EXECUTED (P0 closure still open; partial implementation recorded 2026-09-29)

## Authority and scope

User instruction: "soluciona p0 de bootstrap" authorizes work to close the installer/bootstrap P0. Preserve all pre-existing dirty worktree content. Do not reset, restore, or overwrite unrelated changes.

Implementation direction, bounded to the existing proposed contract: use a signed MSIX as an OS-provisioned seed/bootstrap host only. Treat only provisioning/updating/removing that seed package as the external OS handoff; it must not modify BAGO's selected application target, BAGO state, or user registry/shortcuts. All effects on the selected BAGO target remain owned by the existing AuthorizationBoundary -> ExecutionGateway -> canonical install/apply, rollback, uninstall, and process owners. No NSIS path may remain reachable as an official route.

## Acceptance criteria

1. A clean-machine bootstrap authenticates the signed seed package, publisher, manifest, release candidate, source tree, helper, and exact target before asking for approval.
2. No selected-target, BAGO-state, registry, shortcut, helper-process, or mutable-mirror effect occurs before the matching canonical Permit is consumed; seed-package OS provisioning is explicitly separated from those effects.
3. Exactly one canonical AuthorizationBoundary and ExecutionGateway are used. Apply, rollback, and uninstall retain distinct effect owners and operation identities.
4. Native interaction proof, elevated helper handoff, target exclusivity/fencing, package/target drift checks, replay rejection, and post-install launch are closed fail-closed.
5. Every official NSIS build, publish, E2E, install, update, rollback, and uninstall route is replaced or disabled; scanner visibility for NSIS remains intact.
6. The MSIX build/sign/publish workflow verifies package integrity and publisher identity and binds artifacts to an immutable release tag/candidate.
7. Required negative, concurrency, replay, crash-recovery, owner-boundary, and clean-machine tests pass; strict classification/runtime inventory and the full relevant backend suite pass on the same candidate.
8. Clean-machine Windows evidence verifies trusted signed package acceptance and rejection of unsigned, altered, untrusted, or publisher-mismatched packages. Independent final verification is completed before claiming closure.

## Plan

1. Freeze and record candidate identity and preserve the dirty boundary.
2. Trace existing install/apply/rollback/uninstall/process owners, bootstrap flows, NSIS routes, release workflows, and test surfaces; map each required contract gap to an existing owner (REUSE -> EXTEND -> NEW).
3. Implement the seed-only MSIX handoff and owner-bound extensions in serialized integration order; do not start unrelated sink repairs.
4. Replace every official NSIS route while preserving scanner detection.
5. Run focused tests, release/package checks, strict inventory gates, and full relevant suites against the same candidate.
6. Obtain clean-machine Windows signing/package evidence and an independent verifier pass. If environment/certificate/hardware prerequisites are unavailable, record BLOCKED rather than claim P0 closure.

## Current blockers/assumptions

- Seed-only MSIX is selected as the only direction in the current contract identified as preserving clean-machine install and a unique BAGO execution boundary. This goal interprets the user's P0 instruction as authorization to proceed under the seed-only external OS handoff condition; this does not authorize target effects outside the canonical owners.
- The current candidate is dirty and contains unrelated pre-existing changes. All evidence must be rebound to a fresh candidate fingerprint after edits.
- Signing credentials, publisher identity, MSIX toolchain compatibility, and clean-machine Windows verification are not yet established.

## Progress 2026-09-29

- Completed a scoped read-only habituation trace for bootstrap approval, install
  history/update retry, helper tickets, session mirror setup, rollback and
  uninstall state, installed-app backend launch, and the reachable NSIS
  workflows. See
  `.bago/runtime/CRIT-BAGO-HABITUATION-01-RUNTIME-TRACE_20260929.md`.
- Added one canonical target lease across `system.install.apply`,
  `system.install.rollback`, `system.install.uninstall`, and
  `system.install.archive.rollback` using the existing `ExecutionClaimStore`.
  Active SQLite claims now reject same-target contenders before waiting on the
  material-effect transaction. Apply and uninstall resolve to the same
  normalized install-target key.
- Replaced PATH/SystemRoot-based PowerShell selection for install/apply,
  uninstall elevation, and governed process termination with the inbox
  interpreter under the OS-reported system directory.
- Recorded the selected MSIX seed-only lifecycle boundary in
  `.bago/decisions/DECISIONS.md`; it is an implementation decision, not package
  or release evidence.
- Focused tests: 64 passed, 1 skipped before the rollback fingerprint change;
  latest install/claim/uninstall/windows helper tests: 35 passed, 1 skipped;
  process owner tests: 9 passed; scanner suite: 47 passed.
  `--strict-classification`: PASS (3115 findings, zero unclassified);
  `--strict-runtime`: OPEN (296 runtime-unbound findings, exit 1).
- The P0 remains open. No MSIX host/package, authenticated elevated IPC,
  post-install owner-bound Electron launch, official NSIS route replacement,
  full backend gate, clean-machine evidence, or independent review has been
  completed. The current checkout remains dirty and all receipts must be
  rebound to its final fingerprint.
