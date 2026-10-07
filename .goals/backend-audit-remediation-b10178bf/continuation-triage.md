# Pending gate triage — backend audit continuation

## Authority and candidates

The user authorized continuing pending work (`sigue con lo pendiente`). This is
scoped backend remediation/gate work, not authorization to close bootstrap P0,
remediate global runtime sinks, alter authorization policy or promote canon.
The initial audit was read-only; the original goal's assertion of earlier P2
permission is retained as historical text, not evidence of that permission.

Original P2 18-path candidate: HEAD b10178bf, scoped SHA-256
`fc6f8ed3af6dc977aca13cce674e5bee41c64feb8b39910aa6a4d4c365cd5a1b`.
It was rechecked with binary file hashes at continuation entry and matched.
The preliminary reviewer reported contradictory state/hash/internal-flag facts;
that attempt is not accepted as certification. Actual root state remains
EXECUTED and the bootstrap handoff remains separate/open. No restore/reset was
performed to match the reviewer's claims.

## Complete diagnostic runs

Both runs use Python 3.14.5/Windows, pytest with no cache provider, verbose short
tracebacks, and faulthandler_timeout=45. The observer records every test start,
phase report/traceback and session finish to JSONL without changing selection,
fixtures, timeouts or outcomes.

- Original P2 candidate: **51 failed / 1762 passed / 3 skipped / 214 subtests
  passed**, 592.16 s. Logs: `candidate-diagnostic.{log,jsonl}`.
- Clean local shared clone pinned to the exact HEAD: **51 failed / 1689 passed /
  15 skipped / 214 subtests passed**, 606.36 s. Clone:
  `C:/Users/AMTEC_Terminal_1º/BAGO-audit-diagnostics-b10178bf-baseline`.
  Logs: `baseline-diagnostic.{log,jsonl}`. Tracked diff after testing is empty.
- Exact failed-node intersection is **47**; equal totals did not imply equal
  failures. The baseline lacks ignored UI dist and historical evidence bundles;
  some existing evidence tests return without exercising their body when a bundle
  is absent. Thus baseline PASS on that test was not used as proof of correctness.
- The prior 720 s timeout did not reproduce as a whole-suite hang. The long test
  locations are now known: a seed subprocess exceeded its own 120 s bound while
  scanning the artifact-heavy checkout, and snapshot-leakage validation took
  about 62 s but passed. This diagnoses observations, not a universal timeout
  explanation.

## Candidate-only failures, correction and focused evidence

1. REPL import: SessionAdaptersMixin imported the API catalog without resolving
   its path; a core/chat/providers-only launcher raised ModuleNotFoundError.
   Added canonical piece resolution for the existing catalog owner. Existing
   real subprocess REPL test now passes; no duplicate catalog authority added.
2. WorldStateSnapshot projection: provider configure moved the credential-write
   callsite from line 220 to 234. Regenerated the official derived inventory;
   registry/owners/scanner coverage remain unchanged. Official --check passes.
3. Governed receipt: unignored in-repository `.pytest-tmp-audit` violates the
   receipt writer's output-boundary precondition, returning 2 before writing.
   Use existing ignored `.run` basetemp, not a new ignore or policy exception.
4. CLI seed smoke: previously scanned/materialized the real backend checkout,
   making runtime depend on accumulated unrelated test artifacts and permitting
   stale seed output as an assertion. The test now uses a fresh small temporary
   workspace and asserts that workspace's new output; real launcher/command and
   authorization path are retained.

Resolver/provider gate: 38 passed. CLI/receipt/WorldStateSnapshot/import gate:
26 passed. A first new basetemp attempt had 17 setup errors because its parent
was absent; parent creation and retry are explicitly recorded.

## Additional scoped regression found during continuation

The streaming wrapper held thread-local conversation scope across yields. A
paused stream therefore redirected a second turn on the same caller thread, and
resuming on another thread left the first thread's override behind. New probes
reproduced both behaviors. The iterator now binds only while executing each
next/send/throw/close and restores scope before returning a chunk. An outer
standard generator preserves delegation and GC finalization. An already-bound
turn may finish after archive; a new turn still rejects archived selection.
Throw, cross-thread close, GC, archive, pause/interleave and thread-migration
regressions are covered. Final stream/protocol gate: 23 passed. An initial
archive-test assertion incorrectly called the existing forbidden archived-history
accessor; it was corrected to inspect the persisted records, not relax that API.

## Shared baseline failures (not silently fixed or waived)

| Modules | Failed cases | Observed behavior / next owner action |
|---|---:|---|
| bago_canary_gateway, delegation_grant, release_job_storage_gateway, release_signature_gateway, repository_guard_gateway, role_definition_gateway | 37 | Mostly missing/unspecified WorldStateSnapshot or untrusted authority: Gateway denies before intended effect. Refresh test request builders/fixtures against canonical trusted authority; do not weaken Gateway. |
| context_attach_gateway, project_demo_contract, workspace_patch_gateway | 3 | World-state stale rejection precedes the tests' expected operation-mismatch code. Reconcile assertions with canonical rejection order and prove no material effect. |
| debt_guard | 2 | Fixture approval lambda lacks new `manager` keyword. Update test seam while retaining direct CLI approval properties. |
| session_mirror_safety | 4 | Partially constructed manager fixture lacks `base_path`; snapshot construction fails before mirror behavior. Supply coherent session/resource identity and retain drift/out-of-scope tests. |
| effect_sink_inventory | 1 | Process adapter has five visible owned sinks; test expects four. Inspect canonical owner and inventory before updating a count; no exclusions or lower confidence. |

These **47 cases across 12 modules** are proved to fail on the unchanged HEAD,
not inferred from historical counters. Their fixture/policy contract corrections
are a separate security/owner integration task; this continuation does not
certify them or grant a blanket exception. Final full suite must still report
all failures and skips. Independent P3 may support a bounded remediation verdict,
not global backend success, bootstrap closure or global runtime acceptance.

## Final evidence on the corrected candidate

Source/test/doc/projection scope (20 paths) SHA-256:
`6ac96484931d2d2e0682cff160df2c2607a1192576b930488f6b8c72ab1892e1`.
Both official gates captured stable worktree fingerprint
`8b720d5122b8cc00d327e9a0a40fa7cfe75814a7c01fee87ed681b70ed9fba26`.

- Independent P3 focal: **234 passed / 158 subtests passed**, exit 0.
  `.bago/evidence/remediation-gates/backend-audit-p3-focused-20261002.json`.
- Final full: **47 failed / 1773 passed / 3 skipped / 214 subtests passed**,
  exit 1, 561.32 s; completed without whole-run timeout.
  `.bago/evidence/remediation-gates/backend-audit-final-full-20261002.json`.
- Exact final failed-node set is wholly contained in the isolated HEAD baseline;
  all four original candidate-only failures now pass. Raw output hashes and
  before/after candidate identities were read and checked.

Independent **scoped P3 PASS**, with **full/backend closure BLOCKED**. See
`p3-scoped-review.md`. Reporting/status edits after the gates do not promote the
whole worktree; source evidence applicability was checked against the unchanged
20-path hash. Goal remains EXECUTED. Remaining 47-case repair requires its own
explicit scope/owner integration; no policy relaxation or exclusions performed.
