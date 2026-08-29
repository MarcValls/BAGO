# BAGO audit remediation handoff

## Scope

Remediation of BAGO-AUD-001 through BAGO-AUD-010 from the robust third-party
audit dated 2026-08-22. The declared boundary is documented in
`remediation-baseline-20260824.md`. The dirty patch bytes were not retained at
capture time, but the active closure blocker is now resolved by
`remediation-baseline-recovery-20260828.md`, which retains a recovered CRLF
patch matching the recorded SHA-256.

## Candidate contents

- truthful plan execution and intent stance boundaries;
- canonical BAGO/gestor KV integration contract;
- crash-safe release rollback resume;
- operational truth/evidence/state-transition policies;
- truthful repository status and candidate fingerprinting;
- reproducible evidence packager, raw gate recorder and provenance contract;
- CI gates that fail closed;
- updated UI smoke contract and source-package recursion guard;
- removal and permanent exclusion of session-export HTML.

## Verification protocol

Use `remediation-closure-contract-20260824.md`.  Candidate identity is the full
SHA stored in `audit/bago-provenance.json` in the generated evidence bundle.
The package must contain raw logs for every claimed gate and must pass its own
raw-patch application checks.  This handoff never substitutes for those logs.

## State discipline

The committed remediation is `EXECUTED`.  It becomes `VERIFIED` only when all
candidate-bound gates pass.  It becomes `VALIDATED` only after the independent
review also reports no blocker.  The former audited worktree and this
remediation remain distinct state objects. The previously unreconstructable
initial dirty attribution boundary has been recovered and no longer blocks
global `VALIDATED`; final validation still requires the candidate-bound gate
and review evidence to refer to the same immutable candidate.
