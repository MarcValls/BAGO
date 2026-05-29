# Prompts · BAGO

Este directorio (`\.bago\prompts\`) contiene los prompts canónicos del framework.

## Convención de numeración

| Rango | Propósito |
|-------|-----------|
| `00_*` | Bootstrap y arranque |
| `01_*` | Activación del maestro |
| `02_*` | Análisis de repo |
| `03_*` | Tareas de proyecto |
| `04_*` | Revisión evolutiva |
| `05_*` | Actualización de estado |
| `activar_*.md` | Prompts de activación de componentes (maestro, orquestador, workflow, migración, revisión canónica) |

## Contenido

### A. Prompts de activación canónica

- `activar_maestro.md`
- `activar_orquestador.md`
- `activar_workflow.md`
- `activar_revision_canonica.md`
- `activar_migracion_historial.md`

### B. Prompts repo-first reutilizables

- `00_BOOTSTRAP_PROYECTO.md`
- `01_ARRANQUE_MAESTRO.md`
- `02_ANALISIS_REPO.md`
- `03_TAREA_DE_PROYECTO.md`
- `04_REVISION_EVOLUTIVA.md`
- `05_ACTUALIZACION_ESTADO_BAGO.md`

## Orden recomendado en proyecto real

1. `00_BOOTSTRAP_PROYECTO.md`
2. `01_ARRANQUE_MAESTRO.md`
3. `02_ANALISIS_REPO.md`
4. `03_TAREA_DE_PROYECTO.md`
5. `05_ACTUALIZACION_ESTADO_BAGO.md`

Usa `04_REVISION_EVOLUTIVA.md` solo si hay señal real de deriva o incoherencia.

## Regla

Los prompts son **versionados implícitamente** por su nombre. No se modifican in-place; si evolucionan, se crea una nueva versión con sufijo `_v2`, `_v3`, etc.
