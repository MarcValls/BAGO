# AGENT_START

## Propósito

Punto de entrada único para cualquier agente o sesión que opere bajo BAGO.

## Regla de arranque

No ejecutar trabajo técnico relevante sin bootstrap mínimo.

## Secuencia obligatoria

1. Leer `pack.json`.
2. Leer `../README.md` para capa pública.
3. Leer `core/00_CEREBRO_BAGO.md`.
4. Leer `core/05_GOBERNANZA_DE_SESION.md`.
5. Leer `core/06_MATRIZ_DE_ACTIVACION.md`.
6. Leer `state/global_state.json`.
7. Ejecutar guard de contexto de repo (`tools/repo_context_guard.py check`).
8. Si el guard da `new` o `mismatch`, forzar `workflow_bootstrap_repo_first`/`W1_COLD_START` antes de cualquier otro workflow y tratar `ESTADO_BAGO_ACTUAL` previo como histórico.
9. Leer `state/ESTADO_BAGO_ACTUAL.md`.
10. Contrastar el estado con el repositorio real.
11. Identificar modo BAGO predominante.
12. Activar solo los roles necesarios.
13. Ejecutar el bloque mínimo útil.
14. Actualizar estado tras el bloque.

## Ruta maestra de trabajo

- `workflows/WORKFLOW_MAESTRO_BAGO.md`: secuencia canónica `canon -> integracion -> entorno -> validacion_escalonada -> baseline -> regresion -> operacion_continua`.

## Oferta de arranque

Tras el bootstrap mínimo, ofrecer dos caminos:

1. Ejecutar una función útil del pack, como `./ideas`.
2. Inspeccionar un workflow concreto para configuración humana, como `./workflow-info W1`.

## Regla para workflows concretos

Si el workflow elegido requiere contexto que aún no existe, primero sugerir las tareas previas necesarias y verificar que cumplen su finalidad antes de seguir.

## ESCENARIO-001 activo — Reglas W7 obligatorias

Mientras `global_state.json → active_scenarios` incluya `ESCENARIO-001`, **toda sesión productiva debe pasar el preflight antes de arrancar**:

```bash
python3 tools/session_preflight.py \
  --objetivo "Verbo + objeto + para que [done]" \
  --roles "role_principal,role_apoyo" \
  --artefactos "ruta/artefacto1.md,ruta/artefacto2.json,ruta/artefacto3.py" \
  --task-type system_change
```

- Resultado `GO` → abrir sesión.
- Resultado `KO` → corregir según indicaciones y repetir.
- En sesiones productivas normales usar **W7_FOCO_SESION** en lugar de W1.

Ver reglas completas en `state/scenarios/ESCENARIO-MEJORA-ARTEFACTOS-FOCO.md`.

## Prohibiciones

- No improvisar el arranque.
- No activar todos los roles por defecto.
- No mezclar bootstrap con ejecución principal.
- No tocar decisiones congeladas sin justificación explícita.
