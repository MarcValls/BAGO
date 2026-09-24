# Execution Claims v1

Status: `EXECUTED / SQLITE_LOCAL_SLICE_WITH_WRITE_RECONCILIATION`; PostgreSQL
adapter implemented but integration `NOT_RUN` without a configured database/driver.

## Purpose and naming

`ExecutionClaimStore` coordinates the right to execute a material operation on
a named resource. It is separate from `bago_core.claim_storage.ClaimLedger`,
which stores evidence-backed assertions. The evidence ledger is not a lock or
execution coordinator.

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

The 04 governed pipeline currently claims canonical file resources for
`filesystem.read` and `filesystem.write`. The claim is acquired before budget
reservation. Its `operation_id` binds pipeline operation, step, attempt, and
step fingerprint; the pipeline separately carries its idempotency key. The nested
gateway verifies the claim owner, resource, operation, claim id, and fencing
token immediately before invoking the server-owned adapter. Claim identity and
fencing generation are retained in the step outcome and evidence.

The existing per-plan `RLock` remains for mutable PlanEngine and plan state.
This implementation does not coordinate project/workspace/credential sinks or
other unclaimed effects.

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
transaction spanning the filesystem and ledger. The current pipeline claims
only canonical file resources for `filesystem.read` and `filesystem.write`.

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
