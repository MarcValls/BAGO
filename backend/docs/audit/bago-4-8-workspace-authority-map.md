# BAGO 4.8 workspace authority map

## Canonical separation

- `framework_root`: active BAGO installation root.
- `project_root`: user project checkout.
- `workspace_state_root`: canonical workspace state root at `project_root/.gabo`.

## Current authority paths

### Detection

- `bago_core/workspace_binding.py` resolves framework, project, and
  workspace-state roots.
- It reads `project_root/.gabo/workspace.json` as the canonical identity file.

### Workspace lifecycle

- `.bago/tools/project_memory.py` still owns `init_project`, `link_project`,
  `status_data`, and `seed_project`.
- That module still creates legacy `.bago` artifacts such as `pack.json`,
  `state/context.json`, `state/tasks.json`, `knowledge/manifest.json`, and
  `link.json`.

### Backend permissions

- `.bago/api/handlers_workspace.py` still derives `canChat`,
  `canInitializeWorkspace`, `canLinkWorkspace`, `canRepairWorkspace`, and
  `canSeedWorkspace` from the current status payload.
- `canChat` still allows `binding_confirmed OR project_root`, which is the
  exact over-permissive path the plan targets.

### UI consumption

- `frontend/src/app/ControlPlane.tsx` consumes backend snapshots for
  permissions, but the backend snapshot still exposes legacy workspace fields
  and recommendation arrays.

## Conclusion

The current codebase already has the right conceptual split, but the runtime
still uses legacy `.bago` writes and permissive permission derivation. The plan
should therefore start by fixing evidence and authority wiring, not by adding a
second workspace system.

