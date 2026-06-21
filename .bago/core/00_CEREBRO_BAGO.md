# 00_CEREBRO_BAGO

## Definición

BAGO organiza el trabajo técnico en cuatro modos:

### [B] Balanceado

Clarifica objetivo, alcance, restricciones, riesgos y criterio de éxito.

### [A] Adaptativo

Elige estrategia y secuencia realistas según el estado real del repositorio.

### [G] Generativo

Produce artefactos útiles: código, tests, docs, scripts, configuraciones, planes técnicos.

### [O] Organizativo

Ordena, empaqueta, actualiza estado y deja continuidad.

## Reglas maestras

- No generar antes de entender.
- No rediseñar por impulso.
- No cerrar sin dejar siguiente paso claro.
- No confundir documentación con progreso.
- Preferir cambios mínimos, claros y trazables.

## Módulos del sistema

| Módulo | Ruta | Rol |
|--------|------|-----|
| Canon | `core/canon/` | Normas del sistema — fuente de verdad normativa |
| Workflows | `core/workflows/` | Protocolos de ejecución por tipo de tarea |
| Agents | `agents/` | Roles activables por workflow o tarea |
| State | `state/` | Estado vivo del sistema (sesiones, global_state) |
| Knowledge | `knowledge/` | Aprendizaje producido en proyectos reales — **mismo rango que canon/** |
| Tools | `tools/` | Herramientas ejecutables del sistema |

## Operaciones BAGO reconocidas

- **Sprint**: implementación de un cambio atómico en un proyecto. Ver `W2_IMPLEMENTACION_CONTROLADA`.
- **Audit**: revisión de estado vs. realidad del repo. Ver `W10_AUDITORIA_SINCERIDAD`.
- **Harvest (W9)**: captura de valor después de exploración libre.
- **Cross-learning**: transferencia de conocimiento entre proyectos. Ver `core/workflows/workflow_cross_learning.md`.
- **Cold start**: arranque desde cero en repositorio desconocido. Ver `W1_COLD_START`.

## Nota de actualización

_Última actualización: 2026-05-05 — módulo knowledge/ promovido a módulo core; cross-learning añadido como operación reconocida._
