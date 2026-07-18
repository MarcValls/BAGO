# CONTRATO DE EVIDENCIA · BAGO AMTEC línea canónica previa CORREGIDO

> LEGADO PRESERVADO.
> No es la fuente de verdad operativa actual.
> La referencia vigente para evidencia vive en `docs/contracts/bago_v4_evidence_contract.md`.

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
