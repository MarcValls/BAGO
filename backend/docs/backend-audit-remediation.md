# Backend audit remediation — P2 behavior notes

Implementation scope: `.goals/backend-audit-remediation-b10178bf/goal.md`.
This document describes the executed behavior; it is not a P3 certificate.

## Provider credentials

Named cloud providers with a fixed catalog URL reject a noncanonical base URL
before API test/configuration proceeds. Persisted and legacy endpoint overrides
are also checked when building a session adapter. Canonical URL matching rejects
userinfo, query/fragment/params, malformed ports, host/scheme/port/path drift.
This intentionally blocks custom gateways configured under a fixed cloud provider
name; local/custom provider endpoint configuration is unchanged.
Credential-bearing provider HTTP transport follows redirects only within the
same scheme, hostname and effective port. The guard belongs to the network
adapter's own opener, not the process-wide urllib opener.

## Conversation identity

`send` binds to the conversation captured at call entry. `send_stream` captures
identity when called, before the returned iterator is advanced. Each next/send/
throw/close executes under the bound scope and restores the caller's scope before
yielding; sequential resumes on different threads and generator finalization are
covered. An already-bound stream may finish after its conversation is archived,
but a new stream cannot select an archived conversation. HTTP watchdog workers enter the conversation scope
captured by the requesting thread. Switching the active conversation does not
redirect persisted messages of an in-flight turn.

## Browser request boundary

POST, PUT and DELETE reject an explicit untrusted Origin, including `null`, before
reading the body or dispatching. The same rule applies with or without a token,
and also to text/plain bodies containing JSON. Trusted configured/development
origins and native originless clients retain their token authentication behavior.
No live browser exploit has been tested; browser loopback access is conditional.

## Chat timeout and retries

A timeout means **waiting expired**, not cancellation or rollback. HTTP 504 now
includes `response_state: running`, server-issued `turn_id`, `conversation_id`,
and `retry_with_same_turn_id: true`. Poll using the authenticated POST `/chat`
with `{ "turn_id": "<returned-id>" }`; no message is needed. A poll waits up to
the chat watchdog interval and returns the original completed snapshot or the
same running operation. Reusing the ID never starts another turn. Supplied retry
content must match the original request.

Only one `/chat` operation may run per SessionManager. A new request while it is
running returns 409 and the existing ID. Completed snapshots are retained for
the latest 64 operations in memory. Unknown/evicted IDs, including after restart
or session replacement, return 404 without execution. IDs are lookup keys, not
Permits. This does not promise durable recovery of results across restart, nor
idempotency for a deliberately new request sent without the previous ID after
completion. Streaming and CLI are not covered by this HTTP result cache.

## Corrupt history

JSONL load retains valid records but logs and exposes `recovery_errors` with
path, line number and reason, without including message content. Invalid UTF-8,
JSON and text/schema fields are reported. Read I/O failures propagate; they are
not treated as empty history. Files loaded with corrupt records cannot be
rewritten by mark-good, clear-history or compression. Append remains additive,
including a separator after a torn final record, preserving original bytes.
Detection is per loaded store; external edits after load are not certified by
this protection. Repair/recovery of the corrupt records is a separate action.

## Test execution

Use the repository's existing ignored `.run/` tree for pytest basetemp (create
its parent first). An unignored basetemp within the repository invalidates the
governed receipt test's output-boundary precondition. The real CLI seed smoke
now uses a small temporary workspace rather than scanning/materializing the
checkout and accumulating old test artifacts. No inventory scanner exclusions,
authorization checks or production effect registries were changed.
