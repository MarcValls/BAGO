# 03_ESTADO_BAGO

El estado BAGO es la fuente de verdad operativa resumida.

## Debe responder siempre

- Qué objetivo se está ejecutando.
- En qué modo BAGO está la sesión.
- Qué roles están activos.
- Qué restricciones siguen vigentes.
- Qué decisiones están congeladas.
- Qué se produjo ya.
- Qué sigue después.

## Separación de capas

BAGO mantiene tres capas de estado con responsabilidades estrictamente separadas:

| Archivo | Capa | Responsabilidad |
|---|---|---|
| `state/global_state.json` | Canónica | Fuente de verdad estructural: inventario, referencias finales, sesión activa, validaciones, sprint_status del pack. **Manda sobre cualquier otro archivo en caso de conflicto.** |
| `state/ESTADO_BAGO_ACTUAL.md` | Snapshot legible | Resumen humano del estado del pack. Debe ser consistente con global_state.json. No describe sprints del repo externo como objetivo activo del pack. |
| `state/repo_context.json` | Puntero externo | Solo registra el fingerprint y ruta del repo externo intervenido. **No contiene progreso funcional ni estado canónico del pack.** Incluye `working_mode`: `"self"` cuando BAGO opera en su propio directorio host, `"external"` cuando opera sobre un proyecto distinto. |

**Regla de no-contaminación:** los sprints o tareas del repositorio externo no deben reescribir el estado estructural del pack. Si un sprint del producto se registra, debe hacerlo como sesión/cambio/evidencia en sus directorios propios, no sobreescribiendo los punteros de `global_state.json`.

## Regla

Si el estado y el repo divergen, no inventar una tercera realidad: reconciliar explícitamente.
