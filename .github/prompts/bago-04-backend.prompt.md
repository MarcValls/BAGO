---
agent: 'agent'
description: 'BAGO workpack: 04 backend'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Backend completo

Usa `bago-backend-auditor`.

Audita entrypoints, dispatch, rutas, handlers, validación, servicios, persistencia, filesystem, subprocess,
GitHub, Agents, Interpreter, providers, modelos, router, tools, jobs, scheduler, evidence, state, workspace,
context y configuración.

Para cada familia de endpoints determina método, ruta, handler, input, validación, output, errores,
persistencia, efectos laterales, consumidores y tests.

Detecta endpoints muertos, rutas duplicadas, divergencias, errores silenciosos, JSON sin schema,
persistencia no atómica, concurrencia y trust boundaries.
