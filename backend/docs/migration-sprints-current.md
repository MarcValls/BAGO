# BAGO Migration Sprint Contract

Status: completed
Depends on: `BAGO_MIGRATE_TARGET.md`
Applies to: `C:\Users\AMTEC_Terminal_1º\bago_fw`

This contract records the current-tree migration slices that are already reflected in the active system.

## Sprint Map

| Sprint | Rows | Focus | Status |
|---|---|---|---|
| 0 | 8 | Freeze truth and block snapshot leakage | done |
| 1 | 1, 18, 19, 22 | Entrypoints and runtime selection | done |
| 2 | 2, 3, 4, 5, 20, 25 | Layout, registry, workflows, state, manifest | done |
| 3 | 6, 7, 9, 10, 11, 12, 13, 15, 16 | Knowledge, recovered assets, and contracts | done |
| 4 | 8, 14, 17, 21, 23, 24 | Cleanup, external surfaces, and CI gates | done |
| 5 | final | Validation, sync, and release proof | done |

## Sprint 0

Freeze truth and block snapshot leakage.

## Sprint 1

Entrypoints and runtime selection.

## Sprint 2

Layout, registry, workflows, state, manifest.

## Sprint 3

Knowledge, recovered assets, and contracts.

## Sprint 4

Cleanup, external surfaces, and CI gates.

## Sprint 5

Validation, sync, and release proof.

## Row Groups

1, 18, 19, 22
2, 3, 4, 5, 20, 25
6, 7, 9, 10, 11, 12, 13, 15, 16
8, 14, 17, 21, 23, 24

## Sprint 1 Files

- `.bago/BOOTSTRAP.md`
- `.bago/AGENT_START.md`
- `.bago/START_AGENT.md`
- `bago.ps1`
- `electron/environment.cjs`
- `electron/runtime-service.cjs`
- `tests/test_system_prompt_bootstrap.py`
- `tests/test_no_visible_powershell.py`

## Notes

- The migration rows are retained as current-tree evidence.
- Snapshot-only notes stay out of the active contract surface.
