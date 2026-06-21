# BAGO v4 Architecture

BAGO v4.7 is a session-first control plane. The stable product path is Python 3.11+ CLI, local API, optional React UI, contracts, and evidence. C++ stays experimental and cannot block distribution.

The stable MVP boundary is defined in `docs/MVP.md`. Modules outside that boundary must be documented as partial, experimental, or planned.

## Boundaries

| Scope | Path | Role |
|---|---|---|
| Source workspace | `C:\Bago_v4` | code, docs, tests, release assembly |
| Installed runtime | `C:\Program Files\BAGO` | installed executable surface |
| Mutable user state | `C:\ProgramData\BAGO\user` | sessions, credentials, runtime state |
| Advanced backend source | `C:\bago_true\.bago` | external engine source material |
| Advanced RL source | `C:\bago_true\.bago\rl` | external RL source material |

Release artifacts must not package live state, logs, credentials, caches, `node_modules`, or checkpoints.

## Runtime Layers

1. Launcher layer
   - `bago.cmd`, `bago.ps1`, `bago.sh`
   - `bago_core/cli.py`
   - `bago_core/launcher.py`

2. Core session layer
   - `.bago/core/session_manager.py`
   - `.bago/core/context_store.py`
   - `.bago/core/config_manager.py`
   - `.bago/core/credential_manager.py`

3. Provider layer
   - `.bago/core/provider_adapter.py`
   - `.bago/providers/ollama_local.py`
   - `.bago/providers/ollama_cloud.py`
   - `.bago/providers/copilot.py`
   - `.bago/providers/anthropic.py`
   - `.bago/providers/openrouter.py`
   - `.bago/providers/opencode.py`
   - `.bago/providers/cpp_local.py`

4. Control/API layer
   - `.bago/api/bridge.py`
   - `.bago/api/control_shadow.py`

5. Evidence and governance layer
   - `bago_core/evidence_bundle.py`
   - `bago_core/claim_ledger.py`
   - `bago_core/codegen/evidence_builder.py` (Code Forge 3B)
   - `docs/contracts/`

6. UI layer
   - `ui-react`
   - optional future `apps/mobile-expo`

7. Plan execution layer
   - `PLAN_VERTICE`
   - `PLAN_VERTICE/monitor`
   - `PLAN_VERTICE/skill-draft/bago-v4-executor`

8. Code Forge layer (BAGO 4.7)
   - `bago_core/codegen/task_classifier.py` — request → safe contract
   - `bago_core/codegen/task_compiler.py` — contract → execution plan
   - `bago_core/codegen/context_builder.py` — plan → staged file map
   - `bago_core/codegen/patch_parser.py` — raw output → unified-diff patches
   - `bago_core/codegen/repair_loop.py` — generate → validate → repair (≤3)
   - `bago_core/codegen/code_verdict.py` — repair verdict → final decision
   - `bago_core/codegen/evidence_builder.py` — verdict → audit bundle
   - `bago_core/validation/validation_pipeline.py` — language adapters + gates
   - `bago_core/validation/adapters/python_adapter.py` — Python gate stack
   - `bago_core/execution/atomic_patch.py` — apply patch atomically with snapshot

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

These bridges are current detection surfaces, not current execution authority:

- `bago engine status` for `C:\bago_true\.bago`.
- AppData/cmd-rl detection for migration and compatibility only.

Current RL shadow bridge:

- `bago rl status` and `bago rl shadow` for RL observation.
- `bago rl train bc` and `bago rl eval` for safe policy layer.
- `/rl/status` and `/rl/shadow` expose the same safe state to the local API/UI.

These bridges are still planned:

- canary/full RL execution remains future and gated.

## Current Distribution Shape

Included:

- Python runtime.
- contracts.
- evidence tooling.
- optional React UI build.
- launchers.
- docs.

Excluded:

- `.bago/state`.
- `.bago/logs`.
- credentials.
- `ui-react/node_modules`.
- C++ build requirement.
- checkpoints.

## Next Steps

1. Add release packaging scripts that enforce exclusions.
2. Add install/update smoke tests for `C:\Program Files\BAGO`.
3. Add policy quality metrics before canary.

