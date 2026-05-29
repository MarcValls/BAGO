# Directorio de trazas · BAGO

Este directorio (`\.bago\traces\`) almacena trazas de ejecución, logs estructurados y rastros de auditoría generados por las herramientas del framework.

## Contenido esperado

- **Trazas de sesión**: registros de entrada/salida de cada sesión BAGO.
- **Trazas de workflow**: pasos ejecutados por cada workflow activo.
- **Trazas de agente**: decisiones y handoffs entre roles.
- **Logs de validación**: resultados de `bago validate`, `bago health`, etc.

## Regla

Las trazas deben ser append-only. No se modifica historia pasada; solo se añaden nuevas entradas con timestamp ISO8601.
