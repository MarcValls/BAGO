# Migración y copias

Ejecuta `scripts\backup.cmd` para crear un ZIP.

Para restaurar: detener el MCP, sustituir la carpeta, eliminar `-wal` y `-shm` si existen, reindexar y diagnosticar.

Puedes versionar `memory_root` con Git, pero no publiques datos privados.
