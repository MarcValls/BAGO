# WORKFLOW_MAESTRO_BAGO

## id

`workflow_maestro_bago`

## Regla general

No ejecutar primero.
Primero: entender, encuadrar y dejar trazabilidad.

## Secuencia maestra

`canon -> integracion -> entorno -> validacion_escalonada -> baseline -> regresion -> operacion_continua`

## Modo BAGO por intencion

- `[B]` Balanceado: entender objetivo y limites que no se pueden romper.
- `[A]` Adaptativo: ajustar el plan al estado real del repo y del entorno.
- `[G]` Generativo: producir artefactos y cambios verificables.
- `[O]` Organizativo: cerrar con control, rastro y siguiente paso claro.

## Fase 1: Canon

### Objetivo

Definir que es BAGO, que conserva, que no conserva y reglas obligatorias.

### Salida

- `BAGO_CANON.md` con principios, gobernanza y limites.

### Criterio de paso

Debe poder responderse en una frase: que es BAGO, para que sirve y que no debe intentar ser.

## Fase 2: Integracion

### Objetivo

Hacer que agente y repositorio operen bajo BAGO.

### Salida esperada

- `.bago/AGENT_START.md`
- `.bago/state/ESTADO_BAGO_ACTUAL.md`
- contratos de rol y matriz de activacion vigentes
- protocolo de cambio operativo

### Regla

No tocar sensible sin validacion humana local.

### Criterio de paso

El agente ejecuta este orden sin desviarse:
`leer .bago/ -> entender estado -> contrastar repo -> actuar -> actualizar estado`.

## Fase 3: Entorno

### Objetivo

Preparar entorno local y endurecido para validar de verdad.

### Minimo requerido

- host estable (disco, logs, caches, runtime)
- VM operativa si aplica
- runners reproducibles
- rutas de salida definidas para informes, matriz, baseline y comparativas

### Criterio de paso

Respuesta afirmativa a:
`host aguanta`, `VM arranca`, `runners reproducibles`, `informes en ruta correcta`.

## Fase 4: Validacion escalonada

### Regla principal

Orden obligatorio: `smoke -> stress -> soak`.
No arrancar por `soak`.

### 4.1 Smoke

Pasa con:

- `status=pass`
- `failure_count=0`
- `unexpected_success_count=0`

### 4.2 Stress

Pasa con:

- `pass` limpio
- sin incremento anomalo de fallos
- sin ruido estructural

### 4.3 Soak

Pasa con estabilidad sostenida sin degradacion.
No correr si:

- host justo de disco
- VM no reinicia limpia
- smoke o stress no estabilizados

### Salida de fase

- `smoke-report`
- `stress-report`
- `soak-report`
- resumen consolidado

## Fase 5: Baseline

### Objetivo

Congelar una matriz limpia como referencia oficial.

### Regla

Solo promover baseline tras matriz completa en verde.

### Salida

- baseline congelado
- manifest del baseline
- resumen de referencia

## Fase 6: Regresion

### Objetivo

Convertir validacion puntual en puerta repetible de aceptacion/rechazo.

### Proceso

1. Ejecutar matriz actual.
2. Comparar contra baseline.
3. Fallar ante:

- fallos nuevos
- exitos inesperados anormales
- regresion significativa de tiempo
- regresion significativa de memoria
- regresion significativa de CPU

### Criterio de paso

Comparacion contra baseline en `pass`.

## Fase 7: Operacion continua

### Objetivo

Mantener BAGO como sistema vivo, no como sesion puntual.

### Bucle operativo

1. Arrancar desde `.bago/`.
2. Leer estado.
3. Contrastar repo real.
4. Ejecutar bloque util minimo.
5. Validar al nivel que toque.
6. Actualizar estado.
7. Registrar cambio estructural si aplica.
8. Dejar siguiente paso claro.

## Gobernanza transversal

- `Maestro`: orquesta fase activa y continuidad.
- `Custodio`: bloquea atajos y cambios sensibles sin validacion.
- `Auditor`: registra decisiones, incidencias y diferencias.
- `Supervisor`: protege claridad y estabilidad.

## Orden practico diario

Para arquitectura/runtime:
`canon -> .bago/ -> estado -> repo -> delimitar -> validar sensible -> implementar -> smoke -> stress -> soak(si procede) -> resumen -> baseline o regresion -> actualizar estado -> registrar cambio`.

Para iteracion normal:
`estado -> objetivo -> modo BAGO -> ejecutar -> validar lo justo -> siguiente paso`.

## Criterios de salida por fase

- Canon: se entiende en una pagina.
- Integracion: el agente no trabaja por libre.
- Entorno: infraestructura reproducible.
- Validacion escalonada: smoke/stress/soak confiables.
- Baseline: referencia congelada disponible.
- Regresion: aceptacion/rechazo con criterio.
- Operacion continua: no reconstruir contexto desde cero en cada sesion.

## Version minima

`canon -> integracion -> entorno -> smoke -> stress -> soak -> resumen -> baseline -> regresion -> operacion_continua`

## Navegacion tactica

- `WORKFLOWS_INDEX.md`: indice de acceso a `W1..W6` y a la ruta maestra.
- `workflow-info`: inspector de un workflow concreto para contexto, preguntas y prerequisitos.
- `workflow-info`: inspector para una WF concreta con contexto, preguntas y prerequisitos.
