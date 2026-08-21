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
4. `hygiene: remove unused imports and stale alias comment`
5. `docs(agents): add project-local agent context and Pi skills`
6. `chore(gitignore): ignore electron-viewer generated logs`
7. `fix(frontend): evita cierre obsoleto en el atajo de chat acoplado y añade tests de layout`
8. `fix(frontend): ensure full-screen chat always owns the workspace area`
9. `fix(frontend): prevent side panels from sharing the screen on startup`
10. `fix(frontend): update HelpOverlay copy for chat-dock behavior`
13. `chore(repo): normalize all text files to UTF-8 LF via .gitattributes`
14. `feat(frontend): actionable runtime status and improved empty states on home`
15. `chore(bago): add backend verification helper script`
16. `fix(electron-viewer): prevent EPIPE crash and auto-start local backend in dev mode`
17. `fix(frontend): enforce fullscreen for sidebar panels; only chat may split the screen`

Working tree is clean. Backend: 928 passed / 13 skipped. Frontend: 121 tests passed / typecheck OK / build OK. Open conflicts: none.
