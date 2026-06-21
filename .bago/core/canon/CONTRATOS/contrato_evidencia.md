# CONTRATO DE EVIDENCIA · BAGO AMTEC línea canónica previa CORREGIDO

## Campos obligatorios

- `evidence_id`
- `type`
- `related_to`
- `summary`
- `details`
- `status`
- `recorded_at`

## Tipos admitidos

- decision
- validation
- incident
- closure
- handoff
- measurement
- migration_trace

## Regla

La evidencia complementa pero no sustituye el cambio o la sesión.

## Regla especial de migración

Toda migración sustantiva debe dejar al menos una evidencia del tipo `migration_trace`.
