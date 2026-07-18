# BAGO v4 Architecture

This document captures the structural architecture of BAGO v4.
Operational state, live surfaces, and UI authority live in `docs/SYSTEM_OVERVIEW.md`, `docs/LIVE_SURFACES.md`, and `docs/UI_CANONICAL_CONTRACT.md`.

BAGO v4.8.0 is a session-first control plane.
Product boundary lives in `docs/MVP.md`.

## Authority Model

- The editable workspace is the current source tree for development.
- The installed runtime is a separate release target.
- The React shell is a presentation surface only.
- Backend-confirmed state is authoritative.
- Evidence and contracts define what can be claimed as working.
- UI behavior is defined elsewhere in the UI contract.

## Boundaries

| Scope | Path | Role |
|---|---|---|
| Source workspace | workspace resolved by `.bago\pack.json` | code, docs, tests, release assembly |
| Installed runtime | `C:\Program Files\BAGO` | installed executable surface |
| Mutable user state | `C:\ProgramData\BAGO\user` | sessions, credentials, runtime state |
| Advanced backend source | `C:\bago_true\.bago` | external engine source material |
| Advanced RL source | `C:\bago_true\.bago\rl` | external RL source material |

Release artifacts must not package live state, logs, credentials, caches, `node_modules`, or checkpoints.

## Runtime Layers

1. Launcher layer
   - See `docs/MODULES.md` for the current launcher and CLI inventory.

2. Core session layer
   - See `docs/MODULES.md` for the current session/control inventory.

3. Provider layer
   - See `docs/MODULES.md` for the current provider inventory.

4. Control/API layer
   - See `docs/MODULES.md` for the current control/API inventory.

5. Evidence and governance layer
   - Evidence and claim authorities live in `docs/CLAIMS.md`, `docs/TRACEABILITY.md`, and the evidence bundle docs.

6. UI layer
   - UI authority lives in `docs/UI_CANONICAL_CONTRACT.md` and the visual grammar/review docs.

7. Plan execution layer
   - Plan execution remains evidence-only and is documented separately from runtime modules.

8. Code Forge layer (BAGO 4.8.0)
   - See the codegen and validation modules in `docs/MODULES.md`.

## Primary Data Flow

```text
user
  -> launcher / CLI
  -> session manager
  -> provider adapter
  -> context store + evidence
  -> optional API/UI surfaces
```

Provider switching is handled by the switch engine and must preserve session context when possible.

## API Flow

```text
ui-react
  -> local HTTP API
  -> session/provider/control shadow
  -> response, status, events
```

The API must default to local access. Non-localhost exposure requires explicit token protection.

## Planned External Bridges

These bridges are detection or shadow surfaces, not execution authority:

- `bago engine status` for `C:\bago_true\.bago`
- AppData/cmd-rl detection for migration and compatibility only
- `bago rl status` and `bago rl shadow` for RL observation
- `bago rl train bc` and `bago rl eval` for the safe policy layer
- `/rl/status` and `/rl/shadow` expose the same safe state to the local API/UI
- canary/full RL execution remains future and gated

## Structural Notes

- Distribution rules live in `docs/DISTRIBUTION_CONTRACT.md`.
- Runtime eligibility and MVP bounds live in `docs/MVP.md`.
- Live operational inventory lives in `docs/LIVE_SURFACES.md`.
