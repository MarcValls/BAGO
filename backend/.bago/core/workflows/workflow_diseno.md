# WORKFLOW · DISEÑO

## id

`workflow_design`

## Objetivo

Definir estructura, fronteras, contratos, árbol, estados y trade-offs antes de producir el artefacto final.

## Cuándo usarlo

- arquitectura,
- rediseño de pack,
- definición de roles,
- definición de contratos,
- reorganización de un árbol.

## Roles mínimos

- Orquestador
- Analista
- Arquitecto
- Validador

## Entradas

- objetivo de diseño,
- restricciones funcionales y canónicas,
- artefacto o estructura actual, si existe,
- tensiones, riesgos o deuda detectada en análisis previo.

## Fases

1. Marco y objetivo.
2. Análisis de cargas.
3. Propuesta estructural.
4. Evaluación de alternativas.
5. Consolidación.
6. Validación.

## Salidas

- arquitectura,
- árbol,
- contratos,
- decisión de implementación.

## Escalado

- a Auditor Canónico si aparecen conflictos entre fuentes de verdad o rutas dudosas,
- a Organizador si el diseño desemboca en reempaquetado o handoff estructurado,
- a workflow_execution cuando la estructura ya está suficientemente congelada.

## Incidencias típicas

- mezclar diseño con ejecución prematura,
- rediseñar sin límites claros,
- producir contratos ambiguos o incompatibles entre sí,
- cerrar sin decisión explícita de implementación o diferimiento.

## Criterio de cierre

El diseño solo cierra cuando:

- la estructura propuesta es comprensible y justificable,
- los trade-offs relevantes quedaron explicitados,
- existe decisión clara de implementar, iterar o descartar,
- la validación no detecta contradicción canónica evidente.
