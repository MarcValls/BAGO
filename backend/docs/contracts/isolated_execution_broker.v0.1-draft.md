# ISOLATED_EXECUTION_BROKER_CONTRACT v0.1-DRAFT

Estado del diseño: **PROPOSED**. Artefacto documental: **PREPARED**.
Fecha: 2026-10-01. No adopta canon ni autoriza implementación o efectos.

## 1. Alcance y autoridad

Convertir la propuesta adjunta en un contrato revisable para aislamiento de
procesos y reducción de la ventana entre consentimiento y efecto. El broker
materializa restricciones; no decide permisos. `AuthorizationBoundary` conserva
la emisión, revocación y consumo de Permit. `ExecutionGateway` conserva el
despacho `effect_id -> adapter` backend-owned. Ningún callback, ejecutable o
adapter seleccionado por el worker puede reemplazar ese despacho.

Cadena propuesta:

```text
Governor / propuesta de ronda
  -> Gateway / adapter propietario prepara aislamiento sin efectos de negocio
  -> Broker prepara worker suspendido y recursos -> attestation sellada
  -> superficie de consentimiento canónica -> AuthorizationBoundary emite Permit
  -> Gateway pide claim a AuthorizationBoundary -> Broker habilita staging
  -> worker produce salida -> Broker sella salida sin autoridad del worker
  -> Gateway / Boundary realizan gate final -> adapter propietario hace COMMIT
  -> receipt -> terminación del Job y cierre de recursos
```

`CanonicalPermit` es el nombre conceptual de una extensión del `Permit` actual,
no una segunda clase emisora. `NetworkBroker` y spawn broker son servicios del
adapter propietario; no nuevos gobernadores. Los modos de autorización y las
delegaciones siguen el registro canónico existente. Este borrador no añade un
modo de autoaprobación, bypass ni fallback por confianza histórica.

## 2. Base observada y límites

Checkout local observado: rama `fix/spbe-runtime-fix1-20260927`, HEAD
`b10178bf8a13d0035079e989e46c36760dbd2a46`, versión `4.11.1` desde
`release_version.txt`, worktree sucio. No se formula una afirmación remota.
Los cambios previos de bootstrap y sus goals permanecen fuera de este artefacto.

Fuentes inspeccionadas:

- `backend/.bago/core/authorization_boundary.py`: `Permit`, `_PROCESS_AUTHORITY`,
  `_LOCK`, `consume_permit`, `consumed_authority_lease`.
- `backend/.bago/core/execution_gateway.py`: `execute`, adapter registry,
  validación de world state antes de consumo y despacho, ejecución anidada.
- `backend/.bago/core/native_approval.py`: la confirmación observada usa
  `MessageBoxW` en desktop interactivo; no demuestra CredUI ni secure desktop.
- `backend/docs/contracts/execution_gateway.v2.md`: contrato histórico de slice;
  su lista de pendientes no constituye inventario actual.
- `.bago/runtime/ACTIVE_HANDOFF.md`, contexto, decisiones y conflictos locales:
  continuidad y límites de cierre; sus resultados anteriores no verifican este diseño.

El código actual usa autoridad activa en memoria del proceso y una proyección
JSON que no puede emitir autoridad. `consume_permit` cambia `active -> consumed`
antes del adapter. Su `RLock` no demuestra CAS entre procesos. No se ha encontrado
una implementación de `IsolatedExecutionBroker` ni de su attestation en las
fuentes buscadas. La búsqueda no prueba ausencia global de aislamiento.

## 3. Invariantes exigidas

1. **NO AMBIENT AUTHORITY**: worker sin credenciales del usuario/broker, tokens
   de providers, Permit bearer, sesiones del bus, sockets, Registry writable,
   filesystem real writable ni handles de control del broker.
2. **NO PATH-BASED AUTHORITY AT COMMIT**: ruta es representación/descubrimiento;
   la primitiva debe preservar la identidad autorizada del objeto y namespace.
3. **NO PERMIT BEFORE EXECUTION CONTEXT IS SEALED**: las propiedades efectivas
   del proceso preparado se verifican antes del consentimiento y emisión.
4. **NO IRREVERSIBLE EFFECT FROM THE UNTRUSTED WORKER**: salida en scratch;
   mutación real por el adapter propietario tras gate final.
5. **ONE AUTHORIZATION AUTHORITY** y **ONE EFFECT OWNER**: el broker no emite
   Permits, amplía scope, registra adapters desde IPC ni ejecuta por su cuenta.
6. **FAIL CLOSED ON STATE_DRIFT**: abortar, invalidar y rehidratar; ninguna
   reconstrucción silenciosa del contexto después del consentimiento.
7. **NO REPLAY OR AUTOMATIC RETRY OF COMMIT**: una admisión final por Permit;
   un resultado incierto exige reconciliación del owner, no repetir el efecto.

Amenaza cubierta por el diseño: worker arbitrario malicioso, descendientes,
IPC falsificado, cambios concurrentes de recursos/candidato y salida hostil.
No se promete resistencia a kernel comprometido, administrador hostil o broker
comprometido. Otros procesos del usuario son posibles escritores concurrentes;
una lease BAGO por sí sola no los bloquea.

## 4. Preparación y aislamiento Windows

Perfil normal: AppContainer sin capabilities de Internet/intranet/server,
Job Object sin breakaway, `KILL_ON_JOB_CLOSE`, límites de memoria/CPU/procesos,
mitigaciones verificadas y entorno construido desde allowlist sin secretos.
Job no sustituye el token/AppContainer ni garantiza encerrar procesos creados
mediante servicios externos; esos canales deben quedar inaccesibles [S1, S2].

Crear con imagen absoluta verificada, argv con serialización definida, cwd en
scratch y `CREATE_SUSPENDED`. Asignar/verificar Job, token, capabilities,
mitigaciones y handles antes de resume. Ante cualquier fallo, terminar el
proceso suspendido y liberar recursos; nunca continuar sin sandbox.
La identidad incluye handle de proceso retenido, creation time y digest de
imagen/dependencias autorizadas; PID o hash del archivo por ruta no bastan.
El loader no puede cargar DLL/plugins/código mutable desde scratch o cwd.

Preparar scratch, perfil AppContainer y proceso suspendido también materializa
efectos. Cada uno requiere owner y modo canónico de preparación previamente
adoptado; no se presume que sea libre por ocurrir antes del Permit final.
La autoridad interna de Boundary no se extiende a preparación del broker.
Si no existe una política server-owned acotada para ello, obtener primero la
autorización canónica de preparación; ese Permit no autoriza resume o COMMIT.

Sin herencia: `bInheritHandles=FALSE`. Con herencia explícita:
`STARTUPINFOEX` + `PROC_THREAD_ATTRIBUTE_HANDLE_LIST`, handles inheritable de
derechos mínimos y `bInheritHandles=TRUE` según la API; auditar std handles y
la lista exacta. No combinar FALSE con la expectativa de heredar la lista [S3].
El worker no recibe handles de targets reales, Job, proceso/token del broker ni
handles que permitan duplicarlos. IPC, stdio y scratch constituyen el conjunto
admitido; recursos de entrada se copian o exponen solo lectura si se demuestra
que ello no entrega autoridad ambiental ni secretos ajenos al consentimiento.

Hijos: bloquear creación en el worker; una petición de spawn usa un plan de
descendientes ya ligado a la operación o requiere nueva autorización canónica.
El broker crea cada hijo suspendido en el mismo aislamiento y Job, verifica
antes de resume y nunca acepta `breakaway`/launchers arbitrarios.

Durante consentimiento: worker suspendido, sin UI, red ni handles de efecto.
Workers previos con acceso a la misma superficie de consentimiento deben estar
terminados o aislados de ella. CredUI no es por sí sola prueba de consentimiento
semántico: el verifier canónico debe ligar decisión a descriptor y contexto.
Si la superficie actual no muestra esos datos, el flujo es no elegible.

`RestrictedToken + separate desktop` es perfil **DEGRADED**, con informe explícito
de diferencias y pruebas propias; no puede sustituir AppContainer automáticamente.
Para este draft, DEGRADED y unsandboxed no son elegibles para mutaciones hasta
adopción y evidencia específica. Microsoft recomienda desktop separado para
restricted tokens por exposición a mensajes de ventana [S8].

## 5. Recursos e identidad

Broker abre/retiene objetos y padres antes de sellar contexto. Registro interno:
resource_id opaco, tipo, derechos, VolumeSerialNumber + FileId, identidad padre,
nombre de entrada, stream, digest/version de contenido y política de sharing.
El handle numérico es local al broker; no se serializa como autoridad [S4].

Rechazar por defecto reparse points en todo el camino, junctions, ADS, devices,
UNC/remotos y filesystem sin identidad/semántica probadas. Un flag sobre el
último componente no demuestra seguridad de los padres [S5]. Hard links y
alias requieren rechazo o política explícita que pruebe el alcance de efectos.
Para create, ligar padre retenido y ausencia/nombre exacto de entrada.

FileId prueba identidad, no inmutabilidad del contenido. Revalidar digest y
metadatos autorizados bajo una exclusión efectiva de escritores cuando la
operación depende de ellos. Recursos externos sin exclusión/CAS deben denegar
la mutación. Directory rename y sustitución de entradas también cuentan como drift.

`ReplaceFileW`/`MoveFileEx` por pathname no prueban la invariante 2: existen
ventanas y modos de fallo parciales. El adapter debe especificar una primitiva
por objeto/namespace retenido, o exclusión OS demostrable desde la comprobación
hasta el efecto. `FILE_RENAME_INFO` no constituye por sí solo prueba de CAS
sobre la identidad del destino. Sin prueba de esa propiedad, COMMIT bloqueado
[S6, S7]. No se promete transacción general ni atomicidad multiarchivo.

## 6. Attestation y Permit

`ExecutionContextAttestation` es emitida por el broker confiable, con formato
versionado, JSON canónico definido, SHA-256 con separación de dominio y digest
sin incluir el propio campo digest. Se almacena en registro privado inmutable;
un hash de datos enviados por el worker no demuestra attestation.

Campos obligatorios:

```text
schema_version, execution_context_id, broker_instance_id, authority_epoch
worker_image_digest, dependency_manifest_digest, worker_identity
appcontainer_sid, job_id, effective_isolation_profile, mitigation_digest
operation_digest, argv_digest, environment_digest, resource_set_digest
candidate_fingerprint, session_id, principal_id, round_id
policy_snapshot_digest, revocation_epoch, registry_version_digest
filesystem_resource_ids, network_profile, process_profile, ipc_channel_binding
created_at, attestation_digest
```

Permit extendido, exclusivamente emitido/registrado por AuthorizationBoundary:

```text
permit_id, execution_context_digest, operation_digest, approval_digest
candidate_fingerprint, session_id, principal_id, round_id
policy_snapshot_digest, revocation_epoch, authority_epoch, registry_version_digest
max_uses=1, expires_at, nonce, state=VALID
```

Descriptor mostrado liga operación, recursos y límites, perfil efectivo,
contexto/candidato/ronda y efecto final. `approval_digest` referencia prueba
verificada del descriptor mostrado y decisión; nunca un booleano del caller.
`STATE_DRIFT` incluye policy, round, resource, candidate, registry y epochs.
TTL es defensa secundaria y no extiende autoridad a otro contexto.
`policy_snapshot_digest` se deriva de la política/`policy_version` canónica;
no es otra fuente de política. Los demás digests referencian autoridades
existentes o extensiones propuestas explícitas, nunca declaraciones del caller.

## 7. Máquina de estados, consumo y staging

Separar estado del Permit de resultado del efecto:

```text
VALID -> IN_FLIGHT -> CONSUMED
VALID -> INVALIDATED / EXPIRED / REVOKED
IN_FLIGHT -> CONSUMED (result=success | denied | failed | unknown)
```

Boundary hace claim atómico `VALID -> IN_FLIGHT`, ligado a un único execution_id
y contexto, antes de resume. Gateway sigue siendo quien solicita consumo y
controla adapter. No consumir al empezar staging y luego reutilizar ese Permit
consumido como token general para commit: sería una segunda admisión encubierta.
Dentro de IN_FLIGHT, Boundary concede una sola admisión final y registra
`commit_started`; no vuelve a VALID. Un fallo o cancelación quema la capacidad.

La autoridad reside en un único servicio/proceso Boundary autenticado. Clientes
y helpers nunca cargan JSON para emitir o reclamar. CAS serializado incluye
estado, contexto, execution_id, epochs, expiry y recurso; solicitudes de varios
procesos convergen en esa autoridad. Si se introduce persistencia transaccional,
será interna al mismo Boundary, protegida y con protocolo de recuperación.
Restart invalida permisos/contexts anteriores cambiando authority_epoch;
no rehidrata autoridad activa de la proyección JSON. No se atribuye CAS al RLock
actual entre procesos ni a ExecutionClaimStore, que coordina recursos.

El worker solo produce scratch. Broker espera terminación de todos los writers
del Job, copia salida a staging privado, verifica tipo/tamaño/contenido, rechaza
links/reparse/ADS y sella manifest + digests. Hash mientras el worker aún puede
escribir no es un sello. Staging no se convierte en ejecutable/adapter confiable.

Si el consentimiento especificó bytes exactos de patch/body/message y la salida
no coincide, denegar y preparar una nueva operación con nuevo consentimiento.
Si la salida no era conocida, preparar/autorizar staging no autoriza los bytes
finales: la aprobación de COMMIT debe ligar manifest/digest final en un contexto
sellado nuevo. Sin una semántica canónica explícita de aprobación de resultados
acotados, este draft exige esa segunda ronda. No ampliar permiso retrospectivamente.

## 8. Gate final, revocación y resultados inciertos

Orden del gate: salida sellada -> owner/adapter resuelto -> world state y
recursos revalidados -> Boundary comprueba prueba, contexto, epochs y Permit ->
admisión final única -> primitiva del owner -> receipt y estado terminal.

Comprobación y efecto deben compartir exclusión efectiva/CAS del recurso.
Revocación y admisión final se serializan en Boundary: revocación anterior
impide commit; después del punto de linealización no revierte un efecto.
No afirmar que matar el Job revierte una mutación que el broker ya inició.
Candidate fingerprint delimita entradas de operación; scratch/receipts no
pueden producir drift autoinfligido ni excluir inputs materiales para pasar.

Caída antes del claim: cero efecto final y Job terminado. Caída en staging:
consumir/cancelar ejecución, cero commit. Caída entre admisión y receipt:
resultado UNKNOWN, bloquear replay, reconciliar por identidad/idempotency key
del owner. No prometer exactly-once para red ni transacción OS+ledger.

Receipt incluye IDs/digests anteriores, profile efectivo, resource identities,
manifest final, admisión/commit timestamps, adapter/version, resultado y cleanup.
Sin tokens, secretos ni contenido sensible. Evidence ledger no emite autoridad.
Cleanup termina Job/cierra handles/retira scratch; pertenece al owner y debe
quedar registrado incluso en denegación. Job handle nunca se entrega al worker.

## 9. Red, IPC y efectos externos

Red del worker NONE, sin capacidades ni sockets heredados; comprobar loopback,
LAN, proxy y servicios locales. IPC autenticado al proceso/contexto preparado,
ACL mínima, mensajes tipados con tamaño límite, nonce/sequence, sin RPC genérico,
rutas arbitrarias ni broker impersonating al worker para abrir recursos.

Broker no es proxy libre. Petición liga scheme/host/port/method/path/body digest,
resource y owner. Credentials permanecen en broker. Redirect por defecto DENY;
DNS rebinding, destino efectivo, TLS y proxy requieren perfil probado, sin
transferir credenciales a otro origen. Lecturas externas también requieren el
modo canónico aplicable; el staging no justifica red arbitraria.

`git push`, email, release, delete, credenciales y API mutation: worker prepara
objetos/body/manifest; owner realiza efecto determinista final con nueva ronda
si la salida material cambia. Para Git exigir expected remote ref CAS; para
HTTP usar preconditions/idempotency donde existan. Si proveedor no admite
concurrencia segura, explicitar límite o denegar; no prometer CAS genérico.

## 10. CRIT y criterios de implementación futura

La CRIT debe evaluar este draft, no certificar aislamiento existente. Hallazgo
incluye regla, comportamiento, violación, impacto, evidencia, corrección y método
de verificación. Cualquier escape, duplicación de autoridad o COMMIT basado solo
en ruta impide aprobación para implementación mutante.

| ID | Criterio futuro | Evidencia requerida |
| --- | --- | --- |
| IEB-01 | Token/AppContainer efectivo y cero autoridad ambiental | Windows con worker hostil; attempts FS/Registry/credentials/network/UI |
| IEB-02 | Árbol completo confinado y cleanup al crash | Hijos, breakaway, WMI/servicios, Job handle leaks y cierre último handle |
| IEB-03 | Herencia explícita y sin controles del broker | Enumeración de handles efectivos, stdio y prueba de duplicación denegada |
| IEB-04 | Contexto sellado antes de consentimiento | Traza prepare/attest/display/issue; cambiar argv/env/image/profile deniega |
| IEB-05 | Una autoridad y claim único | Carrera multi-proceso, copia/replay, restart, JSON falsificado, ledger tamper |
| IEB-06 | Recurso exacto en COMMIT | Races en padres/entry/target/content, hardlinks/reparse/ADS, create/delete/replace |
| IEB-07 | Revocación y drift linealizan antes del efecto | Policy/round/candidate/registry/epoch drift preclaim y durante staging |
| IEB-08 | Salida sellada y consentimiento final exacto | Writers concurrentes, output swap, links, bytes distintos del mostrado |
| IEB-09 | IPC/red no amplían scope | Cliente impostor, replay, malformed, redirect/DNS/proxy/loopback/credential leak |
| IEB-10 | UNKNOWN no genera segundo efecto | Crash por fase, failure parcial, timeout y reconciliación owner-specific |
| IEB-11 | Gateway y owners canónicos conservados | Trace API/CLI/nested/delegation, registry desconocido deniega, no callable caller |
| IEB-12 | Evidencia final del candidato exacto | Hashes artefactos, plataforma/build, gates y reviewer independiente |

Orden propuesto: CRIT documental -> cerrar decisiones de primitiva FS, perfil
Windows, semántica Permit y consentimiento final -> autorización explícita de
implementación -> cambios seriales de contratos/Boundary/Gateway -> owner process
y aislamiento -> staging/commit owner-specific -> pruebas hostiles Windows ->
revisión independiente. No iniciar reparación global de sinks desde este draft.

## 11. Fuentes primarias consultadas

Consultadas 2026-10-01. Documentación de APIs es fundamento del diseño; no
evidencia de que BAGO las haya aplicado. APIs y perfiles requieren prueba Windows.

- [S1 AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)
- [S2 Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
- [S3 CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw) y [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
- [S4 FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info)
- [S5 Reparse points and file operations](https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points-and-file-operations)
- [S6 ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)
- [S7 FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
- [S8 CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken)
