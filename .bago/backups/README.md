# Backups · BAGO

Este directorio (`\.bago\backups\`) almacena copias de seguridad generadas automáticamente por el framework.

## Subdirectorios

| Subdirectorio | Contenido | Política de retención |
|---------------|-----------|----------------------|
| `engine/` | Backups del motor base (`bago_engine_*.zip`) | Mantener últimos 3. Borrar automáticamente los anteriores. |
| `engine_memory/` | Backups del motor con memoria (`bago_engine_memory_*.zip`) | Mantener últimos 3. |
| `memory/` | Backups solo de memoria (`bago_memory_merged_*.zip`) | Mantener últimos 3. |

## Regla

- Los backups son **append-only**: nunca se sobrescribe un backup existente.
- El nombre incluye timestamp ISO8601 compacto: `YYYYMMDD_HHMMSS`.
- No se admiten backups manuales sin prefijo `bago_`.
- La rotación es responsabilidad de `backup_manager.py` o del comando `bago backup`.
