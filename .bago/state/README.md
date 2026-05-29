# Estado estructurado · BAGO

Este directorio (`\.bago\state\`) contiene todo el estado mutable del framework: sesiones, contratos, evidencias, sprints, skills y más.

## Subdirectorios

| Directorio | Contenido | Placeholder / Ejemplo |
|------------|-----------|----------------------|
| `agents/` | Estado de agentes personalizados | — |
| `boot/` | Estado de arranque y bootstrap | — |
| `changes/` | Cambios estructurados registrados | `CHG-000.json.example` |
| `config/` | Configuración del framework | — |
| `contracts/` | Contratos operativos verificables | `CONTRACT-000.json.example` + `README.md` |
| `evidences/` | Evidencias de decisión, validación, incidencia | `EVIDENCE-000.json.example` |
| `field/` | Estado del campo de trabajo actual | — |
| `goals/` | Objetivos activos y cerrados | — |
| `orchestrator/` | Estado del orquestador central | — |
| `peers/` | Vinculaciones con otros proyectos BAGO | — |
| `reactor/` | Estado del reactor de eventos | — |
| `research/` | Resultados de investigaciones en curso | — |
| `sac_locks/` | Locks del SAC (Sistema de Auto-Coherencia) | — |
| `sessions/` | Sesiones ejecutadas (cierres, logs) | `SESSION_CLOSE_*.md` |
| `skills/` | Skills registrados y su estado | — |
| `sprints/` | Sprints de desarrollo | `SPRINT-*.json` |
| `toolboxes/` | Cajas de herramientas por proyecto | — |

## Regla

Todo archivo en este árbol es generado o modificado por el framework o por el usuario a través de comandos canónicos (`bago *`). No se editan manualmente salvo indicación explícita del contrato de cambio.
