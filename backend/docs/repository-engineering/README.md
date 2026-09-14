# BAGO Repository Engineering

Status: **PROPOSED** — repository-local operational projection.

This directory adapts the candidate `repository.engineering v0.1.1` method to
BAGO. It governs how agents work on the existing repository tree; it does not
replace `backend/docs/ARCHITECTURE.md`, `backend/.bago`, `.gabo/copilot`, or
the repository's existing contracts.

## Operating boundary

- A feature change and a structural refactor are different operations.
- A module contract describes an existing logical boundary before any physical
  move is proposed.
- An agent may work inside an approved boundary and its public contracts.
- A new cross-module dependency, ownership transfer, public contract change or
  forbidden internal import produces `ARCHITECTURE_BOUNDARY_REQUIRED`.
- Codex, Copilot and delegated agents execute approved work; repository canon
  remains authoritative over agent preference.
- Evidence is tied to the exact baseline/change set. A successful build alone
  does not prove behavior preservation.

## Artifacts

| Artifact | Purpose |
|---|---|
| `CHANGE_UNIT.schema.json` | Machine-readable scope and evidence contract for one operation |
| `MODULE_CONTRACT.md` | Template for documenting a logical module boundary |
| `ARCHITECTURE_PRESSURE.md` | Multi-signal detector for modularization candidates |
| `REFACTOR_PROTOCOL.md` | Characterization, compatibility and behavior-preservation protocol |
| `CHANGE_UNIT.example.json` | Non-active prepared example showing the expected operation shape |

These artifacts are proposals until explicitly adopted by repository
governance. They must not be treated as permission to restructure the tree.

The example change unit is deliberately `PREPARED`; it is illustrative only
and does not claim that an operation was executed.
