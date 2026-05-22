# W10 · Auditoría de Sinceridad

## id

`w10_auditoria_sinceridad`

## Objetivo

Detectar y corregir patrones de documentación que enmascaran la verdad
operativa para agradar al usuario.

## Activadores

- Cierre de escenario o baseline.
- Auditoría periódica programada.
- Sospecha de deriva narrativa detectada por Vértice.

## Flujo

1. Ejecutar centinela: `./bago sincerity` (o `python3 .bago/tools/sincerity_detector.py`).
2. Ejecutar gabinete unificado: `./bago cabinet` para contexto cruzado.
3. Clasificar hallazgos por severidad (ERROR bloquea cierre; WARN exige ticket).
4. Por cada ERROR: eliminar adulación, añadir evidencia o rebajar la afirmación.
5. Re-ejecutar `./bago sincerity --strict` hasta quedar en 0 ERROR.
6. Registrar diff de correcciones en `state/changes/`.

## Salida esperada

- Reporte inicial (`sincerity` / `cabinet`) archivado como evidencia.
- Documentos saneados con evidencia cercana.
- Reporte final con exit code 0.

## No entra en W10

- Refactor de código.
- Cambios en canon o contratos (usar W3 + protocolo de cambio).

## Roles

- Principal: `role_centinela_sinceridad`.
- Apoyo: `role_vertice`, `role_maestro`.

## Criterio de cierre

`./bago sincerity --strict` devuelve exit code 0 sobre el alcance auditado y
cada reclamación fuerte remanente cita evidencia (ruta, test, commit, enlace).
