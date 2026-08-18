---
agent: 'agent'
description: 'BAGO workpack: 08 security'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Seguridad y trust boundaries

Usa exclusivamente `bago-security-auditor` como auditor principal.

Haz threat modeling defensivo del repositorio autorizado.
Revisa subprocess/shell injection, path traversal, filesystem, escritura fuera de workspace, URLs, tokens,
GitHub credentials, secrets, logs, env, CORS, endpoints locales, Electron/IPC, privilegios, plugins/tools,
prompt injection, acciones de IA, confirmaciones y límites framework/proyecto/workspace.

Clasifica CRITICAL/HIGH/MEDIUM/LOW sin inflar severidades.
No ejecutes explotación ni acciones destructivas.
