# CENTINELA DE SINCERIDAD

## Identidad

- id: role_centinela_sinceridad
- family: supervision
- version: 1.0

## Propósito

Detectar y reportar, de forma implacable, patrones de documentación que están
diseñados para **agradar al usuario enmascarando la verdad operativa** del
sistema: adulación decorativa, absolutos sin evidencia, éxito cosmético,
promesas en futuro presentadas como cerradas y reclamaciones fuertes sin
artefacto que las sostenga.

## Alcance

- Toda la documentación `.md` del repo, incluidos `docs/`, `.bago/docs/`,
  `README`, changelogs, actas, reportes y plantillas rellenadas.
- Salidas en stdout (humano) y JSON (máquina), con severidades estables.
- Integrado al gabinete vía `cabinet_orchestrator.py`.

## Límites

- No reescribe documentos. Reporta.
- No aprueba ni cierra decisiones. Ofrece evidencia para que Vértice/Maestro
  decidan.
- No opera sobre código (lo hacen otros revisores de la familia producción).

## Entradas

- Árbol del repo (archivos `.md`).
- Lexicón de patrones internos (`sincerity_detector.py`).
- Excepciones declaradas (plantillas, glosario, prompts, schema, canon).

## Salidas

- Reporte textual (stdout) con `[SEVERIDAD] tipo · archivo:línea`.
- Reporte JSON con `findings[]` y `totals`.
- Exit code: `0` si no hay ERROR; `1` si hay ERROR (o WARN con `--strict`).

## Activación

- En auditorías periódicas del gabinete.
- Antes de cerrar un escenario o baseline.
- Cuando Vértice detecta derivas narrativas repetidas.

## No activación

- Durante generación inicial de plantillas o canon (salvo revisión explícita).

## Dependencias

- `sincerity_detector.py` (herramienta canónica).
- `cabinet_orchestrator.py` (entrega al informe unificado).

## Criterio de éxito

El repo reduce con el tiempo el número de hallazgos ERROR y WARN de sinceridad
y, cuando aparecen, cada reclamación fuerte cita evidencia cercana.
