# Execution Claims v1

Status: `EXECUTED / SQLITE_LOCAL_SLICE_WITH_WRITE_RECONCILIATION`; PostgreSQL
adapter implemented but integration `NOT_RUN` without a configured database/driver.

## Purpose and naming

`ExecutionClaimStore` coordinates the right to execute a material operation on
a named resource. It is separate from `bago_core.claim_storage.ClaimLedger`,
which stores evidence-backed assertions. The evidence ledger is not a lock or
execution coordinator.

The evidence ledger remains a separate assertion/evidence authority. Its
append-only claim and receipt files persist through the registered `state.write`
adapter; this storage route does not make an evidence claim an execution claim,
grant authorization, or issue a Gateway Permit. `ExecutionClaimStore` continues
to coordinate same-resource execution only, and `AuthorizationBoundary` plus
the Gateway adapter remain the authorization/effect authority.

The current contract is implemented in the hidden runtime module
`backend/.bago/core/execution_claims.py`. It defines:

- `try_acquire(resource_key, owner_id, operation_id, lease_seconds)`
- `renew(claim)`
- `release(claim)`
- `validate(claim)`
- `expire()`
- `execute_if_valid(claim, operation)`

The same module resolves the manager-scoped store with
`execution_claim_store_for(manager)`: a trusted `state_root` selects the
cached SQLite store for `execution_claims.sqlite3`; a lightweight manager
without that root uses the process-local default. `ExecutionGateway` retains
the injection override and delegates default selection here.

An `ExecutionClaim` carries `claim_id`, `resource_key`, `operation_id`,
`owner_id`, `lease_until`, `fencing_token`, `status`, `created_at`,
`renewed_at`, and `released_at`.

## Adapters and scope

`InMemoryExecutionClaimStore` is thread-safe inside one Python process. Tokens
increase monotonically per resource for the lifetime of that process. A live
claim excludes another owner of the same resource; unrelated resources can be
claimed independently. Expired claims cannot execute. `execute_if_valid`
validates the current claim and holds a per-resource effect guard while the
gateway adapter runs, so a replacement claim cannot overlap that in-process
effect.

`SQLiteExecutionClaimStore` owns claim coordination in the canonical user state
database `<SessionManager.state_root>/execution_claims.sqlite3`. The separate
`SQLiteExecutionOperationStore`, implemented in
`backend/.bago/core/execution_operations.py`, owns the `execution_operations`
table in that same database file. It is keyed by the stable step idempotency
key. A filesystem write is recorded as `PENDING` with its canonical resource
key and desired-content digest before dispatch; after the adapter returns a
receipt it is marked `COMMITTED` with the receipt payload. Reusing an operation
key with a different resource or digest is rejected. Separate BAGO processes
using that same state root coordinate through SQLite transactions. A regular
`SessionManager` selects this adapter automatically for governed plan effects;
an injected store remains available for controlled tests and hosts. Lightweight
test managers without `state_root` retain the process-local default.

For a material callback, SQLite holds `BEGIN IMMEDIATE` while checking the
claim and running the gateway adapter. Another process cannot replace the
claim generation during that callback. SQLite has one writer per database,
however, so this currently serializes material callbacks across all resource
keys even though acquisition is keyed per resource.

`PostgresExecutionClaimStore` is an explicit, optional adapter for a shared
PostgreSQL service. It uses database time, a unique resource row, atomic
`INSERT .. ON CONFLICT .. WHERE .. RETURNING` acquisition, and row locking
while a gateway callback runs. `psycopg` 3 is loaded lazily; hosts must provide
the driver and DSN or inject a DB-API connector. It is never selected by the
local runtime automatically.

The 04 governed pipeline claims canonical resources for `filesystem.read`,
`filesystem.write`, and `process.execute`. The claim is acquired before budget
reservation. Its `operation_id` binds pipeline operation, step, attempt, and
step fingerprint; the pipeline separately carries its idempotency key. File
resources use their canonical target path. Process resources use the normalized
working directory, argv operation, and active session identity; pipeline-only
metadata is excluded from the process operation key. The nested gateway
verifies the claim owner, resource, operation, claim id, and fencing token
immediately before invoking the server-owned adapter. Claim identity and
fencing generation are retained in the step outcome and evidence.

An execution claim coordinates competing operations; it does not authorize an
effect. The parent `plan.execute` Permit authorizes the governed plan, and each
child effect is dispatched through its registered server-owned adapter. The
process adapter independently checks the consumed Permit or verified nested
plan context, then validates argv and confines cwd to the active workspace
before spawning. Direct process callers outside this governed pipeline are not
covered by this claim integration and remain visible to the global runtime
sink inventory.

The existing per-plan `RLock` remains for mutable PlanEngine and plan state.
This implementation does not coordinate project/workspace/credential sinks or
other unclaimed effects.

## Evidence bundle generation

Public evidence-bundle generation is an explicit `evidence.bundle.generate`
effect. The CLI request binds the absolute output directory, its current
content fingerprint, generation mode/objective/provider/model, base path, and
overwrite choice. Generation requires a strong, direct TTY Permit and the
adapter rechecks the output tree immediately before replacing it. It builds a
sibling staging directory, atomically swaps the completed bundle into place,
and preserves/restores the old tree if that swap fails. The lower-level
materializer is only called by the registered adapter; runtime `--test`
materialization was removed in favor of pytest.

## Archived install rollback

Restoring a Program Files backup ZIP uses the distinct
`system.install.archive.rollback` effect with a strong, non-delegable direct
CLI Permit. The request binds the exact install path and current tree digest,
backup root, archive path and digest, state-preservation choice, and a unique
safety-archive destination. The adapter validates ZIP paths and entry types,
rejects links and expansion beyond its limit, stages extraction beside the
install target, and rechecks the archive and current tree before replacement.
Unless the user explicitly chooses archived state, current `.bago/state`,
`.bago/logs`, `state`, and `logs` are preserved. The retired PowerShell script
does not restore files; it directs users to `bago rollback-archive`.

## GitHub CLI process execution

GitHub CLI reads use the registered `process.inspect` owner and a fixed argv
allowlist for `gh auth status` and GET-only `gh api repos/...` endpoints. The
request is bound to the active SessionManager session and workspace cwd. Repo
creation and auth login/logout use `process.execute` through the Electron
process-execution client: the challenge binds the exact executable, cwd, argv,
and timeout, and the consumed Permit is required before spawn. A login token,
when supplied, stays in the Permit-bound request and is redacted from the
native confirmation dialog. The API handler no longer spawns `gh`/`git`; the
duplicate MCP repository-creation tool and legacy mutating HTTP routes are
retired. GitHub setup routes that remain return 410 until a governed Desktop
caller is provided.

The continuity CLI reads Git HEAD through the same `process.inspect` owner with
the exact read-only argv `git rev-parse HEAD`. Its `verify` subcommand accepts
only `pytest` or `python -m pytest`; it normalizes the interpreter to the
active BAGO runtime, binds cwd and argv in a `process.execute` request, and
requires a direct TTY Permit before the process starts. Arbitrary commands
and inline Python are rejected before authorization or spawn.

## Explicit limits

`InMemoryExecutionClaimStore` is not durable: restart loses owners and fencing
counters. SQLite makes local claim ownership and fencing generations durable
and coordinates processes sharing the same local database. It is not a
multi-machine store and is not a distributed lease service. The SQLite
transaction protects the in-process gateway callback from concurrent lease
transfer; it does not make the filesystem effect and claim database one atomic
transaction. The operation ledger cannot commit atomically with the file
replace. If a caller loses the receipt after replacement, a later authorized
attempt may reconcile only when an unresolved pipeline outcome and a durable
`PENDING` or `COMMITTED` record match the same operation key, resource and
desired-content digest. For `PENDING`, it reapplies the desired content (a
same-content no-op), then commits the returned receipt. A `COMMITTED` ledger
receipt repairs a stale pipeline outcome without repeating the effect. Without
a matching durable record, the unresolved outcome remains blocked. This is
at-least-once idempotent desired-state recovery, not exactly-once execution or a
transaction spanning the filesystem and ledger. The governed pipeline claims
canonical file resources for `filesystem.read` and `filesystem.write`, and
normalized process operations for `process.execute`. Other unclaimed effects
and direct process callers remain outside this pipeline integration.

Nested gateway dispatch normalizes the internal claim record before passing it
to the selected store. This handles duplicate Python module identities from
the hidden runtime import path; the store still verifies owner, resource,
operation, claim id, generation and active lease against canonical state.

The PostgreSQL adapter coordinates claims across hosts sharing the database,
but claim storage alone cannot fence a process that continues after losing its
database connection. Because the current filesystem adapter has no atomic
generation-aware sink contract, the governed pipeline fails closed before a
material filesystem effect when this adapter is injected. Distributed claim
acquisition is implemented; distributed filesystem execution is not enabled.

`filesystem.write` writes a sibling temporary file, flushes it, and atomically
replaces the target. Replaying the same desired content is a no-op with the
same content receipt. This avoids torn visible files and makes that file write
idempotent by content. The local durable ledger supports this recovery model;
it does not span a separate PostgreSQL transaction.

Release-job archival is the explicit `release.job.archive` effect. Its request
fingerprint binds the job ID, persisted-state SHA-256, and archive timestamp.
`AuthorizationBoundary` issues and consumes the Permit; the adapter rechecks
the digest, identity, and terminal state before creating an archive or moving
the active state, log, and staging tree. A changed job or existing archive is
blocked before the first material write. If a move fails and rollback also
fails, the adapter preserves the partial archive and reports its recovery path
instead of deleting moved data. The archive remains recoverable.

The adapter selection is visible in outcome metadata as `durable-local` or
`process-local`. The latter remains for test/fake managers without a trusted
`SessionManager.state_root` and for explicitly injected in-memory stores.

To enable distributed material effects, add a sink contract that atomically
enforces the current fencing generation for every write and a durable
idempotency/reconciliation record. If the shared sink cannot enforce those
properties, keep the current fail-closed behavior.

## Verification scope

Focused tests cover per-resource exclusivity, independent resources, lease
renewal and expiry, monotonically increasing generations, stale-owner
rejection, one governed plan write through the gateway, SQLite restart/recovery,
durable operation-ledger replay and ambiguous-write reconciliation, and
simultaneous acquisition by separate processes. These checks cover one machine
and a shared local SQLite file only. The optional PostgreSQL
integration test runs only when `BAGO_TEST_POSTGRES_DSN` and `psycopg` are
available; neither is present in the current environment, so distributed
database execution is `NOT_RUN`. Distributed filesystem execution remains
disabled and exactly-once behavior is not claimed.
