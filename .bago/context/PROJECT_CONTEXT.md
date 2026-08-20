# BAGO Project Context

- **Name:** BAGO
- **Version:** 4.9.0
- **Purpose:** Local AI control plane. The session is the source of truth; providers and models are interchangeable execution engines.
- **Repository root:** `<repo>`
- **Main branch:** `main`

## Monorepo layout

- `backend/` — Python runtime (core, CLI, local API, contracts). Tests: pytest.
- `frontend/` — React + TypeScript (Vite) control-plane UI.
- `electron-viewer/` — Electron shell with automatic backend lifecycle.
- `.bago/` — Working-tree runtime state, context, decisions, conflicts, and handoffs.

## Current gates (evidence-backed)

- Backend test suite: 928 passed, 13 skipped.
- Frontend typecheck, tests, and production build pass.
- Windows is the primary supported platform; macOS/Linux are experimental.

## Recent closure

1. `feat(frontend): chat acoplado como panel lateral combinado con cualquier pantalla`
2. `test(backend): decodifica stdout de PowerShell según la code page de consola`
3. `infra(runtime): initialize BAGO working-tree runtime wrapper and persistent state`
