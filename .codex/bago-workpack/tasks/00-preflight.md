# Fijar objeto auditado

Usa el agente personalizado `bago_repo_explorer`.

Objetivo: fijar exactamente el objeto auditado antes de cualquier conclusión.

Comprueba:
- raíz git, remoto/s, rama y commit HEAD;
- git status y cambios locales;
- versión o versiones declaradas;
- package managers y runtimes;
- frontend, backend, Electron u otros shells;
- scripts de build/typecheck/test;
- workflows CI;
- archivos de instrucciones AGENTS.md activos o equivalentes.

No modifiques nada.

Entrega:
1. Identidad del repositorio.
2. Commit fijado.
3. Estado git.
4. Versiones declaradas y contradicciones.
5. Stack/runtime detectado.
6. Gates oficiales detectados.
7. Riesgos para la reproducibilidad de la auditoría.
