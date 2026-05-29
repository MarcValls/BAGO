# AGENT_START

## PropÃ³sito

Punto de entrada Ãºnico para cualquier agente o sesiÃ³n que opere bajo BAGO.

## Regla de arranque

No ejecutar trabajo tÃ©cnico relevante sin bootstrap mÃ­nimo.

## Secuencia obligatoria

1. Leer `pack.json`.
2. Leer `../README.md` para capa pÃºblica.
3. Leer `core/00_CEREBRO_BAGO.md`.
4. Leer `core/05_GOBERNANZA_DE_SESION.md`.
5. Leer `core/06_MATRIZ_DE_ACTIVACION.md`.
6. Leer `state/global_state.json`.
7. Ejecutar guard de contexto de repo (`tools/repo_context_guard.py check`).
8. Si el guard da `new` o `mismatch`, forzar `workflow_bootstrap_repo_first`/`W1_COLD_START` antes de cualquier otro workflow y tratar `ESTADO_BAGO_ACTUAL` previo como histÃ³rico.
9. Leer `state/ESTADO_BAGO_ACTUAL.md`.
10. Contrastar el estado con el repositorio real.
11. Identificar modo BAGO predominante.
12. Activar solo los roles necesarios.
13. Ejecutar el bloque mÃ­nimo Ãºtil.
14. Actualizar estado tras el bloque.

## Ruta maestra de trabajo

- `workflows/WORKFLOW_MAESTRO_BAGO.md`: secuencia canÃ³nica `canon -> integracion -> entorno -> validacion_escalonada -> baseline -> regresion -> operacion_continua`.

## Oferta de arranque

Tras el bootstrap mÃ­nimo, ofrecer dos caminos:

1. Ejecutar una funciÃ³n Ãºtil del pack, como `./ideas`.
2. Inspeccionar un workflow concreto para configuraciÃ³n humana, como `./workflow-info W1`.

## Regla para workflows concretos

Si el workflow elegido requiere contexto que aÃºn no existe, primero sugerir las tareas previas necesarias y verificar que cumplen su finalidad antes de seguir.

## ESCENARIO-001 activo â€” Reglas W7 obligatorias

Mientras `global_state.json â†’ active_scenarios` incluya `ESCENARIO-001`, **toda sesiÃ³n productiva debe pasar el preflight antes de arrancar**:

````bash
python3 tools/session_preflight.py \
  --objetivo "Verbo + objeto + para que [done]" \
  --roles "role_principal,role_apoyo" \
  --artefactos "ruta/artefacto1.md,ruta/artefacto2.json,ruta/artefacto3.py" \
  --task-type system_change
```

- Resultado `GO` â†’ abrir sesiÃ³n.
- Resultado `KO` â†’ corregir segÃºn indicaciones y repetir.
- En sesiones productivas normales usar **W7_FOCO_SESION** en lugar de W1.

Ver reglas completas en `state/scenarios/ESCENARIO-MEJORA-ARTEFACTOS-FOCO.md`.

## Prohibiciones

- No improvisar el arranque.
- No activar todos los roles por defecto.
- No mezclar bootstrap con ejecuciÃ³n principal.
- No tocar decisiones congeladas sin justificaciÃ³n explÃ­cita.

## InstalaciÃ³n dual activa

Actualmente BAGO opera en dos instalaciones sincronizadas:
- **USB/Pendrive**: E:\bago_fw â€” instalaciÃ³n portÃ¡til original
- **Disco local**: C:\bago_true â€” clone del motor para trabajo rÃ¡pido

Ambas apuntan a GitHub como fuente de verdad:
- Motor: https://github.com/MarcValls/BAGO
- Knowledge: https://github.com/MarcValls/bago-knowledge

### Comando de sincronizaciÃ³n
`ash
python .bago/tools/bago_sync_bidirectional.py --dry-run   # previsualizar
python .bago/tools/bago_sync_bidirectional.py             # sync + push
`

### Motor LLM local (Ollama)
- ago llm status â€” ver estado
- ago llm models â€” catÃ¡logo
- ago launch --local â€” iniciar con modelo local
- Dentro del chat: /local â†’ fuerza local; /escalar â†’ permite cloud
