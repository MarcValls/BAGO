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
- Frontend client/ControlPlane/navigation gate: `35 passed`; typecheck PASS;
  production build PASS (`123 modules`); Python compile and `git diff --check`
  PASS.
- Inventory after the B2 code path: `2104` total findings, `473`
  `runtime_unbound`, `243` runtime high-confidence, `0` unclassified
  scope/binding; `--strict-classification` passes and `--strict-runtime`
  remains intentionally FAIL/OPEN. The total increases because the inventory
  retains the adapter's material sink findings; no finding is hidden.

This tranche is `EXECUTED / SCOPED`. Full backend evidence, final candidate
identity and independent verification remain pending; no global `VERIFIED` or
`VALIDATED` claim is made.
