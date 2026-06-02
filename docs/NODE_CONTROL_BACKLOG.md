# BAGO Node Control - Technical Backlog

Status: ready for implementation
Depends on: `docs/NODE_CONTROL_SPEC.md`

## Goal

Turn the closed contract into an implementable system:

- one shared PieceStore
- many BAGO runtimes
- connector nodes as the control surface
- explicit evidence for every state change
- stable release selection from GitHub
- separate graph and matrix views

## Phase 1 - Canonical Data Model

Deliverables:

- define `Installation`, `Piece`, `Node`, `Connector`, `Policy`, `Release`, `Evidence`
- add canonical IDs and normalized statuses
- define state transitions for connectors
- define piece identity and hash rules

Exit criteria:

- one data model is used by UI, commands, and evidence
- no screen or command invents its own connector state

Evidence:

- model dump or schema snapshot
- validation command output

## Phase 2 - Shared PieceStore

Deliverables:

- implement the shared store root at `C:\ProgramData\BAGO\pieces\`
- add inventory for `tools`, `agents`, `skills`, `repos`, `knowledge`, `models`, `connectors`, `blobs`, `cache`
- add install discovery without duplication
- add overlay support for local writable layers

Exit criteria:

- one physical piece can be referenced by multiple installations
- no installation owns a private duplicate unless overlay is explicitly enabled

Evidence:

- store inventory
- dedupe report
- installation discovery report

## Phase 3 - Connector Registry

Deliverables:

- create connector records for `installation_id + piece_id`
- support `connected`, `shadow`, `locked`, `detached`, `read-only`, `writable overlay`
- support connector policy fields: `can_execute`, `can_modify`, `sync_mode`, `visibility`
- persist connector state changes

Exit criteria:

- the same piece can behave differently per installation
- every connector has a stable history

Evidence:

- connector list
- connector state transition log

## Phase 4 - Release Source Of Truth

Deliverables:

- list GitHub releases automatically
- mark prereleases as `beta`
- sort latest stable as default
- allow explicit release selection
- expose update/install-apart/uninstall paths

Exit criteria:

- no manual paste is required to discover releases
- the latest stable is selected by default
- prereleases remain visible and selectable

Evidence:

- release fetch log
- selected release record
- install target resolution output

## Phase 5 - Real Commands

Deliverables:

- wire real commands for `connect`, `disconnect`, `lock`, `shadow`, `readonly`, `overlay`
- wire `sync`, `install`, `uninstall`, `audit`
- keep visible PowerShell for execution commands
- keep web surface copy-only where execution is not available

Exit criteria:

- every button maps to a real command or a real API action
- command invocation is visible and traceable

Evidence:

- command transcript
- before/after state snapshot

## Phase 6 - Evidence Pipeline

Deliverables:

- emit evidence for every state change
- store actor/session, target, version/hash, result, timestamp
- make evidence exportable as a bundle

Exit criteria:

- every connector change produces evidence
- evidence can be exported and reviewed later

Evidence:

- evidence bundle
- per-action audit record

## Phase 7 - UI Surface

Deliverables:

- `Dashboard`
- `Installations`
- `Pieces`
- `Nodes`
- `Matrix`
- `Detail`
- `Audit`

UI rules:

- `Nodes` gets its own graph view
- `Matrix` shows `Installation x Piece`
- `Detail` focuses one installation, piece, or connector
- `Audit` shows evidence only

Exit criteria:

- graph and matrix can be viewed separately
- UI never becomes the authority of the runtime

Evidence:

- rendered screens
- interaction screenshots

## Phase 8 - Safety And Uninstall

Deliverables:

- safe uninstall by installation
- optional purge for local runtime data only
- no accidental deletion of shared pieces
- lock down non-local exposure and token requirements

Exit criteria:

- uninstall does not break other installations
- shared pieces remain intact unless explicitly purged

Evidence:

- uninstall log
- preserved PieceStore inventory

## Phase 9 - Tests And Release Gate

Deliverables:

- real install/update/uninstall tests
- connector state tests
- release selection tests
- evidence tests
- clean package validation

Exit criteria:

- the backlog is proven on a clean target
- release packaging does not include live state or credentials

Evidence:

- test results
- package manifest
- release artifact checksums

## Implementation Order

1. Data model
2. Shared PieceStore
3. Connector registry
4. Release source of truth
5. Real commands
6. Evidence pipeline
7. UI surface
8. Safety and uninstall
9. Tests and release gate

## Non-Goals

- no autonomous agent execution
- no hidden background mutation
- no duplication of shared pieces per installation
- no UI-only source of truth

