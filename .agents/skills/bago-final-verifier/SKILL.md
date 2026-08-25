---
name: bago-final-verifier
description: Independent final verification of BAGO changes and closures. Use after implementation or before release to review diffs and evidence, looking for regressions, broken contracts, insufficient tests, scope creep, and unsupported claims.
compatibility: Pi 0.84.2+. Read-only verifier; does not edit code. Returns PASS, FAIL, or BLOCKED with evidence.
metadata:
  targetHarness: pi
  minPiVersion: 0.84.2
  sourceRepo: MarcValls/BAGO
---

# BAGO Final Verifier for Pi

Independent verification pass for BAGO work. Use this skill after an implementation phase or before declaring a closure.

## Procedure

1. Review the current `git diff` or the relevant diff range.
2. Read `.bago/state/PROJECT_STATE.json`, `.bago/runtime/ACTIVE_HANDOFF.md`, and any acceptance criteria if they exist.
3. Check for:
   - Regressions in existing behavior.
   - Broken frontend/backend contracts.
   - Insufficient tests or checks.
   - Changes outside the authorized scope.
   - Unsupported claims in the prior output.
4. Run the repository's own verification commands where safe and relevant (tests, type checks, linters).

## Verdicts

- `PASS` — evidence supports the closure claim.
- `FAIL` — evidence contradicts the closure claim; list what failed.
- `BLOCKED` — missing information or material conflict prevents a verdict.

## Rules

- Do not fix code; only report.
- `VERIFIED` requires executed evidence.
- `VALIDATED` additionally requires satisfied closure criteria and defined validation authority.
- Never convert the absence of findings into proof beyond the verification scope.
- If the task is large or ambiguous, use `/skill:bago-core` first for context and state.
