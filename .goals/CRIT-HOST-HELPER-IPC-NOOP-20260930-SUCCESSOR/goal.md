# Goal: Prove the authenticated host-helper boundary and close bootstrap P0 gates

Status: `PREPARED` — preparation only; implementation and runtime verification are not authorized by this document's creation.

## Parent goals and authority

- Successor to `.goals/CRIT-HOST-HELPER-IPC-20260930/goal.md`, which remains immutable and `BLOCKED`.
- Contributes evidence to `.goals/CRIT-BOOTSTRAP-AUTHORITY-2026/goal.md`; it does not close or replace that P0 goal.
- Preserve the sole authority chain:

  ```text
  direct native user intent -> AuthorizationBoundary -> exact Permit -> Permit consumed by ExecutionGateway -> existing effect owner -> elevated helper transport/materialization endpoint
  ```

- The helper does not issue Permits, create another authority, or become an alternate effect owner. Keep the MSIX seed-only boundary and existing canonical owners.
- Preserve every pre-existing dirty change. Do not reset, restore, or overwrite unrelated worktree content.

## Authorization boundary for this goal

The user's current authorization covers **preparing this successor goal and its acceptance matrix only**. This preparation does not authorize product-source edits, implementation, builds, signing, package installation/activation, UAC prompts, helper/process launches, material effects, or clean-machine installation.

Before a no-op Windows IPC test, obtain separate explicit user authorization for its exact test build/signing and MSIX activation scope. The test must perform no BAGO installation and no selected-target, registry, shortcut, or BAGO-state effect. A real clean-machine install/e2e test is a separate material-effect activity and requires separate explicit authorization. Any later implementation work also requires explicit authorization if not included in that later request.

## Objective

Resolve the authenticated IPC design and, only after the appropriate authorizations and evidence gates, implement and test a fail-closed host-to-helper handoff. Then integrate that evidence into the complete bootstrap P0 closure matrix without claiming closure from mocks, source inspection, test-publisher evidence, or an IPC-only pass.

The leading named-pipe design in the predecessor is a proposal, not a preselection. Compare supported Windows approaches and select one only when the threat model, peer identity and end-to-end evidence support it.

## Threat model and required analysis

Assess a same-user, medium-integrity attacker able to read/replace user-writable files, race or squat an IPC endpoint, replay or alter messages, start a different process, and attempt process injection/handle duplication against the host. Also cover PID reuse, process-instance binding, package/publisher mismatch, helper/script replacement, target drift/TOCTOU, UAC cancellation, retries, alternate administrator credentials, crashes, timeouts, and denial of process-query rights. Do not waive a threat because the proposed transport or DACL is convenient. If a supported OS identity check or security boundary cannot be established, keep the goal `BLOCKED`.

## Acceptance criteria

1. A reviewed protocol decision records endpoint roles, trust anchors, exact OS APIs and access rights, channel namespace/ACL, authenticated process-instance binding, helper/script/package/publisher verification, bounded canonical framing, target binding, one-use/replay handling, timeout/crash/cancel/retry behavior, alternate-account behavior, and explicit limitations. It compares alternatives and does not assume a named pipe is safe merely because it is local.
2. The actual request and any authorization proof are not accepted from user-writable files or command-line text. The exact canonical request crosses the privilege boundary in memory only after the matching direct-user Permit has been consumed by the existing Gateway. No helper launch or other covered material effect occurs before that consumption.
3. The request binds session, effect/action, operation fingerprint, exact target identity and pre-state digest, source/package/helper digests, authenticated package/release-manifest identity, and options. The helper rechecks the authenticated identities and target immediately before any material effect.
4. Both endpoints reject wrong or substituted peers, a pipe squatter, PID/process-instance mismatch, wrong package/publisher/helper/script, stale or replayed request, altered framing/payload, target drift, timeout, cancellation, and unsupported alternate-account elevation. A retry requires fresh direct user authorization and a fresh Permit.
5. Focused adversarial tests exercise the rejection cases and prove absence of material effects on denial. Mocks may test application logic but do not count as OS peer-authentication evidence.
6. After separate explicit authorization, a signed packaged-host Windows integration test exercises the actual elevated IPC path with a no-op helper. It captures OS-reported peer identities and produces no selected-target, BAGO installation/state, registry, or shortcut effect. UAC cancellation and any supported over-the-shoulder account behavior are tested or explicitly fail closed.
7. An independent fresh-context security review of the protocol, implementation, test evidence, and threat boundaries returns a non-blocking result. A `BLOCKED` review cannot be converted to a pass by the implementation author.
8. Full bootstrap P0 criteria in `acceptance-matrix.md` pass on one frozen candidate: unique Boundary/Gateway/owners; no pre-Permit effects; native interaction and authenticated helper; target fencing/drift/replay; post-install launch ownership; no reachable official NSIS bypass; trusted production publisher/release binding; required tests and scanner coverage; and separately authorized clean-machine Windows evidence.
9. The scanner's roots and language coverage are checked separately from classification. The current bootstrap/C# coverage limitation must be closed by supported inventory evidence before claiming a complete P0 sink inventory; do not hide findings with exclusions or code movement.
10. P0 is marked `VALIDATED` only after every acceptance criterion and independent final-verifier criterion passes against the same immutable candidate. Otherwise use `EXECUTED`, `VERIFIED` only for evidence actually demonstrated, or `BLOCKED` with the missing evidence identified. The UI historical-close investigation remains separate and unresolved until it has its own causal evidence.

## Ordered execution plan and gates

1. **P0 rehydration (read-only):** recapture HEAD, branch, porcelain/fingerprint, exact goal/status and current receipts; refresh the full P0 acceptance matrix. Stop on candidate drift or conflicting authority.
2. **Protocol decision (read-only):** resolve the predecessor review's valid findings, compare Windows transports and identity APIs, map the existing production call chain, and obtain independent design review. No code edits during this block.
3. **Implementation (separate authorization required):** implement only the selected protocol and one logical fail-closed transport block. Update status after each block; do not enable installation or add another Permit/effect owner.
4. **Adversarial test development/execution (separate authorization required):** exercise message/peer/replay/target-denial behavior with zero material effects; bind receipts to the recaptured candidate.
5. **No-op packaged Windows test (separate explicit authorization required):** build/sign/activate only the test package and exercise UAC/IPC with a no-op helper. Stop before activation if the authorized package, signer, machine, or test procedure differs from the approved scope.
6. **Full P0 integration (separate authorization required where it causes effects):** close native interaction, pre-Permit effects, NSIS routes, post-install launch ownership, production publisher/release identity, scanner coverage, and all owner boundaries. No unrelated global sink remediation.
7. **Clean-machine material install test (separate explicit authorization required):** only after the no-op and security gates pass, use a disposable clean Windows environment and an approved target. Record the exact candidate, publisher, pre/post state, effects, recovery, and uninstall evidence.
8. **Independent final verification:** fresh-context verifier checks the complete matrix, receipts, diffs, test/gate completeness, and unchanged candidate identity. Close only to the evidence-supported BAGO state.

## Immediate state

This goal was prepared under authorization for planning artifacts only. No product source was edited, and no build, signing, UAC launch, MSIX activation, install, or material effect is authorized or claimed by this preparation.