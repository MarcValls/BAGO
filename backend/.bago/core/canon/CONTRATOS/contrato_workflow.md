# CONTRATO DE WORKFLOW · BAGO AMTEC línea canónica previa CORREGIDO

> LEGADO PRESERVADO.
> No es la fuente de verdad operativa actual.
> La referencia vigente para pipeline y transición de estados vive en `docs/contracts/bago_v4_pipeline_contract.md`.

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

## Reglas

1. Debe ser ejecutable como ruta conceptual clara.
2. Debe terminar en un estado comprensible.
3. Debe decir qué hacer si se bloquea.
4. Si toca migración o preservación histórica, debe distinguir entre:
   - transformación actual,
   - referencia a material legado.

## Regla de cierre

El cierre no puede limitarse a “listo”. Debe indicar:

- resultado,
- reservas,
- rastro.
