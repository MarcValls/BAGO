# Goal: Design and verify authenticated host-helper IPC

Status: `PREPARED` (design and implementation not yet verified)

## Authority and scope

Design and, if the threat model is supportable, implement and verify an authenticated one-shot IPC handoff between the signed MSIX seed host and its elevated helper. Preserve the existing authority chain:

```text
AuthorizationBoundary -> consumed Permit -> ExecutionGateway -> existing effect owner -> helper
```

The helper is not a Permit issuer or a new effect owner. Do not enable installation, run a material effect, activate/reinstall an MSIX package, alter system installation state, or repair global sinks as part of this goal. Keep the existing host fail-closed until acceptance is met. Preserve the pre-existing dirty worktree.

## Threat model to resolve

At minimum, assess a same-user, medium-integrity process that can read/replace user-writable files, race or squat on IPC endpoints, connect to a named pipe, replay a previous message, or supply a different process identity. Do not treat a random pipe name, command-line nonce, user-SID ACL, or file mode as peer authentication. Evaluate process injection into the trusted host, UAC cancellation, retry semantics, PID reuse, alternate administrator credentials, helper replacement, package/publisher mismatch, target drift, and TOCTOU. Do not silently exclude a threat that prevents the requested guarantee; record a blocker instead.

A candidate transport (for example, a one-instance local named pipe) is a proposal only. Select it only if both endpoints can validate the actual OS peer process and its trusted package/helper identity, and if the resulting handoff is bound to the exact canonical request. A failed or unavailable Windows check must fail closed.

## Acceptance criteria

1. A written protocol decision identifies trust anchors, endpoint roles, OS-authenticated peer identity checks, channel ACL/namespace, message framing/canonicalization, one-use/replay behavior, timeout/crash/retry behavior, and explicit threat-model limits.
2. No authorization ticket, shared secret, or authoritative request is trusted from user-writable disk or command-line text. The exact request is transported in memory only after the existing Gateway has consumed the matching direct-user Permit.
3. The message binds at least session, effect/action, operation fingerprint, target identity/state digest, source/package/helper digests, authenticated bootstrap/package identity and release-manifest identity, and options. The helper revalidates identity and target immediately before any material effect.
4. Neither endpoint accepts a pipe squatter, wrong PID/process creation instance, wrong package/publisher, wrong helper, stale/replayed request, altered payload, target drift, or invalid/retried handshake. UAC cancellation and unsupported alternate-account elevation fail closed and require fresh authorization.
5. Automated adversarial tests cover framing, wrong peer, PID reuse/identity mismatch, replay, timeout, cancellation, target/payload drift, and absence of material effects. A Windows integration test exercises the actual transport using a no-op helper; it must not install BAGO, change registry/shortcuts, write to the selected application target, or activate an MSIX package.
6. Independent security review inspects the design and implementation. If the current environment cannot prove a required OS behavior or run a necessary no-effect Windows test, record `BLOCKED`; do not substitute mocks for OS peer-authentication evidence.
7. P0 remains open until this IPC is integrated with the full approved bootstrap chain and the separate signing, NSIS, clean-machine, launch-owner, and release gates pass.

## Execution plan

1. Read-only: rehydrate BAGO state and map the current host, adapter, helper, native approval and Windows API contracts.
2. Compare IPC options and record a protocol decision before implementation; identify any threat-model or platform blocker.
3. Implement one logical transport block with a fail-closed no-op helper boundary and focused adversarial tests; update this goal status after each block.
4. Verify on Windows with a no-op peer, then run the focused suite and candidate-bound gates. Do not run material effects or MSIX activation.
5. Obtain an independent fresh-context security review. Mark only evidence actually achieved; preserve unresolved constraints as `BLOCKED`.
