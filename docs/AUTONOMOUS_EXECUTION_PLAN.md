# BAGO Autonomous Execution Plan

Status: ready for implementation
Depends on: `docs/AUTONOMOUS_EXECUTION_CONTRACT.md`

## Phase 1 - Preflight Registry

Deliverables:

- registry presence checks
- installation target resolution
- release target resolution
- connector target resolution

Exit criteria:

- headless and interactive flows resolve the same targets

Evidence:

- preflight report

## Phase 2 - Policy Gate

Deliverables:

- action permission checks
- mode compatibility checks
- stable vs beta visibility checks
- connect/disconnect permission checks

Exit criteria:

- invalid actions are denied before execution

Evidence:

- allow/deny decision log

## Phase 3 - Evidence Gate

Deliverables:

- evidence record creation
- action result capture
- before/after state snapshot
- bundle export support

Exit criteria:

- every successful or failed action leaves a record

Evidence:

- evidence ledger entries

## Phase 4 - Headless Execution

Deliverables:

- CLI-first execution path
- scripted install/update/uninstall path
- visible validation output

Exit criteria:

- the system works with no UI present

Evidence:

- command transcript
- validation output

## Phase 5 - Interactive Execution

Deliverables:

- UI action dispatch
- graph and matrix actions
- detail-panel action execution
- visible command launch on execution actions

Exit criteria:

- UI actions produce the same backend result as headless commands

Evidence:

- UI interaction log
- matching backend transcript

## Phase 6 - Cross-Mode Validation

Deliverables:

- compare headless vs interactive results
- compare validation outputs
- compare evidence shape

Exit criteria:

- no drift between modes

Evidence:

- parity report

## Implementation Order

1. Preflight registry
2. Policy gate
3. Evidence gate
4. Headless execution
5. Interactive execution
6. Cross-mode validation

