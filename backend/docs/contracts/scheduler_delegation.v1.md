# Scheduler + DelegationGrant v1

Estado: **P4_IMPLEMENTED · RETEST_READY**  
Ámbito: P4 del `Execution Gateway Unification Plan v1`  
Dependencias: Effect Registry v1, ExecutionRequest v2, Authorization Boundary v2, ExecutionGateway v2

## 1. Propósito

Eliminar del scheduler cualquier autoridad derivada de estado persistido como:

`confirmed=true`

`approved_permissions=[...]`

Una programación describe **cuándo** intentar una operación. No autoriza **qué**
puede ejecutar.

Cadena normativa:

`direct user decision`
→ `schedule.delegate ExecutionRequest`
→ `UserAuthorizationProof`
→ `AuthorizationDecision`
→ `parent Permit`
→ `ExecutionGateway`
→ `DelegationGrant`
→ `scheduled trigger`
→ `child ExecutionRequest`
→ `DelegationGrant validation + atomic run claim`
→ `child Permit`
→ `ExecutionGateway`
→ `EffectAdapter`
→ `effect`

## 2. Invariantes P4

1. `SCHEDULE != AUTHORITY`.
2. `STORED_CONFIRMATION != AUTHORITY`.
3. `CLIENT_PERMISSION_LIST != AUTHORITY`.
4. `DELEGATION_GRANT_CREATION_IS_AN_E6_EFFECT`.
5. `DELEGATION_GRANT_REQUIRES_CONSUMED_PARENT_PERMIT`.
6. `CHILD_AUTHORITY <= DELEGATION_GRANT <= PARENT_AUTHORITY`.
7. Cada run consume cardinalidad del grant antes de exponer un child Permit.
8. Cada child Permit es one-time y mantiene las reglas de replay de AuthorizationBoundary.
9. Un grant revocado, expirado, agotado o ligado a policy obsoleta falla cerrado.
10. Cambiar target, argumentos materializados, scope, efecto, cadencia o schedule binding invalida la delegación.
11. `delegation_depth = 1` y `can_redelegate = false`.
12. Un efecto con `delegable=false` no puede entrar en un DelegationGrant.
13. Fallar al resolver el EffectAdapter ocurre antes de gastar una ejecución del grant.
14. El scheduler nunca llama directamente a `execute_package` ni `execute_pipeline_package`.
15. Los schedules legacy habilitados sin DelegationGrant se migran a estado pausado/fail-closed.

## 3. DelegationGrant material

Campos de autoridad:

- `grant_id`
- `principal_id`
- `schedule_id`
- `schedule_digest`
- `allowed_effects`
- `target_digest`
- `arguments_digest`
- `scope`
- `policy_version`
- `child_actor_kind=scheduler`
- `child_source_surface=scheduler`
- `delegation_depth=1`
- `can_redelegate=false`
- `issued_at`
- `expires_at`
- `max_runs`
- `run_count`
- `state`
- `revoked_at`
- `revocation_reason`
- procedencia del parent Permit, proof y decision.

El `grant_fingerprint` cubre el envelope estático de autoridad.

## 4. Child Permit

El trigger temporal no ejecuta.

Primero se reconstruye un `ExecutionRequest` hijo con:

- effect exacto;
- actor `scheduler`;
- principal heredado;
- sesión actual;
- source surface `scheduler`;
- target exacto;
- argumentos exactos;
- scope exacto;
- policy version exacta;
- `parent_execution_id=schedule:<id>`;
- `delegation_id=<grant_id>`.

Después `DelegationGrantRegistry.claim_child` valida el subconjunto y consume
atómicamente una unidad de `max_runs`. Solo entonces
`AuthorizationBoundary.issue_delegated_permit` emite un Permit corto y
one-time ligado al fingerprint exacto del child.

## 5. Mutación de schedules

No requieren ampliar autoridad:

- cambiar nombre;
- cambiar descripción;
- pausar;
- reanudar si el mismo grant sigue válido.

Requieren nuevo DelegationGrant:

- target;
- target_type;
- input material;
- schedule_type;
- interval;
- cron;
- timezone;
- overlap/misfire semantics;
- sustitución de `delegation_id`.

La eliminación del schedule revoca su grant.

## 6. Compatibilidad legacy

Schema del schedule registry: `v2`.

Al leer un registro legacy:

- se eliminan `confirmed`;
- se eliminan `approved_permissions`;
- si no existe `delegation_id`, cualquier schedule habilitado se pausa;
- se marca `legacy_authority_disabled=true`.

Estos campos pueden aparecer en payloads de clientes antiguos, pero nunca se
persisten ni participan en autorización.

El `CapabilityRuntimeEffectAdapter` conserva temporalmente parámetros legacy
internos exigidos por el runtime de paquetes; sus valores proceden de metadata
backend-owned del paquete, no del schedule ni del cliente.

## 7. Targets soportados en P4

`capability` y `pipeline`:

- se normalizan a `capability.execute` / `pipeline.execute`;
- se liga el digest del paquete autorizado;
- se ejecutan por `ExecutionGateway`.

`plan`:

- se normaliza a `plan.execute`;
- puede obtener grant, pero la ejecución falla cerrada mientras no exista su
  EffectAdapter de la fase posterior correspondiente.

`task` dinámico:

- no puede recibir autoridad persistente porque el plan/material effect todavía
  no existe en el momento de autorizar;
- P4 responde `delegation_target_dynamic`;
- debe materializarse primero como plan o paquete gobernado.

## 8. Procedencia humana y P13

P4 conserva la procedencia del parent proof y exige:

`provenance.kind = direct_user_interaction`.

La garantía registrada es:

`proof_assurance = interactive_origin`.

P4 **no** declara identidad humana fuerte. El efecto `schedule.delegate` es E6
y el registro canónico lo marca `authorization_mode=strong`; la prueba
criptográfica WebAuthn / Windows Hello / FIDO2 sigue perteneciendo a P13.

Por tanto:

`INTERACTIVE_ORIGIN_BOUND = YES`

`STRONG_HUMAN_IDENTITY_VERIFIED = NO`

## 9. Retest / CRIT P4

Vectores obligatorios:

- `confirmed=true` sin grant;
- `approved_permissions` inyectados por cliente;
- grant sin parent Permit consumido;
- agent-asserted authorization;
- efecto hijo fuera de `allowed_effects`;
- efecto `delegable=false`;
- target alterado;
- argumentos alterados;
- scope ampliado;
- actor/surface alterados;
- lineage alterado;
- schedule definition alterada;
- policy version obsoleta;
- grant revocado;
- grant expirado;
- grant agotado;
- replay del child Permit;
- adapter inexistente;
- schedule legacy habilitado.

Condición de promoción posterior:

`P0 = 0`

`P1 = 0`

P4 queda preparado para retest, no promovido ni congelado.

## 10. Estado global

`P4_SCHEDULER_DELEGATION = RETEST_READY`

`LEGACY_SCHEDULE_CONFIRMATION_AUTHORITY = REMOVED`

`SCHEDULED_RUN_CHILD_PERMIT = REQUIRED`

`UNIQUE_EXECUTION_BOUNDARY = NOT_YET`

Siguen pendientes P5–P12 antes de declarar ExecutionGateway frontera única.
