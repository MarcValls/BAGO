---
agent: 'agent'
description: 'BAGO workpack: 03 frontend'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Frontend completo

Usa `bago-frontend-auditor`.

Audita ControlPlane, shell, navegación, sidebar, top bar, inspector, drawers, modales, command palette,
shortcuts, Workspace, Agents, Interpreter, GitHub, Providers, Models, Router, Tools, Capabilities, Pipeline,
contexto, chat, historial, evidencia, jobs y cualquier sección adicional.

Para cada feature: entrypoint, propietario de estado, componentes, hooks, API, backend, persistencia, tests,
loading/error/empty, rutas de error, UI huérfana y backend sin UI.

Busca específicamente estado duplicado, effects fuera de scope, listeners duplicados, sistemas de drawers paralelos,
shortcuts inconsistentes, componentes montados varias veces, fetches redundantes, race conditions y estado derivado innecesario.
