# Backend audit remediation — b10178bf

## Authority and scope

P2 execution requested by the user for the five backend findings supplied in this session. Baseline: HEAD `b10178bf8a13d0035079e989e46c36760dbd2a46`, branch `fix/spbe-runtime-fix1-20260927`, dirty worktree. Canonical product version is resolved from `release_version.txt`. Baseline backend scoped source fingerprint: `4031398190235283f858b06bb60f908ada5fd5f83cc1ba6fc441d0b22538ce27` (sorted Git-tracked files under backend `.bago/api`, `.bago/core`, `.bago/providers`, `tests`; SHA-256 of path + NUL + each file SHA-256).

Preserve unrelated bootstrap, IPC, Electron, runtime-sink partition and existing goal work. No global sink remediation, registry changes, builds/signing/installations, commit, push, production secrets or live provider requests. This contract is immutable once execution starts; record implementation decisions and limitations in status.json.

## Acceptance criteria

1. Named cloud provider HTTP test/configuration cannot silently send stored or environment credentials to a caller-selected noncanonical endpoint. Reject an untrusted endpoint before transport or config mutation; preserve canonical endpoint behavior and local provider configuration. Cover the real handler/adapter chain with fake secrets and intercepted transport.
2. Bind nonstreaming and streaming session turns to the conversation captured at entry, including HTTP watchdog execution on another thread. Switching/creating another conversation while a provider is waiting must not redirect persisted messages or response evidence.
3. Disallowed browser Origin cannot execute mutating HTTP requests, including tokenless mode and text/plain JSON. Preserve trusted UI origins and authenticated/native originless clients. Test rejection before dispatch; do not claim a live browser exploit test.
4. A chat timeout must not encourage an unidentified/replayed material turn. Use an identifiable, queryable operation with idempotent retries and explicit running state (or cooperative cancellation with equivalent evidence). Do not promise rollback of effects already executed. Prove a timeout followed by retry does not call send twice.
5. Corrupt JSONL records must be reported. Preserve the original bytes and block destructive rewrites of a stream loaded with corruption; valid records may remain readable. Test corrupt context and timeline, malformed UTF-8, and valid legacy histories.

## Execution blocks and checks

- Provider credential endpoint boundary + mocked/offline provider registration tests.
- Conversation binding + real store/concurrent turn regression tests.
- Origin protection + auth/HTTP plumbing regression tests.
- Identified timeout/idempotency + watchdog/retry regression tests.
- Corruption reporting/rewrite protection + context persistence/recovery regression tests.
- Combined backend focused gate, compile check, git diff --check. Full backend suite when feasible; explicitly record anything omitted or failing.

After each block update status.json with builder_summary, checks_run and candidate evidence. P2 result is EXECUTED only. Independent P3 certification and VERIFIED/VALIDATED promotion are outside this request.
