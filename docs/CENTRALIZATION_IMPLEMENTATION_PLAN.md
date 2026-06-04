# BAGO Centralization Implementation Plan

Status: ready for implementation
Depends on: `docs/CENTRALIZATION_CONTRACT.md`

## Phase 1 - Registry First

Deliverables:

- canonical installation registry
- installation discovery
- last sync metadata
- uninstall state tracking

Exit criteria:

- every runtime installation is visible in one registry

Evidence:

- registry snapshot
- discovery command output

## Phase 2 - Policy Engine

Deliverables:

- connector decision engine
- connector mode transitions
- stable/beta visibility rules
- execution permission rules

Exit criteria:

- every connector decision comes from policy, not UI guesswork

Evidence:

- decision log
- state transition log

## Phase 3 - Evidence Ledger

Deliverables:

- append-only evidence records
- query by installation, piece, action, timestamp
- exportable evidence bundle

Exit criteria:

- every connector change writes evidence before completion

Evidence:

- ledger entries
- bundle export

## Phase 4 - Compatibility Matrix

Deliverables:

- version compatibility table
- prerelease gating
- execution matrix per installation and piece

Exit criteria:

- invalid version combinations are blocked before execution

Evidence:

- matrix snapshot
- rejected invalid combination report

## Phase 5 - PieceStore and Connectors

Deliverables:

- shared PieceStore root
- connector registry persistence
- install/disconnect/sync actions

Exit criteria:

- one piece can serve multiple installations with different policies

Evidence:

- dedupe report
- connector audit trail

## Phase 6 - UI Wiring

Deliverables:

- dashboard
- installations view
- pieces view
- nodes graph
- matrix view
- detail panel
- audit view

Exit criteria:

- UI renders the contract without inventing new state

Evidence:

- screenshots
- interaction logs

## Phase 7 - Release and Uninstall

Deliverables:

- stable latest install target
- beta prerelease listing
- install separate copy
- uninstall by installation

Exit criteria:

- release selection and uninstall are both explicit and auditable

Evidence:

- release selection log
- uninstall log

## Implementation Order

1. Registry
2. Policy engine
3. Evidence ledger
4. Compatibility matrix
5. PieceStore and connectors
6. UI wiring
7. Release and uninstall

