# TEST_ISOLATION_POLICY — BAGO v3.4.0
## Estado: CERRADO ✅ (resuelto en v3.4.0 — Contrato §8)

## Reglas

### Regla 1: Sin escritura en state real
Ningún test puede escribir en `.bago/state/` real. Violación = gate rojo.

### Regla 2: BAGO_STATE_DIR para tests
Tests que necesiten acceso a state DEBEN usar la variable de entorno `BAGO_STATE_DIR`
apuntando a un `tempfile.TemporaryDirectory()`.

### Regla 3: BAGO_NEURAL_STATE_DIR para Neural Bus
Tests del Neural Bus DEBEN usar `BAGO_NEURAL_STATE_DIR` apuntando a tmpdir.

### Regla 4: Cleanup garantizado
El tmpdir debe destruirse al finalizar el test (contexto `with` o fixture `tmp_path`).

## Herramientas de enforcement
- `state_sandbox_agent` — escanea `.bago/state/` pre/post test y detecta cambios
- `post_test_cleanup_loop` — se ejecuta después de `pytest` y verifica no hay ruido

## Historial
- `3.4.0` — Reglas 2, 3 implementadas en `bago_neural.py` y `spiral_loop.py`
- `3.3.0` — Deuda documentada en CONTRACTS.md §8
