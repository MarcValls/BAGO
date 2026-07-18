# REGLAS DE ACTIVACIÓN · BAGO AMTEC línea canónica previa CORREGIDO

## Finalidad

Controlar activación, contención y escalado de roles. En esta edición se añade una regla explícita: la migración histórica no justifica por sí sola activar más roles. Preservar historia no debe convertirse en inflación operativa.

## Regla matriz

Toda tarea pasa por:

1. clasificación,
2. workflow,
3. activación mínima suficiente,
4. ejecución,
5. validación.

## Maestro BAGO

Se activa cuando hay que recibir, integrar o devolver una salida al usuario. No sustituye ni al Orquestador ni al Validador.

## Orquestador Central

Se activa cuando una tarea necesita clasificación, ruta o secuencia. Es obligatorio en toda tarea no trivial.

## Analista

Se activa cuando el problema está insuficientemente delimitado o cuando hay que comparar estados, versiones, tensiones y riesgos.

## Arquitecto

Se activa cuando se toca estructura, contratos, jerarquías, rutas o integración sistémica.

## Generador

Se activa cuando existe diseño suficiente para producir un artefacto completo.

## Organizador

Se activa cuando hay múltiples artefactos, empaquetado, árbol, índices o handoff complejo.

## Validador

Se activa en toda tarea no trivial que termine en entregable o dictamen.

## Auditor Canónico

Se activa si hay:

- conflicto de nomenclatura,
- migración estructural,
- rutas dudosas,
- competición entre fuentes de verdad,
- dudas sobre compatibilidad con canon.

## Vértice

Se activa cuando hay:

- patrón repetitivo,
- deuda estructural,
- tensión evolutiva,
- necesidad de priorizar simplificación futura.

## Especialistas

Solo si:

- existe frontera técnica real,
- su intervención reduce riesgo o mejora decisión,
- no duplican producción base.

## Casos particulares de migración

En una migración histórica se recomiendan:

- Orquestador
- Auditor Canónico
- Analista
- Validador

Arquitecto y Vértice solo si la migración obliga a rediseñar estructura o si revela patrón de deuda sistémica.

## Activaciones prohibidas

- cinco o más roles para una tarea estrecha,
- Vértice en tareas rutinarias sin patrón,
- especialistas por prestigio o costumbre,
- cierre sin Validador en trabajo no trivial.

## ADAPTADOR_PROYECTO

### Activar cuando

- la tarea cae sobre un repositorio real,
- el contexto del proyecto aún no está cargado,
- el repo cambió de forma relevante.

### No activar cuando

- el contexto del repo ya está cargado y congelado para la iteración actual,
- la tarea es puramente canónica y no depende del proyecto real.

## INICIADOR_MAESTRO

### Activar cuando

- el bootstrap repo-first ya produjo contexto suficiente,
- hay que transformar ese contexto en una entrada limpia para el maestro.

### No activar cuando

- la sesión ya está arrancada y el objetivo actual está claro,
- la tarea no depende de un repo real.

## Regla repo-first

Si la tarea depende de un repositorio real y el contexto no está cargado, el sistema debe recorrer primero `workflow_bootstrap_repo_first` antes de análisis, diseño o ejecución.
