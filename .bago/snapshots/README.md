# Snapshots · BAGO

Este directorio (`\.bago\snapshots\`) almacena snapshots completos del framework en un momento dado.

## Formato

`bago_snapshot_YYYYMMDD_HHMMSS.zip`

## Contenido esperado

Un snapshot es una foto completa del estado del framework incluyendo:

- `pack.json` y manifiestos
- `state/` (sesiones, contratos, evidencias, sprints)
- `tools/` (sin __pycache__)
- `core/` y `roles/`
- `knowledge/` (si está montada)

## Diferencia con backups

| Aspecto | Backup | Snapshot |
|---------|--------|----------|
| **Alcance** | Motor o memoria parcial | Framework completo |
| **Frecuencia** | Post-instalación o pre-cambio | Manual o pre-release |
| **Restauración** | Reinstalar motor | Descomprimir en raíz |

## Regla

- Los snapshots son **append-only**.
- No se generan automáticamente salvo indicación explícita (`bago snapshot create`).
- Se conservan hasta que el usuario los elimine explícitamente.
