# WORKFLOW · VALIDACIÓN

## id

`workflow_validation`

## Objetivo

Emitir juicio formal sobre un resultado producido.

## Cuándo usarlo

- cierre de una ejecución no trivial,
- revisión formal de un cambio sistémico,
- comprobación de coherencia de un artefacto antes de congelarlo o entregarlo.

## Roles mínimos

- Orquestador
- Validador

## Entradas

- alcance prometido,
- artefacto o resultado a validar,
- contratos, reglas o criterios de aceptación aplicables,
- contexto mínimo de la iteración que produjo el resultado.

## Fases

1. Leer alcance prometido.
2. Revisar completitud, coherencia y compatibilidad.
3. Clasificar resultado.
4. Recomendar cierre o iteración.

## Salidas

- GO,
- GO_WITH_RESERVATIONS,
- KO,
- hallazgos,
- acciones sugeridas.

## Escalado

- a Auditor Canónico si hay conflicto de rutas, fuentes de verdad o semántica,
- a Arquitecto si la validación revela un problema estructural y no solo de acabado,
- a una nueva iteración de análisis o ejecución según el tipo de hallazgo.

## Incidencias típicas

- validar contra un alcance implícito y no declarado,
- confundir juicio formal con opinión general,
- marcar GO cuando solo existe completitud parcial,
- no dejar acciones sugeridas cuando el resultado no cierra limpio.

## Criterio de cierre

La validación solo cierra cuando:

- el resultado queda clasificado con un estado de validación explícito,
- los hallazgos principales quedan documentados,
- se recomienda cierre o siguiente iteración,
- no queda ambigüedad sobre si el artefacto es utilizable.
