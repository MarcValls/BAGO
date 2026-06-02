# BAGO Autonomous Execution Contract

Status: closed for review
Depends on: `docs/CENTRALIZATION_CONTRACT.md`, `docs/NODE_CONTROL_SPEC.md`

## Principle

BAGO may run with or without an interactive UI, but the execution contract stays the same.

The UI is optional.
Validation is mandatory.
Evidence is mandatory.
Policy is mandatory.

## Execution Modes

### Headless

Use when:

- running from CLI
- running in CI
- running from install scripts
- running with no UI available

Rules:

- no visual dependency
- no hidden background action
- every action must be printable and auditable
- every release action must pass validation first

### Interactive

Use when:

- the user opens the manager UI
- the user wants visual confirmation
- the user wants graph or matrix navigation

Rules:

- UI can request actions
- backend decides actions
- UI never becomes the authority
- command execution stays visible

## Validation Gates

### Preflight

Before any action:

- registry available
- policy available
- target resolved
- release resolved if applicable
- connector state known

### Action Gate

Before executing:

- action is allowed by policy
- target exists
- mode is compatible
- evidence slot is ready

### Postflight

After executing:

- evidence written
- state reloaded
- result reported
- failure path recorded

## Allowed Surfaces

### CLI

- `validate`
- `install`
- `uninstall`
- `connect`
- `disconnect`
- `shadow`
- `readonly`
- `overlay`
- `sync`
- `audit`

### UI

- dashboard
- installations
- pieces
- nodes
- matrix
- detail
- audit

### No-UI

- same commands through CLI or scripts
- same validation gates
- same evidence ledger

## Forbidden Behaviors

- execution without policy
- execution without evidence
- silent background mutation
- UI-only state changes
- release selection without explicit target
- connector changes without ledger entry

## Success Criteria

- the same action behaves the same with or without UI
- headless and interactive flows produce the same evidence shape
- validation catches invalid installs, invalid connectors, and invalid release targets

