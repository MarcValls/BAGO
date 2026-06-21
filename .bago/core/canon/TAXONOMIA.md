# TAXONOMÍA · BAGO AMTEC línea canónica previa CORREGIDO

## Objetivo

Estabilizar el vocabulario operativo del sistema y su relación con la migración histórica. En esta edición, además de nombrar entidades, la taxonomía normaliza familias y estados para facilitar validación.

## Entidades

- **sesión**: unidad de trabajo acotada con objetivo y cierre.
- **tarea**: encargo concreto dentro de una sesión.
- **workflow**: ruta declarativa con fases y cierre.
- **rol**: capacidad funcional con fronteras definidas.
- **cambio**: mutación aceptada que altera sistema o intervención relevante.
- **evidencia**: registro verificable asociado a decisión, validación o incidencia.
- **incidencia**: evento no deseado que afecta coherencia, alcance o calidad.
- **legado**: material histórico preservado que no gobierna el estado actual, pero sí puede informar o probar genealogía.

## Familias de rol normalizadas

Valores permitidos:

- `government`
- `production`
- `supervision`
- `specialist`

Los documentos visibles pueden usar nombres en español, pero los modelos estructurados deben referirse a estas familias normalizadas cuando toque validación.

## Tipos de tarea

- `analysis`
- `design`
- `execution`
- `validation`
- `organization`
- `system_change`
- `project_bootstrap`
- `repository_audit`
- `history_migration`

## Resultados de validación

- `GO`
- `GO_WITH_RESERVATIONS`
- `KO`

## Estados de sesión

- `created`
- `loaded`
- `in_progress`
- `blocked`
- `awaiting_validation`
- `completed`
- `closed`

## Severidad de cambio

- `patch`
- `minor`
- `major`

## Tipos de evidencia

- `decision`
- `validation`
- `incident`
- `closure`
- `handoff`
- `measurement`
- `migration_trace`

## Regla de traducción histórica

Todo concepto traído desde la v1 debe mapearse a un término de esta taxonomía o quedar marcado como `legacy_*`.

## Regla de introducción de un nuevo término

Un término nuevo solo entra si:

1. nombra una frontera real,
2. no duplica otro,
3. aporta claridad o control,
4. se documenta aquí y, si procede, en esquema.

## Extensión V2.2.1 · Bootstrap de proyecto

Se añade el tipo de tarea:

- `project_bootstrap`

Este tipo debe usarse cuando la tarea depende de un repositorio real y el contexto del proyecto aún no está suficientemente cargado.
