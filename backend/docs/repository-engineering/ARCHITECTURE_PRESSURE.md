# Architecture Pressure Signals

Status: **PROPOSED**. This is an advisory detector, not an automatic mandate
to split files or move directories.

## Signals

Record a signal only when it is supported by repository evidence:

- `FILE_GROWTH`
- `RESPONSIBILITY_GROWTH`
- `DEPENDENCY_FAN_OUT`
- `DEPENDENCY_FAN_IN`
- `CIRCULAR_DEPENDENCY`
- `CROSS_MODULE_INTERNAL_IMPORT`
- `PUBLIC_API_GROWTH`
- `CHANGE_COUPLING`
- `HIGH_CHURN_AREA`
- `DUPLICATED_RESPONSIBILITY`
- `STATE_OWNERSHIP_AMBIGUITY`
- `GOD_SERVICE`
- `GOD_COMPONENT`

## Decision rule

One signal is an observation. A modularization candidate requires at least two
correlated signals plus one concrete consequence such as difficult testing,
unbounded change scope, duplicated authority, or a forbidden dependency.

```text
signals + consequence
    -> MODULARIZATION_CANDIDATE
    -> repo.plan_change(operation=modularize)
    -> characterization tests
    -> approved boundary
```

The detector must not block ordinary work solely because a file exceeds a line
threshold. Size is evidence for inspection, not a modularization verdict.

## Required finding fields

Each candidate records:

- signal IDs and measured evidence;
- affected module/files;
- current owner of state and public contracts;
- observed consequence;
- proposed boundary;
- behavior-preservation tests;
- dependencies that require escalation;
- whether the candidate is `PROPOSED`, `PREPARED`, `BLOCKED` or `CONFLICT`.
