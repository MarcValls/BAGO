# CONTRATO DE WORKFLOW · BAGO AMTEC línea canónica previa CORREGIDO

## Objeto

Regular la forma mínima de todo workflow.

## Campos obligatorios

- id
- objetivo
- cuándo usarlo
- roles mínimos
- entradas
- fases
- salidas
- escalado
- incidencia típica
- criterio de cierre

## Estado de cumplimiento (INC-001)

Los workflows canónicos en `.bago/core/workflows/` se migran progresivamente a
este contrato. Estado actual:

| Workflow | Campos presentes / 10 | Faltantes |
|----------|----------------------|-----------|
| workflow_analisis.md | 9/10 | escalado |
| workflow_bootstrap_repo_first.md | 6/10 | salidas, escalado, incidencia típica, criterio de cierre |
| workflow_cambio_sistemico.md | 8/10 | incidencia típica, criterio de cierre |
| workflow_cross_learning.md | ~3/10 | formato legado, no sigue estructura canónica |
| workflow_diseno.md | 9/10 | criterio de cierre |
| workflow_ejecucion.md | 8/10 | escalado, incidencia típica |
| workflow_migracion_historial.md | 8/10 | escalado, criterio de cierre |
| workflow_validacion.md | 10/10 | ✅ completo |

**Regla:** Todo workflow NUEVO debe cumplir los 10 campos. Los workflows
existentes se actualizarán en la medida de lo posible sin romper referencias
externas.

## Reglas

1. Debe ser ejecutable como ruta conceptual clara.
2. Debe terminar en un estado comprensible.
3. Debe decir qué hacer si se bloquea.
4. Si toca migración o preservación histórica, debe distinguir entre:
   - transformación actual,
   - referencia a material legado.

## Regla de cierre

El cierre no puede limitarse a "listo". Debe indicar:

- resultado,
- reservas,
- rastro.
