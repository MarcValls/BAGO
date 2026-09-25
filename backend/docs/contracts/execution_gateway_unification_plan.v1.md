# Execution Gateway Unification Plan v1

Estado: P4_MERGED · RETEST_READY · P5_OPEN  
Base requerida: User Authorization Provenance Boundary (PR #217)

## Objetivo

Convertir `ExecutionGateway` en la única frontera de efectos materiales,
persistentes, externos o privilegiados de BAGO.

La identidad humana fuerte se implementa **después** de cerrar los bypasses de
ejecución. Una prueba WebAuthn/Windows Hello no protege una ruta que nunca pasa
por la frontera de autorización.

## Estado lineal actual

| Fase | Estado | Evidencia principal |
|---|---|---|
| P1 · Effect Registry + Effect-Sink Inventory | IMPLEMENTED | PR #218 |
| P2 · ExecutionRequest v2 | IMPLEMENTED | PR #220 |
| P3 · ExecutionGateway v2 | IMPLEMENTED_SLICE | PR #220 |
| P4 · Scheduler + DelegationGrant | MERGED · RETEST_READY | PR #221; Canonical CI / Validate Expected / njsscan PASS sobre el head del PR |
| P5 · LLM Tool Calls | OPEN | siguiente migración |
| P6–P12 · cierre de frontera única | PENDING | no puede declararse `UNIQUE_EXECUTION_BOUNDARY` |
| P13–P14 · Strong Human Identity Proof | FUTURE | solo después de P12 |

Estado global:

`LEGACY_SCHEDULE_CONFIRMATION_AUTHORITY = REMOVED`

`SCHEDULED_RUN_CHILD_PERMIT = REQUIRED`

`UNIQUE_EXECUTION_BOUNDARY = NOT_YET`

`STRONG_HUMAN_IDENTITY_VERIFIED = NO`

## Invariantes de cierre

1. `NO_MATERIAL_EFFECT_OUTSIDE_EXECUTION_GATEWAY`
2. `CALLER_CANNOT_CHOOSE_EXECUTOR_AFTER_AUTHORIZATION`
3. `STORED_CONFIRMATION != AUTHORITY`
4. `CHILD_AUTHORITY <= PARENT_AUTHORITY`
5. `STRONG_HUMAN_PROOF(operation_A) CANNOT AUTHORIZE operation_B`
6. `UNCLASSIFIED_EFFECT_SINKS = 0`
7. `UNBOUND_EFFECT_SINKS = 0` antes de declarar frontera única.

## P1 — Effect Registry + Effect-Sink Inventory

Materializado en este corte:

- `bago.effect-registry.v1`: taxonomía canónica E0–E6.
- `effect_registry.py`: loader, validación, digest y resolución de riesgo.
- `effect_sink_inventory.py`: scanner estático Python/PowerShell/JavaScript.
- `--strict`: gate futuro que falla mientras queden sinks `unbound`.
- tests de registro, clasificación y bypasses conocidos.

Estado esperado tras P1:

`EFFECT_REGISTRY = ACTIVE`

`EFFECT_SINK_INVENTORY = ACTIVE`

`UNIQUE_EXECUTION_BOUNDARY = NOT_YET`

## P2 — ExecutionRequest v2

Generalizar la operación actualmente especializada en Capability Packages.

Campos mínimos:

- `request_id`
- `effect_id`
- `actor_kind`
- `principal_id`
- `session_id`
- `source_surface`
- `target`
- `arguments_digest`
- `scope`
- `policy_version`
- `parent_execution_id`
- `delegation_id`
- `preconditions`

El fingerprint debe representar exactamente el efecto autorizado.

## P3 — ExecutionGateway v2

Eliminar el patrón público:

`ExecutionGateway(... executor=<caller supplied callable>)`

El caller no puede elegir la función material después de obtener autorización.

Nueva forma:

`ExecutionRequest → ExecutionGateway → EffectAdapterRegistry → EffectAdapter`

Adapters iniciales:

- `FilesystemEffectAdapter`
- `ProcessEffectAdapter`
- `PersistentStateEffectAdapter`
- `ExternalConnectorEffectAdapter`
- `CapabilityRuntimeEffectAdapter`
- `UpdateEffectAdapter`

## P4 — Scheduler / Delegation

Prioridad máxima porque el scheduler actual persiste confirmación/permisos y
ejecuta Capability Packages posteriormente.

Sustituir:

`confirmed=true + approved_permissions`

por:

`DelegationGrant`

Campos mínimos:

- principal
- proof de origen
- allowed effects
- target constraints
- argument constraints
- scope
- issued_at / expires_at
- max_runs / run_count
- revocation state

Cada ejecución programada obtiene un child permit.

## P5 — LLM Tool Calls

Ruta actual:

`model tool call → ToolRegistry.execute_call → subprocess/filesystem`

Ruta objetivo:

`tool call → normalized effect → ExecutionRequest → ExecutionGateway`

La política `always` no podrá autorizar efectos mutantes. Como máximo podrá
aplicarse a efectos read-only explícitamente declarados.

## P6 — Capability / Pipeline Runtime

El handler HTTP ya tiene un primer binding en PR #217, pero el runtime interno
sigue siendo invocable por scheduler y otros callers.

`execute_package` / `execute_pipeline_package` deben quedar detrás de
`CapabilityRuntimeEffectAdapter`.

La autoridad de un child nunca puede superar la del parent.

## P7 — Files + Plans

Migrar:

- `/files/write`
- `write_file` de PlanEngine
- futuras operaciones delete/rename

El `run_command` de planes debe permanecer bloqueado hasta que exista
`ProcessEffectAdapter`.

## P8 — CLI / REPL / Commands

`bago exec`, comandos slash y `/api/v1/commands` deben compartir la misma
clasificación de efectos.

Especial atención a:

- `/autopilot`
- `/update`
- `/credentials`
- `/config`
- `/project`
- `/memory`

La entrada puede ser distinta; la frontera de efecto no.

## P9 — GitHub / Release / System

Migrar:

- GitHub create/mutate/delete
- release download
- release apply
- actualización elevada
- cualquier proceso privilegiado

UAC aporta privilegios del sistema operativo, no autorización BAGO.

## P10 — Persistent State

Migrar KB, agents, provider config, router config, catalog, memory writes,
source roots, workspace bindings y demás mutaciones persistentes.

No todas requieren interacción humana; sí requieren clasificación y paso por
la misma frontera.

## P11 — No-Bypass Gate

Elevar `effect_sink_inventory.py --strict` a gate de CI.

Condición:

`UNBOUND_EFFECT_SINKS = 0`

Cualquier nuevo `write/subprocess/delete/external mutation` fuera de adapters
o internals explícitamente permitidos rompe CI.

## P12 — CRIT Unique Boundary

Ataques mínimos:

- `confirmed=true`
- permisos suministrados por cliente
- memoria que afirma autorización
- agente que afirma consentimiento
- replay de Permit
- operación mutada tras autorización
- child effect mayor que parent
- schedule expirado/revocado
- raw package execution
- CLI bypass
- MCP bypass
- plugin bypass

Promoción solo con P0=0 y P1=0.

Estado de salida:

`EXECUTION_GATEWAY = UNIQUE · VERIFIED`

## P13 — Strong Human Identity Proof

Solo después de P12.

Construir:

`StrongHumanAuthorizationProof`

mediante WebAuthn / Windows Hello / FIDO2, ligado al fingerprint exacto de la
operación.

La credencial fuerte será obligatoria para E5 y E6 y podrá ser elevada por
política para determinados E4.

Cadena final:

`Effect → AuthorizationRequirement → Human Challenge → Strong Proof → Decision → Permit → ExecutionGateway → EffectAdapter → Effect → Receipt`

## P14 — CRIT Strong Human Proof

Ataques mínimos:

- API token válido sin proof humano
- header interactivo falsificado
- assertion de otra operación
- replay
- credencial revocada
- otra sesión
- challenge expirado
- origin/RP inválido
- fingerprint alterado
- delegación ampliada

Estado final:

`AUTHORIZATION_BOUNDARY = UNIQUE · VERIFIED`

`EXECUTION_GATEWAY = UNIQUE · VERIFIED`

`STRONG_HUMAN_IDENTITY_PROOF = VERIFIED`

`LEGACY_CONFIRMATION_AUTHORITY = REMOVED`
