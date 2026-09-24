# 04-FIX2 — Preparación lateral de contrato e integración

Fecha: 2026-09-23

Estado del artefacto: `EXECUTED`

Estado de la revisión: `OPEN / EXECUTED` (identidad reconciliada localmente;
verificación independiente pendiente)

Estado de integración runtime: `CONNECTED_SCOPED`

Este documento registra la ejecución del sidecar bounded de 04-FIX2 sin
modificar el contrato 04_GOVERNED_WORK_PIPELINE_CONTRACT v0.2-FIX1 ni su
package congelado. No es una certificación, no emite autoridad y no convierte
el monorepo completo en gateway-unique por la mera integración de este scope.

## 1. Identidad y límite de autoridad

Baseline declarado por la decisión y la revisión abierta:

- Package: `RED_RAZONAMIENTO_LR_FROZEN_OPEN_2026-09-21`
- Package SHA-256 autoritativo local: `e50b310f2d9775979cce813f27fd92640cb4380290204b2da510d38653da60db`
- Contract SHA-256: `5db2b02ce92b0618cc51559e275c7d12f8d297ce36831213bd2789a4b5288146`

El ZIP con el nombre declarado produce el SHA autoritativo local y sus siete
entradas de `SHA256SUMS.txt` pasan. El SHA histórico `748556bc...` aparece en
otro bundle local de auditoría y queda superseded como identificador de este
baseline. La evidencia completa está en
`.bago/audits/04-fix2-package-identity-reconciliation-20260923.md`.

La identidad ya está reconciliada localmente. El runtime bounded registra ahora
`plan.execute` y sus adapters de child después de cerrar los invariantes y los
retests locales; el review formal sigue sin certificarse hasta la verificación
independiente candidate-bound.

Ownership no transferible:

- 04 es dueño de la coordinación de pipeline/workflow/step, presupuesto
  agregado, bindings de definición e idempotencia.
- 03 conserva los budgets propios de ReasoningRun.
- 02 conserva PropagationBudget y sus invariantes.
- 03A conserva identidad, grants, permits, decisiones, emisión, consumo,
  ampliación y revocación de autoridad.
- 04 solo transporta referencias de autoridad; nunca crea, amplía, consume o
  revoca autoridad.
- STRONG_HUMAN_IDENTITY_PROOF y contrato 05 permanecen fuera de este sidecar.

## 2. Work items ejecutados en el sidecar bounded

### GWP-02-01 — PipelineBudgetEnvelope (ejecutado)

Owner: 04.

Campos preparados para la definición de pipeline:

- `pipeline_budget_envelope_id`
- `budget_limit`
- `budget_consumed`
- `budget_remaining`
- `budget_state` (`AVAILABLE`, `EXHAUSTED`)

Invariantes:

1. `budget_consumed` solo crece dentro del pipeline.
2. `budget_remaining = budget_limit - budget_consumed` y nunca es negativo.
3. Cada step/attempt declara el consumo antes del commit material.
4. Un retry no recarga el envelope.
5. `EXHAUSTED` bloquea nuevos attempts de forma fail-closed.
6. Este envelope no sustituye ningún budget de 02, 03 o 03A.

### GWP-02-02 — Workflow version binding (ejecutado)

Owner: 04 para la identidad de definición; 03A para la autoridad ligada al
attempt.

Campos preparados:

- `workflow_definition_id`
- `workflow_version`
- `workflow_fingerprint`
- `step_definition_fingerprint`

Invariantes:

1. El fingerprint se calcula sobre la definición, no sobre el estado mutable
   del run.
2. Prepare, commit, retry y handoff deben declarar la misma versión explícita.
3. Una definición cambiada entre prepare y commit produce `STALE_DEFINITION` o
   `CONFLICT`; nunca continúa silenciosamente.
4. El handoff no puede actualizar la versión implícitamente.

### GWP-02-03 — Pipeline/step idempotency (ejecutado)

Owner: 04 para la coordinación; 03A conserva las reglas de autoridad del
attempt.

Campos preparados:

- `pipeline_operation_id`
- `step_idempotency_key`
- `outcome_status` (`PENDING`, `COMMITTED`, `FAILED`, `OUTCOME_UNKNOWN`)
- `outcome_receipt_ref`

Invariantes:

1. El mismo `step_idempotency_key` no puede producir dos commits materiales.
2. Un dispatch repetido devuelve el mismo outcome, o un conflicto explícito.
3. `OUTCOME_UNKNOWN` no se convierte en éxito y no permite retry automático.
4. Un retry autorizado usa una identidad de attempt nueva sin recargar el
   presupuesto del pipeline.
5. El outcome permanece ligado al `pipeline_operation_id` y al fingerprint de
   la definición.

### GWP-02-04 — Delegated-authority references (ejecutado)

Owner: 03A para autoridad; 04 únicamente para referencias de coordinación.

Campos preparados:

- `delegation_chain_ref`
- `authority_snapshot_fingerprint`
- `attempt_permit_ref`
- `attempt_decision_ref`

Invariantes:

1. 04 no emite ni consume permits.
2. Un attempt protegido vuelve a 03A para validar su autoridad actual.
3. Handoff, retry y child step rechazan una referencia stale, revocada,
   expirada o incompatible con el fingerprint de operación.
4. La referencia no crea herencia implícita ni permite ampliar el scope.

## 3. Binding ejecutado con Scheduler

El scheduler normaliza `target_type=plan` al target completo de `plan.execute`
y emite un child request mediante `DelegationGrant`. La cadena ejecutada queda
así:

1. `_validated_child_for_schedule` reconstruye el target exacto.
2. `_execute_target` resuelve el adapter antes de consumir una run del grant.
3. `ExecutionGateway` resuelve `plan.execute` y el child material usa el mismo
   gateway-owned adapter.
4. El scheduler no llama directamente a `PlanEngine`, ni interpreta
   `confirmed` o `approved_permissions` como autoridad.

El binding ejecutado transporta, como referencias no autoritativas, el
`workflow_version`, `workflow_fingerprint`, `pipeline_operation_id`,
`step_idempotency_key` y snapshot de autoridad. La validación final seguirá en
03A y la ejecución material seguirá en `ExecutionGateway`.

## 4. Binding ejecutado con PlanEngine

El PlanEngine conserva estado de pasos y receipts locales y ahora se enlaza al
sidecar bounded mediante `PlanRuntimeEffectAdapter`. Los cuatro work items se
mantienen como coordinación runtime, sin transferir ownership de autoridad.

La ruta material queda cerrada en este scope de esta forma:

- `POST /plans/<id>/execute` exige challenge/approve/Permit y ejecuta mediante
  `ExecutionGateway`.
- `write_file` y `read_file` pasan por adapters gateway-owned; el executor
  legacy devuelve un bloqueo estructurado si se invoca fuera de esa cadena.
- `run_command` permanece bloqueado por ausencia de `ProcessEffectAdapter`.
- el registry default registra `plan.execute`, `filesystem.read` y
  `filesystem.write`; no registra `process.execute` como child de plan.
- el scheduler no puede gastar una run de grant si falta el adapter parent, y
  el pipeline no consume presupuesto si falta el adapter child.
- cada child material se construye como `ExecutionRequest` y vuelve al gateway
  mediante `execute_nested`; no hay callable ni escritura directa desde el
  handler o PlanEngine.

## 5. Retests ejecutados

- PASS: budget agotado bloquea el siguiente step y no deja `budget_remaining`
  negativo;
- PASS: retry no recarga `PipelineBudgetEnvelope`;
- PASS: definición stale entre prepare y commit;
- PASS: workflow/version y step fingerprint van ligados al child;
- PASS: doble dispatch concurrente del mismo step produce un solo commit;
- PASS: outcome `OUTCOME_UNKNOWN` sin retry automático;
- PASS: scheduler de plan consume su grant y materializa mediante gateway;
- PASS: child no soportado no consume presupuesto;
- PASS: PlanEngine no escribe sin la cadena `ExecutionRequest → ExecutionGateway`;
- PASS: `confirmed` y `approved_permissions` no sustituyen un Permit;
- PASS: dispatch nested sin contexto gateway-owned queda bloqueado.

La matriz completa de comandos y resultados está en
`.bago/audits/04-fix2-runtime-integration-20260923.md`.

## 6. Transición autorizada

Este artefacto queda en `EXECUTED` con integración `CONNECTED_SCOPED`. La
transición siguiente requiere revisión independiente sobre los cuatro work
items y cualquier gate global separado. La identidad del package congelado ya
está reconciliada localmente. No se promueve a `VERIFIED` ni `VALIDATED`, y la
inventory global de sinks continúa siendo una afirmación distinta y abierta.
