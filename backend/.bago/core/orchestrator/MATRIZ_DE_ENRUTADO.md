# MATRIZ DE ENRUTADO · BAGO AMTEC línea canónica previa CORREGIDO

| Tipo de tarea     |     Riesgo | Workflow                   | Roles mínimos                                      | Escalado típico         |
| ----------------- | ---------: | -------------------------- | -------------------------------------------------- | ----------------------- |
| analysis          |       bajo | workflow_analysis          | Orquestador, Analista, Validador                   | Arquitecto              |
| design            |      medio | workflow_design            | Orquestador, Analista, Arquitecto, Validador       | Auditor Canónico        |
| execution         |       bajo | workflow_execution         | Orquestador, Generador, Validador                  | Organizador             |
| execution         |       alto | workflow_execution         | Orquestador, Arquitecto, Generador, Validador      | Auditor Canónico        |
| validation        |       bajo | workflow_validation        | Orquestador, Validador                             | Auditor Canónico        |
| organization      |       bajo | workflow_execution         | Orquestador, Organizador, Validador                | Arquitecto              |
| system_change     |       alto | workflow_system_change     | Orquestador, Auditor Canónico, Validador           | Arquitecto, Vértice     |
| history_migration | medio/alto | workflow_history_migration | Orquestador, Analista, Auditor Canónico, Validador | Arquitecto, Organizador |

## Observación

`history_migration` no equivale a “documentación”. Es una tarea híbrida entre análisis, transformación y trazabilidad.

## Extensión V2.2.1 · Ruta repo-first

| Tipo de tarea     | Riesgo | Workflow                      | Roles mínimos                                              | Escalado frecuente |
| ----------------- | -----: | ----------------------------- | ---------------------------------------------------------- | ------------------ |
| project_bootstrap |  medio | workflow_bootstrap_repo_first | ADAPTADOR_PROYECTO, INICIADOR_MAESTRO, ORQUESTADOR_CENTRAL | Analista           |
