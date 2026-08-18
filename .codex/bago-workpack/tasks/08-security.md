# Seguridad y trust boundaries

Usa exclusivamente `bago_security_auditor` como auditor principal.

Haz threat modeling defensivo del repositorio autorizado.
Revisa subprocess/shell injection, path traversal, filesystem, escritura fuera de workspace, URLs, tokens,
GitHub credentials, secrets, logs, env, CORS, endpoints locales, Electron/IPC, privilegios, plugins/tools,
prompt injection, acciones de IA, confirmaciones y límites framework/proyecto/workspace.

Clasifica CRITICAL/HIGH/MEDIUM/LOW sin inflar severidades.
No ejecutes explotación ni acciones destructivas.
