# Execution Gateway v2

Estado: P2_P3_IMPLEMENTED_SLICE · CRIT_READY  
Dependencias: Effect Registry v1, Authorization Boundary v2

## Propósito

Generalizar la autorización desde una operación especializada de Capability
Packages a una petición de ejecución transversal y eliminar el callable
suministrado por el caller.

Cadena materializada:

`ExecutionRequest`
→ `AuthorizationChallenge`
→ `UserAuthorizationProof`
→ `AuthorizationDecision`
→ `Permit`
→ `ExecutionGateway`
→ `EffectAdapterRegistry`
→ `EffectAdapter`
→ efecto

## ExecutionRequest v2

Campos de identidad material:

- effect_id
- actor_kind
- principal_id
- session_id
- source_surface
- target
- arguments_digest
- scope
- policy_version
- parent_execution_id
- delegation_id
- preconditions

El request_id identifica transporte/instancia y NO participa en el fingerprint.
Esto permite reconstruir la misma operación en challenge/approve/execute sin
convertir un ID aleatorio de transporte en autoridad.

El fingerprint sí incluye toda la semántica material.

Los argumentos crudos no se publican en el descriptor de autorización; se
publica únicamente su digest.

## ExecutionGateway v2

Se elimina del API del gateway:

`executor: Callable`

El caller no puede proporcionar la implementación que se ejecutará tras la
autorización.

El gateway resuelve:

`effect_id → EffectAdapter`

mediante un registro backend-owned.

Primer adapter:

`CapabilityRuntimeEffectAdapter`

Efectos:

- `capability.execute`
- `pipeline.execute`

El adapter revalida package kind, package digest y session context antes de
invocar el runtime existente.

## Invariantes

1. `CALLER_CANNOT_CHOOSE_EXECUTOR_AFTER_AUTHORIZATION`
2. `PERMIT.effect_id == ExecutionRequest.effect_id`
3. `PERMIT.fingerprint == ExecutionRequest.fingerprint`
4. `PACKAGE_DIGEST_AT_EXECUTION == AUTHORIZED_PACKAGE_DIGEST`
5. `CONTEXT_SESSION == REQUEST_SESSION`
6. `UNKNOWN_EFFECT_ADAPTER → FAIL_CLOSED`
7. Un error de resolución de adapter no consume un Permit válido.
8. Replay de Permit sigue prohibido.

## Compatibilidad

`AuthorizationOperation` permanece temporalmente como alias de
`ExecutionRequest` y `build_operation` como shim para callers legacy.

Ningún caller nuevo debe usarlos.

## Estado de frontera

Esta versión NO autoriza declarar:

`UNIQUE_EXECUTION_BOUNDARY`

Solo Capability Packages están enlazados al nuevo dispatcher cerrado.

Pendientes:

- Scheduler + DelegationGrant
- LLM Tool Calls
- nested Capability/Pipeline authority
- Files
- Plans
- CLI / REPL / commands
- GitHub / Release / System
- Persistent State
- no-bypass strict CI gate

Estado:

`EXECUTION_REQUEST_V2 = IMPLEMENTED`

`EXECUTION_GATEWAY_V2 = IMPLEMENTED_SLICE`

`UNIQUE_EXECUTION_BOUNDARY = NOT_YET`
