# Veredicto de release — BAGO 3.4.0b1

No marcar todavía como `3.4.0` estable.

BAGO está mucho más limpio: los contratos quedaron explícitos, la superficie CLI
vuelve a cuadrar con el registry y la documentación pública ya no debería anunciar
conteos falsos. Aun así, el propio contrato deja pendientes reales que bloquean
un estable honesto:

- `bago spiral --test` queda bloqueado por el guard de comandos dangerous.
- `bago neural --test` tiene side effects sobre state runtime.
- Hay tests legacy por migrar o archivar.
- Las docs `.bago/CLI_v3_*` deben declararse históricas explícitamente.

Siguiente paso razonable: `3.4.0b2`.