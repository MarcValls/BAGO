# Step 01 — Línea base reproducible

Estado: `EXECUTED · NO CERRADO`

## Candidato

- Rama: `fix/spbe-runtime-fix1-20260927`
- HEAD: `a21858780615440a775a7989970b8917fc0d6732`
- Árbol: `80a13e2b54439df6d4948c93b158048d90666f72`
- Entradas de worktree: `99`
- Fingerprint: `85c961415393a2632321f3660119113205145c764b137227d708776f3be161e2`
- Recibo de ejecución: `%TEMP%/bago-step1-baseline-85c961415393.json`

## Inventario ligado al candidato

El inventario oficial ejecutado dos veces produjo el mismo digest de salida
(`819096bee770a6fa9ea430f3257c455c69221791bdc7e2f35104644024a94955`):

- `3156` sinks detectados
- `2789` sinks sin binding
- `298` `runtime_unbound`
- `0` sin clasificar
- `strict-classification`: salida `0`
- `strict-runtime`: salida `2`
- scanner SHA-256: `41fe714209fef52a14a0e9bb4a1c5e24d68ca17cb48e23df647752a87309be7f`
- registro de efectos SHA-256: `ab1edad052f705ae01092b120858c876ce1ec760e88875beb89b37d55fd61f30`

## Resultado de pruebas

`backend/tests/test_effect_sink_inventory.py`: `46 passed, 1 failed`.

La prueba fallida espera cuatro findings en el adapter de procesos, pero el
scanner devuelve cinco (`test_process_execution_sink_is_owned_by_registered_gateway_adapter`).
La causa debe resolverse en la cobertura/clasificación del scanner antes de
usar esta captura como cierre de partición.

El quinto finding es `process.execute` en `backend/.bago/core/execution_adapters/process.py:768`,
una llamada `subprocess.run` del inspector de identidad de procesos. Está
clasificado como `gateway_owned/gateway_adapter`; no es un efecto desconocido.
El test espera cuatro porque precede a esa ruta de inspección.

## Brecha de cobertura conocida

`bootstrap/msix-host/Program.cs` no se escanea: `bootstrap/` no está en
`DEFAULT_ROOTS` y `.cs` no está en las extensiones de `_iter_files`. Por tanto,
`strict-classification=0` solo clasifica lo descubierto; no prueba cobertura
completa.

La ejecución fue de auditoría y no corrigió el test ni el scanner: la regla de
partición global exige detenerse ante una brecha de cobertura antes de reparar
sinks o cambiar su clasificación.

## Conclusión

La línea base es repetible y el candidato no cambió durante la captura
(`candidate_unchanged=true`, `inventory_deterministic=true`). El paso 1 queda
`NO CERRADO` hasta resolver la discrepancia de la prueba y ampliar/verificar la
cobertura del scanner. No se inició el recibo causal ni `ExecutionTarget`.
