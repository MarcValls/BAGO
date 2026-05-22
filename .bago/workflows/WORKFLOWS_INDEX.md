# WORKFLOWS_INDEX

## Proposito

Índice operativo de workflows BAGO. La ruta maestra ordena la secuencia global; este índice baja a workflows tácticos según el tipo de trabajo.

## Ruta maestra

- [WORKFLOW_MAESTRO_BAGO](./WORKFLOW_MAESTRO_BAGO.md): canon -> integracion -> entorno -> validacion_escalonada -> baseline -> regresion -> operacion_continua
- [launch_workflow_maestro.sh](../tools/launch_workflow_maestro.sh): lanzador minimo para abrir la ruta maestra o un workflow tactico.
- `make WF`: selector rapido que enumera los workflows tacticos con su funcion.
- `workflow-info`: inspector de un workflow concreto para ver contexto, preguntas y prerequisitos.

## Workflows tacticos

- [W1_COLD_START](./W1_COLD_START.md): arrancar desde un repo desconocido y dejar un contexto util.
- [W2_IMPLEMENTACION_CONTROLADA](./W2_IMPLEMENTACION_CONTROLADA.md): implementar sin dispersion ni perdida de trazabilidad.
- [W3_REFACTOR_SENSIBLE](./W3_REFACTOR_SENSIBLE.md): refactorizar sin romper contratos ni introducir deriva.
- [W4_DEBUG_MULTICAUSA](./W4_DEBUG_MULTICAUSA.md): diagnosticar fallos con causas plausibles multiples.
- [W5_CIERRE_Y_CONTINUIDAD](./W5_CIERRE_Y_CONTINUIDAD.md): cerrar una sesion con continuidad y siguiente paso claro.
- [W6_IDEACION_APLICADA](./W6_IDEACION_APLICADA.md): analizar el repo y devolver ideas concretas priorizadas por implementabilidad y estabilidad.
- [W7_FOCO_SESION](./W7_FOCO_SESION.md): arrancar una sesión con objetivo único, máximo 2 roles y artefactos pre-declarados. Mejora Producción y Foco. **Usar en sesiones productivas normales en lugar de W1.**
- [W8_EXPLORACION](./W8_EXPLORACION.md): sesión exploratoria ligera sin objetivo concreto previo — preflight mínimo, ≥1 artefacto, ≥1 decisión. W7-lite para cuando no sabes qué vas a cambiar.
- [W9_COSECHA](./W9_COSECHA.md): cosecha contextual post-exploración libre — 3 preguntas, ≤5 min, genera sesión harvest + CHG + EVD automáticamente. Actúa después de que el pensamiento madura.
- [W0_FREE_SESSION](./W0_FREE_SESSION.md): workflow de control para sesiones `.bago/off` — solo para ESCENARIO-002 (competición on/off). No usar en producción.
- [W10_AUDITORIA_SINCERIDAD](./W10_AUDITORIA_SINCERIDAD.md): auditoría de sinceridad — detecta afirmaciones de estado no verificadas y genera un informe de hallazgos con evidencia requerida.

## Regla de uso

1. Empezar por `WORKFLOW_MAESTRO_BAGO` si el objetivo es orientar una sesion completa.
2. Elegir `W1..W7` segun la fase tactica concreta.
3. Usar `make WF` para ver la lista resumida.
4. Usar `workflow-info` cuando se quiera preparar una WF para configuración humana.
5. Usar `launch_workflow_maestro.sh` cuando se quiera entrada ejecutable.
6. Mantener `ESTADO_BAGO_ACTUAL.md` alineado con el workflow ejecutado.

## Nota de conteo público

El sistema publica 11 workflows operativos de usuario (W0–W10). `WORKFLOW_MAESTRO_BAGO.md` y este índice son protocolos del sistema, no workflows operativos adicionales.
