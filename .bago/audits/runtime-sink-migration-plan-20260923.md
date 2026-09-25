# Runtime effect-sink migration plan — 2026-09-23

## Baseline

- Candidate: `313ff3940484233e5cbad82e4585e5d346cf8b0b`
- Worktree at planning time: clean.
- Inventory: `2201` findings, `0` unclassified scope, `0` unclassified binding.
- Runtime uniqueness gate: `587` `runtime_unbound` findings; `268` high-confidence findings.
- The inventory remains exhaustive: classification is not an exclusion and
  `--strict-runtime` remains the closure gate.

## Objective

Move every runtime effect sink behind the canonical `ExecutionGateway` with:

1. one canonical `effect_id` and registry owner;
2. authority resolved before the material effect;
3. a server-owned adapter with no caller-supplied callable;
4. a negative test proving the effect is blocked before it materializes;
5. candidate-bound inventory and focused/full regression evidence.

No phase may promote the global product to `VERIFIED` or `VALIDATED` while a
runtime sink remains unbound or while the independent final review is absent.

## Ordered migration waves

### Wave A — internal persistent state (this execution)

Effects: `state.write`, `config.write`, `memory.write`,
`agent.definition.write`.

Centralize atomic text, JSON and durable append operations in the
server-owned `ServerStateEffectAdapter`. Migrate the shared atomic primitive
first, then the configuration, schedule and API persistence callers. The
adapter must reject traversal, a root mismatch and non-policy effects before
writing.

Closure for the wave: adapter registration, policy-authority tests, traversal
and root-mismatch BLOCK tests, focused gateway/atomic/config/schedule tests,
inventory reduction bound to the resulting candidate.

### Wave B — user/project/credential material effects

Effects: `project.write`, `workspace.bind`, `filesystem.write`,
`filesystem.delete`, `credential.write`, `state.delete`.

Migrate project/demo and workspace binding routes, provider configuration and
secret deletion, router override deletion, and any remaining user-facing
material writes to explicit challenge → approve → one-time Permit → adapter
execution. No compatibility fallback may write directly.

### Wave C — network and process execution

Effects: `network.read`, `network.external_write`, `process.execute`, and
provider/agent/tool runners. Add fixed adapters for HTTP reads and process
execution, then migrate providers, AgentGateway, ScriptRegistry, ProcessRunner
and command bridges. Policy reads remain server-owned policy effects; external
mutations and processes remain explicit/delegated effects.

### Wave D — release, installer and Electron surfaces

Effects in installers, update/release managers, Electron main/preload/services
and build/admin tooling. Keep release/admin and derived snapshots visible in
the inventory, but close every runtime authority sink that can execute from a
running BAGO process. Add bridge-level negative tests and packaged-runtime
evidence.

## Execution record

Latest block: `toolsmith.save_toolbox()` removed its parallel direct directory
creation and now requires success from the existing server-owned `state.write`
writer before returning the toolbox path. Regression proof: directory absent
when delegation starts, present after writer completion. Twelve orchestration
tests passed; compile, strict classification and diff-check PASS. Inventory:
2316 / 68 runtime-unbound / 0 unclassified; strict-runtime OPEN. The second
sink, `toolsmith.create_tool()`, remains an explicit module-generation effect.
Duration reconstructed at ~1m net, excluding tests and gates.

Next block: Node Control state bootstrap no longer performs its own registry
root `mkdir`; the existing `state.write` for the first registry file creates
the parent. Its modular guard imports the read-only `backend/tools/
check_modular.py` implementation and calls `run_all()` in-process, removing the
direct unbound Python subprocess. The first test run exposed that the old path
incorrectly searched outside `backend/` and always returned R6; the root was
corrected. Final Node Control split + translator tests: 31 passed in 13.20s;
compile, strict classification and diff-check PASS. Inventory: 2314 / 66
runtime-unbound / 0 unclassified; strict-runtime remains OPEN. Duration ~2m45s
net estimated, excluding tests and gates.

DirectoryContext block: `HybridRetriever` no longer runs `git diff
--name-only` directly. SessionManager propagates its active manager through
both context construction paths; the retriever delegates the exact Git
read-only query to `process.inspect`, with a workspace cwd and absolute
`safe.directory`. Standalone retrievers without manager context omit this
working-set boost and never spawn Git. The server Git allowlist gained only the
exact `diff --name-only` argv. DirectoryContext + Gateway tests: 65 passed in
5.11s; compile, strict classification and diff-check PASS. Inventory: 2313 /
65 runtime-unbound / 0 unclassified; strict-runtime remains OPEN. Duration
reconstructed at ~1m net, excluding tests and gates.
Wave A was executed as `A1-persistent-authority` and extended with the
server-owned transport seam needed by the already-running providers and
runtime probes:

- `ServerStateEffectAdapter` owns `state.write`, `config.write`,
  `memory.write` and `agent.definition.write`; policy authorization, trusted
  root equality, traversal/symlink/forbidden-segment blocking and durable
  materialization happen inside the gateway path.
- `NetworkReadEffectAdapter` owns the classified Python transport calls for
  `provider_transport`, `runtime_probe` and `local_discovery`. It preserves
  `urllib` transport errors so unavailable local services still use their
  existing fallback behavior.
- Atomic JSON/text, schedule/config/context/agent/provider persistence and the
  migrated Python provider/bridge/tool transports now call server-owned
  helpers; no caller-supplied callable is accepted by these adapters.
- Negative coverage proves server-policy effects block root mismatch,
  traversal and public-gateway dispatch before materialization. The authority
  ledger remains explicitly `authority_internal`, not a disguised runtime
  adapter.

Candidate-bound execution evidence for this bounded tranche:

- Inventory moved from `2201` findings / `587` runtime-unbound to `2092`
  findings / `474` runtime-unbound (`244` high-confidence). Runtime residuals
  are explicit: `305` filesystem writes, `78` deletes, `79` process effects
  and `12` release/update network reads.
- `--strict-classification` passes with zero unclassified scope/binding.
  `--strict-runtime` remains intentionally failing while the residual waves
  are open; no classification was used as an exclusion.
- Focused gateway/persistence/transport suite: `99 passed`; full backend
  suite: `1251 passed, 2 skipped, 198 subtests passed` after regenerating the
  import-migration inventory (`69` files, `110` mutations).
- The resulting worktree must be committed as one candidate before any
  protected lifecycle claim. Wave B (project/workspace/credential/delete),
  Wave C (process and remaining external effects) and Wave D
  (release/installer/Electron) remain `PROPOSED/OPEN`.

The plan artifact is intentionally tracked; runtime state and receipts remain
candidate-bound in `.bago/` and are not inferred from this document. This
tranche is `EXECUTED`, not globally `VERIFIED` or `VALIDATED`; independent
final review is still required.

## Wave B1 execution record — session-model state deletion

Wave B was started with the smallest isolated destructive runtime sink:
`state.delete` for the session model override. The route now constructs one
canonical `ExecutionRequest`, exposes the existing challenge/approval
lifecycle, restores the automatic provider/model, and only then consumes the
one-time Permit through `ExecutionGateway`. `StateDeleteEffectAdapter` owns
the final unlink and rejects a missing/changed trusted root, another session,
symlinks, traversal, non-canonical resources and every target other than
`.bago_session_model.json` under the live session `state_root`.

The React client now performs challenge → approve → execute for clearing the
override, after a visible confirmation. The receipt and authorization
metadata are returned to the UI; no compatibility direct-delete fallback
remains. Negative coverage proves that challenge, missing/invalid Permit and
automatic-switch failure leave the persisted override intact.

Candidate-bound execution evidence before final commit:

- Backend focused gateway/router/authorization suite: `30 passed`.
- Frontend focused client/ControlPlane/navigation suite: `34 passed`.
- Frontend typecheck: PASS; production build: PASS (`123 modules`).
- Current effect inventory: `2099` findings, `473` runtime-unbound and `243`
  high-confidence runtime-unbound; `0` unclassified scope/binding.
- `--strict-classification`: PASS. `--strict-runtime`: FAIL/OPEN, exit `1`.

This is `EXECUTED / SCOPED` only. The remaining project/workspace/credential
effects in Wave B, all later waves, the full final candidate gate and
independent review remain open. No global `VERIFIED` or `VALIDATED` claim is
made from this bounded start.

## Wave B2 execution record — workspace.bind / workspace.persist

This cut closes the HTTP `POST /workspace/persist` surface for the canonical
`workspace.bind` effect. The handler now only performs pure preflight,
constructs the server-owned `ExecutionRequest`, and exposes the existing
challenge → approve → one-time Permit → execute lifecycle. It no longer calls
`rebind_project_root()`, `save()` or writes `last_workspace.json` directly.

`WorkspaceBindEffectAdapter` is registered in the default
`ExecutionGateway` registry and owns the compound effect. Immediately before
materialization it checks the live manager/session, absolute project identity,
workspace resource/operation, binding digest, workspace id and scope. A
per-session lock prevents concurrent binds from interleaving. A changed or
invalid root fails before rebind; the current root is idempotent and avoids a
second mirror rebuild. The adapter emits a receipt that distinguishes rebind,
session JSON persistence, SQLite indexing and `last_workspace` persistence;
the nested last-workspace write remains server-policy-owned.

The React client now performs challenge → approve → execute for this route,
and the visible Workspace “Persistir” action goes through the client instead
of the dead `/workspace persist` command. The previous snapshot effect that
silently issued a bind has been removed. `/project` callers and the TTY wizard
still reach `rebind_project_root()` directly; they are explicitly outside B2
and remain the next `project.write` tranche rather than being counted as
closed by this route migration.

Candidate-bound evidence for the implementation tranche:

- BAGO-wrapped B2 gateway/workspace/authorization/persistence/project/safety
  gate: `47 passed` before the final persistence-receipt refinement; the
  refined focal gateway/workspace/authorization/atomic gate: `31 passed`.
- On candidate `fa7b1727216562fc51591b92e8d777b3ddd51a3f`, the full backend
  suite passes `1260 passed, 2 skipped, 198 subtests passed` in `225.85s`.
- Frontend client/ControlPlane/navigation gate: `35 passed`; typecheck PASS;
  production build PASS (`123 modules`); Python compile and `git diff --check`
  PASS.
- Inventory after the B2 code path: `2104` total findings, `473`
  `runtime_unbound`, `243` runtime high-confidence, `0` unclassified
  scope/binding; `--strict-classification` passes and `--strict-runtime`
  remains intentionally FAIL/OPEN. The total increases because the inventory
  retains the adapter's material sink findings; no finding is hidden.

This tranche is `EXECUTED / SCOPED` on the candidate above. Independent
verification remains pending; no global `VERIFIED` or `VALIDATED` claim is
made.

## Session workspace mirror materialization tranche — 2026-09-25

The automatic session mirror now has a canonical policy-only effect,
`workspace.mirror.prepare`, registered in the effect registry and owned by
`SessionWorkspaceMirrorEffectAdapter`. `SessionManager` constructs the
server-originated request; only the adapter performs recursive removal,
workspace copy and context-root creation. Immediately before materialization it
checks the live session id, manager project root, canonical
`<temp>/BAGO/sessions/<session>` destination, symlink boundaries, workspace
size/file policy and available disk space. Size/space failure retains the
existing fallback to the project root. Invalid identity/source/destination
blocks before materialization.

Evidence on the dirty worktree: focused mirror/gateway/workspace/canonical
contract suite `60 passed`; the first related session/workspace regression
before adding the symlink-path recheck passed `259 passed, 1 skipped, 8
subtests` in `90.29s`. Adding that recheck exposed two Windows long-path alias
failures (`258 passed, 2 failed, 1 skipped, 8 subtests` in `86.42s`). The
adapter now checks lexical path
components without resolving away the user path alias; targeted tests pass
`11 passed`, and the complete related session/workspace regression passes
`260 passed, 1 skipped, 8 subtests` in `89.87s`. `py_compile` and
`git diff --check` pass. Inventory is
`2108` findings / `433` runtime-unbound with zero unclassified scope/binding;
strict classification passes and strict runtime remains open. This tranche
does not cover `SessionManager.state_dir.mkdir`, `attach_context`,
`sync_workspace_mirror`, or any Electron installation caller. Full backend
suite and independent final review must be rerun against the final candidate.

## Workspace mirror sync authorization tranche — 2026-09-25

`/project/sync` now constructs the canonical explicit effect
`workspace.mirror.sync` and supports challenge → approve → one-time Permit →
gateway execute. `WorkspaceMirrorSyncEffectAdapter` rechecks the live session,
source mirror, target project, workspace identity and operation digest before
copying and after acquiring a per-session lock. It reuses the canonical
SessionManager mirror exclusion policy and skips symlinks. The HTTP command
path no longer calls the direct copier; both the generic `/project sync`
command and direct `SessionManager.sync_workspace_mirror()` fail closed. React
shows a confirmation before its workspace-activation sync.

Evidence: backend focal suite `68 passed` in `37.64s`, plus `3 passed` across adapter/HTTP sync cases after receipt-metadata restoration; frontend API client
`22 passed` in `0.447s`; frontend typecheck, Python compile and diff check
PASS. Inventory: `2114` total, `430` runtime-unbound, zero unclassified;
`--strict-classification` PASS, `--strict-runtime` FAIL/OPEN with exit `2`.
The source-edit timestamp window was about `14m29s` (03:22:58–03:37:27
Madrid); tests partly overlapped final refinements, so this is not pure active
editing time. This tranche is `EXECUTED / SCOPED`; no global `VERIFIED` or
`VALIDATED` claim. The complete backend suite, committed candidate and
independent final review remain pending.

## Context attachment authorization tranche — 2026-09-25

workspace.context.attach is a registered explicit effect owned by
ContextAttachEffectAdapter. The request binds session identity, source root,
context destination, selected roots and a digest of selected file contents.
The adapter requires the exact consumed Permit, revalidates before and after
copy, follows the SessionManager exclusion policy, skips symlinks, stages a
complete bundle and publishes it atomically. /context/attach owns the
challenge/approve/execute API flow. The React command surface confirms the
operation and sends paths as data; generic command and direct manager paths
fail closed.

Evidence on the dirty worktree: adapter/API pre-effect cases 5 passed;
API route metadata 22 passed, 143 subtests; frontend API/context regressions
30 passed; typecheck, compile, registry JSON and diff checks PASS. Inventory:
2120 total, 425 runtime-unbound, zero unclassified; strict classification
PASS and strict runtime FAIL/OPEN (exit 2). The first debug cycle found and
fixed an identity-tuple comparison mismatch and an HTTP status mapping error.
Source changes span 7m08s (03:43:08–03:50:16 Madrid), including that debug
loop; this is not pure active-edit time. Full backend suite, committed
candidate and independent final review remain pending.

## Detached release-update helper authorization tranche — 2026-09-25

The `system.update.apply` adapter still owns the single update operation. After
consuming its strong direct-user Permit, it revalidates the prepared descriptor
and creates a one-use helper ticket. Permit consumption now persists the exact
executed request descriptor in the canonical AuthorizationBoundary ledger.
The detached PowerShell helper validates that consumed Permit, its decision
and direct-interaction proof, the exact update target, canonical ledger path,
and the helper's own SHA-256; it atomically claims the ticket before staging,
replacing files, stopping/starting processes, writing state, or deleting the
bundle. The authorization check sits outside the effect cleanup block, so a
missing/forged ticket or changed target cannot write an error state or delete
the payload.

Evidence: update-helper authorization tests `6 passed`, including a real
challenge/approve/consume flow that produces the helper ticket, a successful
component swap, direct invocation with a forged ticket blocked before effects,
and changed-target rejection before effects. The release helper's material
sinks remain visible in the inventory and are classified as the implementation
of the registered adapter based on that tested dispatch path. Current inventory
is `2131` total / `408` runtime-unbound, with zero unclassified; strict
classification PASS, strict runtime FAIL/OPEN. Full backend suite, committed
candidate and independent final review remain open.

## Debt guard fixture separation — 2026-09-25

Removed the embedded `_run_tests()` fixture writer from
`backend/.bago/tools/debt_guard.py`; the `--test` compatibility flag now
directs maintainers to the dedicated pytest module without mutating files.
`backend/tests/test_debt_guard.py` owns the config round-trip, rule checks,
exclusion and read-only status coverage. Five former fixture sinks remain in
the total inventory under test scope and no longer count as runtime authority.

Evidence: dedicated tests `3 passed` in `0.24s`; `py_compile` and
`git diff --check` PASS. Strict classification PASS; strict runtime remains
FAIL/OPEN at `403` (inventory `2131` total, zero unclassified). The remaining
seven `debt_guard.py` sinks perform real config writes, Git inspection and
hook install/removal and still require gateway ownership. Full backend suite,
committed candidate and independent final review remain open.

## PowerShell persistent-setting inventory coverage — 2026-09-25

The PowerShell scanner previously omitted `New-ItemProperty`, `Set-Item`,
`[Environment]::SetEnvironmentVariable`, and .NET `File.WriteAllText` family
calls. It now reports registry/environment operations as
`system.configuration.write` and .NET file materialization as
`filesystem.write`. The installer-specific inventory exposes 47 sinks instead
of 41, including five runtime configuration changes that remain unbound.

Evidence: inventory/registry tests `24 passed`; global inventory `2198` total,
`395` runtime-unbound, zero unclassified. Strict classification PASS;
strict-runtime FAIL/OPEN. This improves scanner visibility only; it is not
gateway ownership and does not close Wave D.

## Installer authority-ingress map — 2026-09-25

Current-source inspection found that `install-v4.ps1` is a shared materializer,
not a single Electron-only entrypoint. Its production callers include:

- Electron bootstrap, repair, reinstall, new-copy and source-update via
  `install-service.cjs` → `dependency-service.cjs::runInstallScript`.
- Electron release-job install/rollback flow in
  `release-job-manager.cjs`, which launches the staged or installed
  `install-v4.ps1` directly.
- CLI `bago install` in `bago_core/commands/cmd_lifecycle.py`, which calls
  PowerShell directly.
- Standalone `install-assistant.ps1` and `install-remote.ps1`, both of which
  launch the helper outside the running Electron bridge. These wrappers also
  have their own network, extraction, cleanup and process sinks.

The existing `system.update.apply` owner covers update application only; it
does not authorize fresh install, repair, reinstall, new-copy, provider setup,
shell integration or the release-job installer. A future implementation must
use one canonical install effect and the existing `AuthorizationBoundary`,
with an operation-bound strong Permit and a one-use ticket checked by the
elevated helper before its first material sink. Every production ingress must
route through that owner or fail closed. Tests and packagers remain non-runtime
scopes, not bypasses accepted by the runtime installer.

State: ingress map `VERIFIED_CURRENT_SOURCE`; install effect, adapter, ticket,
caller migration and negative pre-effect tests are `PROPOSED/OPEN`. Preserve
PowerShell 5.1 behavior, same-source repair semantics and the current guided
configuration flow when implementing. No installer sink was migrated in this
audit.

### Authorization sequencing correction — 2026-09-25

Current-source inspection found that `install-v4.ps1` self-elevates with
`Start-Process -Verb RunAs` before its main install flow. That launch is itself
a material `process.execute` sink, so ticket validation only in the elevated
child would be too late. Direct script entry must fail closed before
self-elevation unless it carries a valid gateway-issued install ticket; the
elevated child must independently validate the same consumed ledger record,
exact helper hash and operation-bound target before any install sink. The
adapter remains the sole launcher for authorized production paths.

The installer also obtains guided configuration and provider choices
interactively. Those choices must be collected and bound into the request
before challenge/approval, or moved to a non-material preparation phase; a
Permit over only `SourceRoot` and `InstallDir` would not authorize later chosen
effects. For `install-remote.ps1`, download and extraction stay separately
owned and must finish before install authorization, with the verified staged
bundle identity bound to that request.

Evidence: current source in `backend/install-v4.ps1` (self-elevation and guided
prompts) and `backend/install-remote.ps1` (download/checksum/signature/
extraction before helper invocation); inventory reports 47 unbound installer
sinks and 395 runtime-unbound overall. This corrects the implementation order
only; no installer sink was migrated and no installer tests ran in this block.
Source/documentation change window: 2m04s (05:44:49–05:46:53 Madrid).

## Install operation identity foundation — 2026-09-25

Added `backend/.bago/core/install_plan.py` as a pure, shared descriptor
builder for an installation operation. It binds action, source-tree SHA-256,
helper SHA-256, absolute destination, selected mode, normalized boolean
options, package digest, and a digest of the separately held provider/config
choices. It rejects unknown options, unselected modes, linked/reparse path
components, and helper paths outside the source tree. The descriptor excludes
raw configuration and secret values.

Evidence: `backend/tests/test_install_plan.py` — 8 passed in 0.32s;
`py_compile` PASS; scoped inventory scan of the new module found zero sinks;
`git diff --check` PASS. Source-change window: 1m52s
(05:53:21–05:55:13 Madrid; tests reported separately).

Boundary: this is operation-identity groundwork only. No runtime caller,
AuthorizationBoundary challenge, ExecutionGateway adapter, ticket validator,
or pre-effect helper denial is wired yet; `runtime_paths_routed=0`. The global
inventory was not rerun after this source addition, so its last recorded
2198/395 totals are historical for this tranche. Installer migration and both
strict gates remain open.

## Electron runtime process-lifecycle boundary — 2026-09-25

Current-worktree inventory is 2239 total sinks, 243 runtime-unbound and zero
unclassified. `backend/electron/runtime-service.cjs` has seven runtime sinks
after project linking moved to the existing `project.write` owner. The
remaining calls are not one reusable operation: they start the persistent
web-chat server, stop its process tree, invoke CLI/session commands, manage the
supervisor and clean up matching processes. The registered `process.execute`
adapter requires an exact consumed Permit plus the active `SessionManager`
session and runs a bounded child process in that manager's workspace. It does
not own daemon lifecycle or process-tree cleanup, so routing these calls through
it as-is would bypass its scope and semantics.

Next migration must define a server-owned process-lifecycle effect with an
operation-bound target, session/runtime identity, explicit desktop confirmation
for termination, and a pre-effect check in the owner. The existing `/project/link`
client pattern is not sufficient evidence of authorization for those different
operations. No process-lifecycle sink was changed in this triage; no strict
gate result is claimed. Triage window: 7m17s (09:44:15–09:51:32 UTC).

## Electron synchronous BAGO process calls — 2026-09-25

`runBagoNode` and `runBagoSession` now use the desktop-confirmed `process.execute` Gateway flow. The operation binds exact argv, active `SessionManager` session/cwd, trusted Python root and the selected module's SHA-256; the adapter rechecks the module digest before spawn. The API fixes `session_control --base-path` to the active manager path. Read-only launcher dashboard commands use `process.inspect`, an exact allowlist with a 30-second cap and server-policy dispatch.

Evidence: 93 passed plus 157 subtests in 8.30s; Electron client and clipboard IPC checks, Node syntax, Python compile, strict classification and `git diff --check` passed. Current inventory: 2247 / 241 runtime-unbound / 0 unclassified. `runtime-service.cjs` still has five lifecycle sinks; strict runtime, full backend suite and independent review remain open. Source block duration: 15m53s (09:58:06–10:14:36 UTC), tests timed separately.

`runSupervisorCmd` now uses the same Electron process client and `process.execute` adapter instead of `execFile`. The API accepts only `scripts/bago_supervisor.py` under the trusted runtime, and the request fingerprint binds the source SHA-256, active session/cwd and exact argv. The adapter rechecks the source after Permit consumption and before spawn; source drift after desktop approval is denied before `subprocess.run`.

Evidence: 56 passed in 3.81s; Electron client, Node syntax, Python compile, strict classification and `git diff --check` passed. Inventory: 2249 / 240 runtime-unbound / 0 unclassified. Four Electron process lifecycle sinks remain; global strict runtime, full backend suite and independent review remain open. Block duration 4m26s (10:19:19–10:23:57 UTC), excluding tests.

`cleanupZombies` now routes through strong, non-delegable `process.terminate`. The native desktop confirmation displays the exact active framework and state roots; the API derives them from `SessionManager`, and the caller cannot provide paths, PIDs or script text. The process adapter validates the roots before invoking fixed trusted PowerShell and excludes its own backend PID. Evidence: 62 focused tests passed in 4.35s; Electron client, Node syntax, compile, strict classification and `git diff --check` passed. Inventory: 2249 / 239 runtime-unbound / 0 unclassified. Three lifecycle sinks remain. Registry version is 1.16.0. Block duration 11m04s (10:26:32–10:37:47 UTC), excluding 10.49s of tests.

Removed the broad automatic `cleanupManagedRuntime` sweep from application shutdown; it previously selected Python/Node processes by partial command-line patterns and called `taskkill`. Also removed the automatic `cleanupZombies` shutdown/fallback calls. The manual cleanup button still uses the strong Gateway effect. Shutdown retains only the tracked webchat child stop. Inventory: 2248 / 238 runtime-unbound / 0 unclassified. Evidence: 17 tests in 4.50s, clipboard IPC, syntax, strict classification and diff check pass. Block duration 3m43s (10:39:09–10:42:57 UTC), tests excluded. Two direct runtime process sinks remain.

`stopWebChatProcess` no longer starts `taskkill.exe` from Electron. It now requests strong `process.terminate` for the live HTTP server process; the API binds its own PID, port and trusted root, and the adapter schedules a fixed terminator that revalidates `bago_core.launcher serve` identity after the HTTP result can be sent. The Electron owner waits for the tracked child exit before completing app quit. The scanner now detects JS `.kill()` process termination while excluding `process.kill(pid, 0)` liveness probes. It reveals the still-unbound startup-failure `child.kill()` call. Evidence: 63 focused tests passed in 4.99s and 22 inventory tests in 22.51s; client, syntax, compile, strict classification and diff check pass. Inventory is 2253 total / 238 runtime-unbound / 0 unclassified. Two bootstrap lifecycle sinks remain. Block duration 9m54s (10:44:28–10:55:14 UTC), tests excluded.

`StructuredLogger` now dispatches append and log rotation through the unique
server-policy `logging.append` effect. `StructuredLoggingEffectAdapter` checks
that the target is exactly `<canonical user log root>/bridge.jsonl`, validates
one bounded JSONL object and rotation parameters, and owns append/rotation.
The logger no longer creates its root or performs direct write/rename/delete;
noncanonical custom log roots fail closed. Evidence: 30 focused tests passed
in 20.79s; the first run caught a stale registry version assertion, which was
updated and passed on rerun. Python compile, strict classification (2252 / 0
unclassified), and `git diff --check` pass. Strict runtime remains OPEN at 233
runtime-unbound. Block duration 6m36s (11:02:10–11:09:29 UTC), excluding
42.52s of pytest.

Code Forge staging now routes its six mkdir/copy/rmtree findings through the
registered server-policy `workspace.validation.stage` adapter. The facade is
write-free; one owner creates a random staging identity under the canonical
temporary root, skips ignored paths and links, and only permits cleanup of an
identity created by that runtime. Noncanonical custom parents fail before the
effect. Evidence: final focused run 42 passed in 21.69s; an earlier run had six
failures (missing namespace creation and Windows short-path identity), fixed
before the passing runs. Compile, strict classification (2260 / 0
unclassified), scoped inventory (0 facade sinks, all 12 owner sinks
gateway-owned), and `git diff --check` pass. Strict runtime remains OPEN at
227. Block duration 13m10s (11:09:29–11:23:45 UTC), excluding 66.12s pytest.

SecretStore direct setters were a second, unguarded materialization API even
though current provider writes already arrived under `credential.write`. The
canonical file writer now lives only in `CredentialWriteEffectAdapter`, which
checks config digest, provider/key identity, canonical secret root and links
before atomic replacement/deletion. SecretStore retains path identity, reads
and pure encryption; public direct set/delete fail before filesystem effects.
Evidence: 10 credential adapter tests and 31 legacy-state/inventory tests
passed; `secrets.py` has zero sinks and all four adapter materializers are
`gateway_owned`. Compile and strict classification pass (2260 total / 223
runtime-unbound / 0 unclassified); strict runtime remains OPEN. Block duration
8m28s (11:23:45–11:32:57 UTC), excluding 44.15s of pytest.

The five sinks in `backend/.bago/seed.py` are now recorded as gateway-owned:
the only production loader is `project_memory.seed_project`, which first
requires the consumed operation-bound `project.write` authorization, and the
project lifecycle materializer callsite test restricts that entry to
`ProjectWriteEffectAdapter`. Inventory findings remain visible and a focused
test asserts all five findings retain gateway-owned classification. Evidence:
24 inventory tests passed in 21.16s; compile, strict classification (2260
total / 218 runtime-unbound / 0 unclassified), and `git diff --check` pass.
Strict runtime remains OPEN. Block duration: 1m10s (11:36:37–11:38:08 UTC),
excluding pytest.

Evidence bundle generation now uses strong `evidence.bundle.generate` in
effect-registry 1.19.0. Public CLI/API calls go through the TTY challenge and
consumed Permit. The request binds the output path, prior tree digest and all
generation options; the adapter checks path components and links, fingerprints
the old tree again after generation, stages beside the destination, then swaps
atomically and restores the old tree if commit fails. The eight low-level
`evidence_io.py` materialization findings remain visible and are gateway-owned;
the private bundle materializer has one production caller, the registered
adapter. Runtime `evidence --test` was removed, and validation references now
use pytest. Evidence: 46 focused tests passed in 35.35s; compile, strict
classification (2266 / 0 unclassified) and `git diff --check` pass. Strict
runtime remains OPEN at 210. Earlier runs caught and fixed the module size
limit and stale version expectation. Block duration: 13m29s
(11:41:29–11:56:31 UTC), excluding pytest execution.

The standalone ZIP rollback now uses `system.install.archive.rollback`, an E5
strong and non-delegable effect. Root CLI `bago rollback-archive` obtains direct
TTY approval over the exact install root/current tree digest, named ZIP/root and
ZIP digest, state choice, and unique safety ZIP. The adapter blocks symlinks,
special ZIP entries, traversal/duplicate paths, oversized archives, archive
drift, install drift and backup roots inside the install target. It extracts to
a sibling stage, creates a safety archive before replacement, preserves current
state unless archived state is explicitly selected, and restores the original
install if swapping fails. `rollback-bago.ps1` is an inert migration pointer;
its inventory has zero sinks, and all materializer sinks remain visible under
the registered adapter. Evidence: 37 focused tests passed in 26.62s; compile,
strict classification (2274 total / 0 unclassified), and diff check pass.
Strict runtime remains OPEN at 201. Block duration: 10m13s
(11:59:18–12:10:25 UTC), excluding 53.59s aggregate pytest execution.

GitHub repo connection no longer performs `state.mkdir` before its atomic
`state.write`. The one persistent materializer now owns both parent creation
and replacement, preserving repo-connection behavior without another effect
owner. Evidence: 66 tests passed in 4.04s; compile, strict classification
(2273 / 0 unclassified), and `git diff --check` pass. Strict runtime remains
OPEN at 200. Block duration: 41s (12:12:47–12:13:32 UTC), excluding pytest.

## 2026-09-25 — Memory database owner and redundant session index removal

`KnowledgeBase` and `EmbeddingStore` now expose read-only access only. Their
bounded mutations share the registered `database.write` adapter, which
rechecks the active session, canonical state root and target, derives source
session from the active SessionManager, serializes in-process writes per root,
and writes schema/FTS/WAL and embedding records. Chat, REPL and the HTTP
embedding-upsert route use challenge → approve → one-time Permit → adapter.
The scanner continues to report adapter materialization sinks and tests bind
them to the registered owner.

`SessionDB` was deleted after tracing its only production caller: session save
updated the SQLite index, but no product read path consumed it;
`ContextStore.list_sessions` enumerates session metadata and session JSON is
already canonical. Workspace save receipts now require the session JSON only.
This removes a second session persistence path rather than adding another
database writer.

Evidence: 102 memory/RAG/gateway/inventory tests passed; 67 session,
workspace/inventory tests passed after retiring SessionDB. BAGO `verify`
fingerprints strict classification PASS at 2336 sinks / 100 runtime-unbound /
0 unclassified. Strict runtime remains FAIL/OPEN at 100. `git diff --check`
passes. The full backend suite, committed candidate and independent review
remain outstanding. The worktree is intentionally dirty; these results are
scoped execution evidence only. Reconstructed change time: about 15 minutes,
excluding 2m58s of pytest and about 48s spent in inventory gates; a stopwatch
was not started at the block's beginning.

## 2026-09-25 — CLI manager process launch and instance lock

The direct server `Popen` in `bago manager` now dispatches through the existing
`process.execute` owner. The CLI binds a direct TTY challenge to the exact
launcher digest, workspace, compiled UI, loopback host and port; the adapter
checks the consumed Permit and revalidates the target before creating the
detached server process. `bago_core.instance_lock` owns only the singleton
coordination file, and the CLI `serve` command remains the sole lock caller.

Evidence: four focused tests passed in 4.42s under a 60s process timeout;
Python compile, strict classification and `git diff --check` passed. Inventory
is 2338 / 96 runtime-unbound / 0 unclassified. Strict runtime remains OPEN.
The global backend suite, committed candidate and independent review are not
complete. Reconstructed change duration: about 4m40s, excluding about 37s of
compile/test/gate execution; interruptions prevented stopwatch-level timing.

## 2026-09-25 — BagoContext process and event queue

`BagoContext.run_tool()` retains its API signature but now fails closed. The
repository has no callers, and its arbitrary `subprocess.run` was outside the
Gateway. `flush_events(clear=True)` now clears the durable queue by replacing
the file with empty content through the existing `state.write` owner; the
runtime module has no direct effect sinks.

Evidence: 2 focused tests passed in 0.23s with a 60s timeout; compile, BAGO
strict classification, and `git diff --check` passed. Inventory is
2338 / 94 runtime-unbound / 0 unclassified; strict runtime remains OPEN.
The change took about 3m30s excluding about 11s of test/gate execution; timing
is reconstructed after interruptions.

## 2026-09-25 — Legacy model WRITE markers are display-only

`SessionTurnMixin` no longer materializes `[WRITE:path]...[/WRITE]` blocks.
The response displays the path and proposed content while saying it is not
written. Actual file changes must use the existing `filesystem.write`
challenge/Permit and Gateway adapter. This removes model-output-controlled
mkdir/write authority without adding another executor.

Evidence: 1 focused test passed in 0.15s with a 60s timeout; compile, BAGO
strict classification, and `git diff --check` passed. Inventory is
2336 / 92 runtime-unbound / 0 unclassified; strict runtime remains OPEN.
Change duration: about 3m15s excluding about 11s of compile/test/gate.

## 2026-09-25 — Session state root resolution is read-only

`resolve_state_root` now returns canonical identity without creating the
directory. `SessionManager` and `mark_active_session` no longer create it in
parallel; canonical state writers own materialization when a write occurs.

Evidence: 19 focused user-state/session-recovery/persistence/workspace tests
passed in 3.62s; compile, BAGO strict classification, and `git diff --check`
passed. Inventory is 2333 / 89 runtime-unbound / 0 unclassified; strict
runtime remains OPEN. Change duration: about 1m58s excluding about 14s of
checks.

## 2026-09-25 — Git identity inspection migrated

`SessionPersistenceMixin._git_info()` now dispatches its exact repository-root
and branch queries through the existing server-policy `process.inspect` owner.
The Git read-only allowlist admits only three exact `rev-parse` argv shapes;
no new execution authority was introduced. Evidence: 57 focused tests passed
in 3.08s; compile and diff check passed. Direct inventory: 2331 total / 87
runtime-unbound / zero unclassified; strict classification PASS, strict runtime
OPEN. The repository verify wrapper failed to spawn its child (`WinError 2`),
so the scanner itself was run directly under a 90s timeout. Change duration was
approximately 3m35s (18:48:31–18:52:30 UTC), excluding about 25s for tests,
compile and gates. Candidate commit, full backend suite and independent review
remain open.

## 2026-09-25 — Deshabilitado el writer standalone sin Permit

`backend/.bago/tools/file_write.py` ya no crea directorios ni escribe por sí
solo. El shim responde con `filesystem_write_authorization_required` y dirige a
la ruta de sesión `/files/write`, cuyo challenge, aprobación y Permit ya
materializan mediante `FilesystemEffectAdapter`. `BAGO_DEV_MODE` no es autoridad
y no relaja esta frontera. El manifiesto conserva el hash actualizado del tool
y el registro avisa que el shim está deshabilitado. Evidencia: 47 pruebas
focales pasaron en 4.05s; compile, strict classification y diff check PASS.
Inventario: 2329 total / 85 runtime-unbound / cero unclassified; strict runtime
continúa abierto. La UI/API autorizada conserva la escritura; el CLI standalone
legacy queda limitado hasta disponer de sesión y autorización propias. Tiempo
de cambio estimado: ~5m40s (18:52:30–18:58:32 UTC), excluyendo unos 22s de
pruebas, compilación y gates.

## 2026-09-25 — Materialización de Node Control sin mkdir paralelo

`materialize_piece_store()` ya no crea directamente el root, las categorías o
las carpetas de piezas. El writer registrado de `manifest.json` materializa sus
padres al hacer la escritura; si el manifiesto ya existe, también existen sus
padres. Prueba de regresión confirma ese orden. Node Control split + translator:
29 passed en 9.94s; compile, strict classification y diff check PASS. Inventario:
2326 total / 82 runtime-unbound / cero sin clasificar; strict runtime sigue
OPEN. Tiempo de cambio estimado ~4m35s (18:58:32–19:03:34 UTC), excluyendo unos
25s de pruebas, compilación y gates.

## 2026-09-25 — Append de planes de agente por state.write

`AgentOrchestrator` ya no crea el directorio del plan ni abre directamente el
JSONL en modo append. La ruta se calcula sin materializar; el registro se anexa
con `bago_core.atomic_json.append_text_durable` (`state.write`). Prueba nueva
comprueba que el directorio no exista antes del writer. `test_agent_kit.py`:
43 passed en 3.64s; compile, strict classification y diff check PASS. Inventario:
2324 total / 80 runtime-unbound / cero sin clasificar; strict runtime OPEN.
Tiempo de cambio estimado ~1m35s (aprox. 19:06:07–19:08:05 UTC), excluyendo
~22s de pruebas, compilación y gates.

## 2026-09-25 — Proyección Android delegada a state.write

`cmd_android._write_layers_state()` conserva ruta y payload, delegando el JSON
atómico en `bago_core.atomic_json.write_json_atomic` (`state.write`). Se
eliminaron el mkdir y `write_text` propios. Una prueba confirma delegación y
payload. Prueba final 1 passed (0.24s); py_compile, clasificación y diff check
PASS. El primer intento falló porque `bago_core.commands.cmd_android` se importó
como atributo función; se corrigió a importlib del módulo y se repitió con éxito.
Inventario: 2322 total / 78 runtime-unbound / cero unclassified; strict runtime
continúa OPEN. Duración neta estimada ~2m47s (19:08:05–19:11:05 UTC), sin unos
13s de prueba, compile y gates.

## 2026-09-25 — Persistencia del ledger de evidencia

`ClaimLedger` ya no crea `evidence/` en el constructor. `claims.jsonl` y
`claim_receipts.jsonl` anexan mediante `append_text_durable` (`state.write`). El
contrato `execution_claims.v1.md` ahora registra explícitamente que este writer
no transforma evidencia en claim de ejecución, no autoriza y no emite Permit.
`ClaimLedger` sigue separado de `ExecutionClaimStore`. Evidencia: 16 pruebas
focales passed en 13.34s; compile, strict classification y diff check PASS.
Inventario: 2320 total / 75 runtime-unbound / 0 unclassified; strict runtime
OPEN. Tiempo neto estimado: ~2m10s (19:11:05–19:13:53 UTC), excluyendo unos 34s
de tests, compile y gates.

## 2026-09-25 — Raíces de estado por Gateway y backups sin poda al arrancar

`state.directory.ensure` queda registrado como efecto server-policy y lo
materializa `ServerStateEffectAdapter`, limitado a los destinos que resuelve el
contrato vivo de `BAGO_USER_ROOT`, `BAGO_RUNTIME_ROOT`, `BAGO_STATE_ROOT`, cache
y backups. La autorización ocurre antes del adapter y el target se vuelve a
validar antes de `mkdir`. Se mantuvo el override explícito de estado incluso
cuando vive fuera del root de usuario; el receipt representa ese caso sin
intentar una ruta relativa inválida. `ensure_user_roots()` ya no ejecuta
`unlink`: `backup_prune_candidates()` solo calcula candidatos de retención.

Evidencia: 77 pruebas focales de rutas, lock, runtime-state, registry y Gateway
pasaron en 8.13s con timeout de 60s y basetemp dentro del checkout. Una primera
corrida no aisló el basetemp y falló al enumerar Temp global por permisos; una
segunda corrida encontró el surface sin prefijo `server.` y una tercera detectó
el receipt del override; ambos defectos se corrigieron antes del pase final.
`py_compile` y `git diff --check` PASS. Inventario: 2321 sinks / 73
runtime-unbound / 0 sin clasificar; strict-classification PASS,
strict-runtime FAIL/OPEN. Duración neta del cambio reconstruida: ~12m,
excluyendo pruebas y gates; no se capturó cronómetro continuo.

## 2026-09-25 — AuditTrail usa el writer canónico de estado

`OperationalIntegrity.AuditTrail.append()` conserva timestamp, payload JSONL y
ruta, pero delega el append en `bago_core.atomic_json.append_text_durable`
(`state.write`). Se retiraron el `mkdir` y el `Path.open` duplicados; la prueba
confirma que una carpeta ausente se crea durante el append gobernado.

Evidencia: `test_operational_integrity.py` + `test_claim_ledger_split.py`:
21 passed en 16.05s bajo timeout de 60s y basetemp local. Un primer intento
detectó que la fachada `atomic_json` no acepta `source_surface`; se quitó ese
argumento y se repitió con éxito, conservando el surface canónico existente.
`py_compile`, strict-classification y `git diff --check` PASS. Inventario:
2319 sinks / 71 runtime-unbound / 0 sin clasificar; strict-runtime FAIL/OPEN.
Duración neta reconstruida ~5m, excluyendo unos 16s de prueba y gates.

## 2026-09-25 — Fingerprint Git del candidato por process.inspect

`bago_core.candidate_identity` dejó de ejecutar `subprocess.run` directamente.
Las consultas exactas de raíz, HEAD, rama, upstream, remote y status pasan por
el owner existente `process.inspect`. El allowlist acepta solo esas consultas
read-only, con prefijos `safe.directory` absolutos, y rechaza mutaciones. El
diff binario del worktree se resume dentro del adapter como SHA-256 para no
truncar salida grande ni mover el cálculo/ejecución a una segunda autoridad.

Evidencia: `test_session_git_info_gateway.py`, `test_execution_gateway_v2.py`
y `test_governed_verify_receipt.py`: 63 passed en 25.98s bajo timeout de 90s y
basetemp local. Un primer pase encontró que `encoding` forzaba texto incluso
con `text=False`; corregido y el bloque completo pasó. `py_compile`,
strict-classification y `git diff --check` PASS. Inventario: 2317 sinks / 69
runtime-unbound / 0 sin clasificar; strict-runtime FAIL/OPEN. Duración neta del
cambio reconstruida ~7m, excluyendo unos 26s de pruebas y gates.
