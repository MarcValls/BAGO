---
agent: 'agent'
description: 'BAGO workpack: 14 refactor plan'
---

Use the repository-level BAGO Copilot instructions. Use `repository-engineering` when the task includes repository state/change/verification and `bago-core` for lifecycle/evidence.

# Plan de corrección por PR

Usa `bago-refactor-planner`.

Lee la síntesis integral del MISMO RunId y los informes que la sustentan.
Produce un plan incremental por PR.

Para cada PR:
OBJETIVO
PRIORIDAD P0/P1/P2/P3/P4
HALLAZGOS QUE CIERRA
ARCHIVOS AFECTADOS
CAMBIO
RIESGO
DEPENDENCIAS
TESTS NECESARIOS
CRITERIO DE CIERRE
ROLLBACK
ESTADO INICIAL

Termina con TOP 10 acciones en orden.
No modifiques BAGO.
