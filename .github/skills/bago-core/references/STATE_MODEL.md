# BAGO State Model — Provisional Adapter

Use state labels as evidence-bearing claims, not stylistic language.

## PROPOSED

The change/result exists only as an idea, recommendation, design, or requested action.

Required evidence: proposal text or decision record.

## PREPARED

The intended artifact is constructed but not yet applied/executed in its target environment.

Examples: patch file created; migration script written; deployment manifest built but not deployed.

## EXECUTED

The action occurred in the target scope.

Required evidence: tool/action result, file/repository state, command result, API result, or equivalent execution trace.

## VERIFIED

Independent or subsequent evidence confirms the executed state/check outcome.

Required evidence must bind to the relevant final artifact/version/state.

## VALIDATED

All mandatory acceptance conditions for the operation/scenario are satisfied.

`VALIDATED` is stronger than `VERIFIED`; a technically correct artifact can be verified without satisfying every acceptance criterion.

## Negative terminal classifications

When useful, distinguish:

- `BLOCKED`: missing authority, capability, identity, or evidence prevents safe continuation.
- `CONFLICT`: current state/instructions contain an incompatible or unexpected competing condition.
- `FAILED`: an executed acceptance check ran and did not pass.

Do not use `FAILED` for checks that never ran.
