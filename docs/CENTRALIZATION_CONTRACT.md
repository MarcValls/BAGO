# BAGO Centralization Contract

Status: closed for review
Depends on: `docs/NODE_CONTROL_SPEC.md`

## Principle

BAGO centralizes control, not runtime state.

Centralize:

- installation registry
- shared PieceStore
- connector graph
- policy decisions
- release index
- evidence ledger
- compatibility matrix

Keep local per installation:

- session state
- user runtime config
- local cache
- logs
- credentials
- overlays

Do not centralize:

- live session memory
- transient execution state
- secrets
- per-install logs
- per-install caches

## Centralized Components

### Installation Registry

Source of truth for:

- `installation_id`
- path
- version
- state
- policy
- last sync
- uninstall status

### Policy Engine

Decides:

- connect or deny
- execute or shadow
- read-only or overlay
- stable or beta visibility
- version pinning

### Evidence Ledger

Records:

- action
- target
- before state
- after state
- version or hash
- timestamp
- actor or session
- result code

### Compatibility Matrix

Maps:

- installation version
- piece version
- connector mode
- release tag
- prerelease flag
- execution permission

## Boundary Rules

- No installation may own the shared piece by default.
- No connector may change state without evidence.
- No release may be installed without an explicit target.
- No UI may become the authority over policy.
- No shared piece may be duplicated unless overlay is explicit.

## Verification

Minimum checks:

- registry lists all installations
- policy engine resolves each connector decision
- evidence ledger receives every state change
- compatibility matrix blocks invalid version mixes

