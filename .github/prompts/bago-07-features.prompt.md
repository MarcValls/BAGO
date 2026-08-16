---
agent: 'agent'
description: 'BAGO workpack: 07 features'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Agents, Interpreter y GitHub

Usa `bago-architecture-auditor`; para contratos concretos puede usar `bago-contracts-auditor`.

Audita en profundidad:

AGENTS: CRUD, modelo, validación, persistencia, IDs, concurrencia, test, UI/backend.
INTERPRETER: pipeline real, etapas simuladas, inputs/outputs, trazabilidad, errores, evidencia y visualización.
GITHUB: auth status, gh CLI, OAuth/device flow, tokens, refresh, logout, setup, repos, errores, exposición de secretos y runtime local.

Para cada capacidad indica PREPARED, EXECUTABLE, EXECUTED, VERIFIED o NO VERIFICADO, explicando la evidencia.
