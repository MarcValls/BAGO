# 04-FIX2 — Evidencia de integración runtime acotada

Fecha: 2026-09-23

Estado de ejecución: `EXECUTED`

Estado de revisión: `OPEN / EXECUTED`

Estado de promoción: `NOT_PROMOTED`

## Candidato y alcance

- Repositorio: `C:\Users\AMTEC_Terminal_1º\BAGO`
- Rama: `sync-capability-anatomy-v02-20260922`
- Base Git: `272ed071b7ae2736bdfc6b480153c61ecfc1135a`
- Versión autoritativa: `4.11.1` (`release_version.txt`)
- Worktree: dirty; la evidencia queda ligada al estado de trabajo actual y no
  se presenta como evidencia de un commit limpio.
- Package congelado reconciliado localmente:
  `e50b310f2d9775979cce813f27fd92640cb4380290204b2da510d38653da60db`.
- Contrato 04 incluido en el package:
  `5db2b02ce92b0618cc51559e275c7d12f8d297ce36831213bd2789a4b5288146`.

El package congelado y sus bytes no fueron modificados. Este cambio es un
sidecar runtime bounded; no reescribe 04_GOVERNED_WORK_PIPELINE_CONTRACT, no
introduce contrato 05 y no cambia los owners de 02, 03 o 03A.

## Implementación ejecutada

- `backend/.bago/core/governed_work_pipeline.py`: coordinación sidecar
  `bago.governed-work-pipeline/v0.2-FIX2` con presupuesto, bindings,
  idempotencia, outcomes y referencias de autoridad.
- `backend/.bago/core/execution_gateway.py`: owners server-side para
  `plan.execute`, `filesystem.read` y `filesystem.write`; dispatch nested solo
  para children declarados por el parent consumido.
- `backend/.bago/core/plan_engine.py`: estado gobernado por plan, `attempt` y
  serialización de la evidencia.
- `backend/.bago/api/handlers_schedule.py`: un plan programado se normaliza al
  target completo de `plan.execute`; el adapter se resuelve antes de reclamar
  una run del grant.
- `backend/.bago/api/handlers_jobs.py`: la API de planes exige
  challenge/approve/Permit; el executor legacy permanece fail-closed y
  `auto_execute` no ejecuta autoridad implícita.
- `backend/.bago/api/handlers_files.py`: `/files/write` sigue pasando por el
  mismo gateway y no escribe desde el handler.

`process.execute` no tiene adapter en este bloque: un step `run_command` se
bloquea antes de consumir presupuesto del pipeline. La capacidad no soportada
continúa explícitamente fuera del alcance ejecutado.

## Invariantes cerrados en este candidato

### GWP-02-01 — PipelineBudgetEnvelope

La sidecar materializa `pipeline_budget_envelope_id`, `budget_limit`,
`budget_consumed`, `budget_remaining` y `budget_state`. El consumo se reserva
antes del dispatch material, es monotónico, no se recarga con retry y el estado
`EXHAUSTED` bloquea nuevos attempts.

### GWP-02-02 — Workflow/version binding

El target autorizado contiene `workflow_definition_id`, `workflow_version`,
`workflow_fingerprint`, el fingerprint agregado de steps y el fingerprint de
cada definición. Cambiar la definición después de preparar el Permit produce
`workflow_definition_stale` antes de cualquier child effect.

### GWP-02-03 — Pipeline/step idempotency

Cada attempt usa `pipeline_operation_id`, step id, attempt nuevo y
`step_idempotency_key`. Los outcomes se registran como `PENDING`, `COMMITTED`,
`FAILED` u `OUTCOME_UNKNOWN` con receipt y evidencia. Un replay no vuelve a
materializar el child; `OUTCOME_UNKNOWN` bloquea el retry automático.

### GWP-02-04 — Delegated-authority references

Cada outcome conserva `delegation_chain_ref`,
`authority_snapshot_fingerprint`, `attempt_permit_ref` y
`attempt_decision_ref`. 04 solo transporta esas referencias. El parent Permit
lo emite/consume 03A; `execute_nested` no emite, consume, amplía ni revoca
autoridad y exige el contexto gateway-owned.

## Evidence ejecutada

Claim -> acción -> resultado:

1. Invariantes y rutas materializadas ->
   `python .bago/bin/bago.py verify -- python -m pytest backend/tests/test_governed_work_pipeline.py backend/tests/test_execution_gateway_v2.py backend/tests/test_files_write_workspace_scope.py backend/tests/test_plan_engine_contract.py backend/tests/test_effect_sink_inventory.py backend/tests/test_schedule_delegation.py backend/tests/test_authorization_boundary.py backend/tests/test_delegation_grant.py backend/tests/test_capability_contract.py backend/tests/test_capability_api_v1_contract.py backend/tests/test_api_dispatch_route_meta.py -q` ->
   `PASS`, `96 passed, 142 subtests passed`.
2. Compilación de los módulos runtime y tests tocados ->
   `python -m py_compile ...` sobre los ocho paths del bloque -> `PASS`.
3. Higiene del diff -> `git diff --check` -> `PASS`.
4. Vectores específicos ->
   `backend/tests/test_governed_work_pipeline.py` -> `32 passed`, incluyendo
   write/read real, mutación stale, presupuesto, replay concurrente,
   `OUTCOME_UNKNOWN`, child no soportado y bypass sin contexto gateway.
5. Suite backend completa sobre el candidato final ->
   `python -m pytest -q backend/tests` -> `1240 passed, 2 skipped,
   198 subtests passed`.

La verificación independiente del candidato no se ha ejecutado en este cierre.
Por ello esta evidencia no promueve el estado a `VERIFIED` ni a `VALIDATED`.
La inventory global de sinks permanece una afirmación separada y abierta: este
sidecar no certifica que todo sink del monorepo tenga un único owner gateway.

## Criterio de cierre restante

- revisión independiente candidate-bound;
- eventual gate de inventory global separado;
- reconciliación de cualquier proyección externa stale sin modificar el
  package congelado.

Hasta entonces, el resultado correcto es `EXECUTED`, con integración
`CONNECTED_SCOPED` para Scheduler/PlanEngine y sin promoción global.
