# BAGO 4.8 Live Surfaces

This runtime snapshot validates only surfaces that have an active execution path.

## Live

- Installation roles: `bago_core/install_roles.py`, `bago.ps1 roles`, and Electron preload role helpers.
- Local HTTP API: `.bago/api/bridge.py` with `/session`, `/status`, `/menu`, and `/command`.
- Command execution safety: `bago_core/execution/process_runner.py`.
- UI runtime: `ui-react/dist` served by the local BAGO API server, backed by `ui-react/src/app/ControlPlane.tsx`.
- Launch wrappers: `bago`, `bago.cmd`, `bago.ps1`, and `bago.sh`.

## Retired In This Runtime Snapshot

- `.bago/roles`: replaced by installation-role selection in `bago_core/install_roles.py`.
- `.bago/mcp`: no active MCP server is wired in this runtime snapshot; the HTTP API is the live integration surface.
- `.bago/extensions/bash-runner`: no active extension runner is wired in this runtime snapshot; process execution goes through `ProcessRunner`.
- `.github/workflows`: source repository concern. This runtime tree does not ship CI workflows.
