# BAGO remediation baseline

- Remediation state: `PROPOSED`
- Product audit state: `EXECUTED / PARTIALLY VERIFIED`
- Candidate baseline captured: 2026-08-24
- Repository: `C:\Users\AMTEC_Terminal_1º\BAGO`
- HEAD: `e76b01b0a0552d8eee7c536f8c4eef25e3a82a42`
- Branch: `main`
- Upstream: `origin/main`
- Remote: `https://github.com/MarcValls/BAGO.git`
- Working tree: `DIRTY`
- Existing tracked diff SHA-256 (UTF-8 export of `git diff --binary`): `943f59fd339f0f57c63f21beb785c0d3c35f6977ecf7bf569b74c324a523bb79`

This baseline is an attribution boundary. Changes listed below predate the remediation and must not be attributed to it. No code or state transition was performed while capturing this record.

## Provenance limitation discovered during closure

The SHA-256 above was captured, but the corresponding dirty patch bytes were
not retained. The file list and hash prove that a dirty boundary was observed;
they do **not** let a third party reconstruct or independently verify its exact
contents. Consequently, strict attribution between those pre-existing edits
and later remediation edits remains `UNRESOLVED`. This limitation must be
carried into every handoff/package and blocks global `VALIDATED`; it must never
be replaced by a reconstructed or inferred patch presented as the original.

## Existing tracked changes

- `backend/.bago/api/handlers_jobs.py`
- `backend/.bago/core/config_manager.py`
- `backend/.bago/core/plan_engine.py`
- `backend/.bago/core/session_turn_mixin.py`
- `backend/tests/integrations/pi/test_negatives.py`
- `backend/tests/test_plan_engine_contract.py`

## Existing untracked changes

- `.goals/current-plan.md` — SHA-256 `eb9a0e9a2a5aaac22c39df4961383fde3524270f32b3eb2aa169565a8cafe46a`
- `backend/tests/test_conversational_goal.py` — SHA-256 `71ee352b7748c083a934fb7734d286b39146c79cc1e0b99a3041141a0760947b`
- `pi-session-2026-08-23T16-40-01-002Z_01a02f7e-4aea-7587-b545-9bdfa00aeaf3.html` — SHA-256 `119b293946ed4ac107ab1a5f5d7da01087149e50ede57ea1149ffdfed820fe3e`

## Closure matrix opened at baseline

Every item remains `OPEN`; no remediation item has transitioned to `EXECUTED`.

| ID | Required closure evidence | State |
|---|---|---|
| BAGO-AUD-001 | Negative no-executable-actions regression and truthful response | OPEN |
| BAGO-AUD-002 | Affirmative, negated and interrogative intent regressions | OPEN |
| BAGO-AUD-003 | Real gestor-con-Bago health/read/write/update/delete integration | OPEN |
| BAGO-AUD-004 | Crash-injected, idempotent release resume with recoverable rollback | OPEN |
| BAGO-AUD-005 | Canonical-LF patch passes raw `git apply --check` | OPEN |
| BAGO-AUD-006 | Full SHA, remote, branch/upstream and SHA-256 manifest | OPEN |
| BAGO-AUD-007 | Included handoff or removed handoff claim | OPEN |
| BAGO-AUD-008 | Raw, timestamped, SHA-bound logs for every claimed gate | OPEN |
| BAGO-AUD-009 | gestor-con-Bago baseline/delta provenance and reproducible checks | OPEN |
| BAGO-AUD-010 | Session HTML removed or explicitly sanitized and inventoried | OPEN |

## Required transition chain

`finding -> remediation -> regression fails before -> regression passes after -> evidence -> immutable candidate SHA -> state transition`

The next change must identify the affected `BAGO-AUD-*` IDs and must not modify this baseline record.
