# ISOLATED_EXECUTION_BROKER — v0.2-DECISIONS

Fecha: 2026-10-01. Alcance autorizado: concretar las decisiones abiertas del
v0.1-DRAFT. Documento **PREPARED**, decisiones de diseño **PROPOSED**.
No modifica registro, código de producto, canon ni estado global.

## 1. Resultado y continuidad

| Decisión | Selección | Estado de diseño |
| --- | --- | --- |
| D-FS | No admitir reemplazo de destino mutable sin exclusión efectiva o CAS por identidad. Rename relativo por handle es candidato de namespace, no CAS de destino | OPEN: evidencia contradice la receta handle + rename como solución suficiente |
| D-WIN | LPAC como perfil normal del AppContainer; Job y lista explícita de handles; no capabilities de red ni fallback automático | Especificado; evidencia runtime pendiente |
| D-PERMIT | Extensión del Boundary: claim único, admisión final y journal durable sin facultad emisora; tokens nunca salen al worker | Especificado; integración runtime pendiente |
| D-CONSENT | Consentimiento separado de preparación, RUN y COMMIT cuando el resultado era desconocido; CredUI secure prompt más verificación de identidad y descriptor | Protocolo especificado; proveedor de autenticación y rendering requieren spike Windows |

Readiness de implementación mutante completa: **BLOCKED_BY_D-FS**, además de
las pruebas IEB-01..12 todavía pendientes. No se sustituye atomic replace por
escritura in-place ni se elimina overwrite del objetivo para obtener un PASS.
Las decisiones son elecciones concretas para revisión; no canon adoptado.

Base: rama `fix/spbe-runtime-fix1-20260927`, HEAD
`b10178bf8a13d0035079e989e46c36760dbd2a46`, worktree sucio, versión
`4.11.1` de `release_version.txt`. Sin afirmación remota.
v0.1 y su CRIT se conservan como antecedente por hash. Este documento desarrolla
sus condiciones abiertas; el PASS del v0.1 no se hereda como aprobación del v0.2.

## 2. D-FS — selección basada en observación nativa

Primitiva investigada: `NtSetInformationFile(FileRenameInformationEx=65)`,
source abierto con DELETE, parent retenido en `RootDirectory`, nombre relativo
de una sola entrada. Se probó REPLACE_IF_EXISTS (1) y su combinación con
POSIX_SEMANTICS (3). El experimento solo usa archivos recién creados bajo
`artifacts/ieb-decisions-20261001/`; no apunta a targets de producto.

Windows observado: `Windows-10-10.0.19045-SP0`; Python `3.14.5`.
Evidencia final:
`artifacts/ieb-decisions-20261001/run-d73c49e77ac64515ae4fc210c503f071/observations.json`.

| Caso | Resultado observado |
| --- | --- |
| Sin handle retenido de target, replace relativo | SUCCESS |
| Target retenido sin SHARE_DELETE, replace normal | DENIED, WinError 5 |
| Target retenido sin SHARE_DELETE, replace POSIX | DENIED, WinError 32 |
| Target retenido con SHARE_DELETE, replace normal | DENIED, WinError 5 |
| Target retenido con SHARE_DELETE, replace POSIX | SUCCESS; handle conserva FileId viejo, nombre referencia otro FileId |
| Competidor sustituye target y luego se ejecuta commit POSIX | Ambos SUCCESS; handle autorizado sigue con FileId original |

La última observación es un interleaving determinista en el mismo proceso y
principal, no una prueba de carrera multiproceso ni de aislamiento. Demuestra
que esta primitiva no acepta/comprueba expected-target-FileId: puede reemplazar
una entrada ya sustituida. No demuestra imposibilidad de todas las soluciones
Windows. Cambiar la comprobación a inmediatamente antes del syscall deja la
misma ventana conceptual; comprobar el FileId después descubre el daño tarde.

Un primer intento Win32 con `SetFileInformationByHandle` y parent relativo
devolvió WinError 87 incluso en el baseline. Ese intento no verifica la
semántica de bloqueo. Un segundo intento nativo corrigió el transporte pero
falló al leer por pathname mientras source seguía abierto con DELETE; se
corrigió la observación usando ReadFile con sharing explícito. Solo el tercer
run completo y su hash soportan la tabla anterior. Se conservan los intentos.

Selecciones y descartes:

- Mantener identidad por `VolumeSerialNumber + FileId`, parent/entry/stream,
  digest de contenido y manifest de salida. Son precondiciones necesarias.
- Rename relativo evita redescubrir parent por ruta; **no** prueba CAS de target.
- No escoger `os.replace`, ReplaceFileW, MoveFileEx ni close-lock-then-rename
  como implementación de la invariante de identidad.
- No escoger escritura in-place: cambiaría atomicidad y recuperación exigidas.
- No tratar oplock de directorio como exclusión de entrada: Microsoft documenta
  que esos cambios pueden completar sin acknowledgment [M1].
- No escoger TxF como backend normal: Microsoft recomienda alternativas y
  advierte que puede desaparecer [M2]. No se ejecutó un experimento TxF.
- No introducir minifilter, servicio privilegiado que cambie ACLs del repo,
  writer único que impida editar al usuario, ni redefinición del workspace como
  infraestructura implícitamente autorizada por esta tarea.

Gate de cierre D-FS: proponer una primitiva con expected-target identity o una
exclusión OS efectiva que abarque comprobación y replace, contra escritores
externos no cooperantes del mismo principal; demostrar create/overwrite/delete,
rename de padres, hardlinks, reparse, writers ya abiertos y crash. Si requiere
otro componente o frontera de producto, explicitar esa decisión y su alcance.
Hasta entonces, **D-FS OPEN / mutating COMMIT DENY**. No reparar el adapter
filesystem existente como parte de este trabajo documental.

## 3. D-WIN — perfil elegido LPAC_JOB_V1

Elegir AppContainer **LPAC**, mediante SECURITY_CAPABILITIES y opt-out de
ALL_APPLICATION_PACKAGES. La documentación distingue LPAC de AppContainer
normal por accesos ambientales más restringidos a archivos, Registry y COM [M3].
El perfil normal anterior queda concretado como LPAC; no se hereda compatibilidad
de AppContainer clásico, restricted token ni proceso normal.

| Propiedad | Valor exigido |
| --- | --- |
| Backend | LPAC con SID de instancia; broker mantiene registro privado |
| Red | Cero capability de Internet/intranet/server, cero sockets heredados, sin excepción loopback |
| Registry/COM | Sin capabilities de lectura Registry/COM; prohibido añadirlas para arreglar arranque |
| Imagen | Executable absoluto y manifest sellado de código/dependencias; immutable input separado de output |
| Token | IS_APPCONTAINER + IS_LESS_PRIVILEGED_APPCONTAINER comprobados y conjunto de SIDs efectivo igual al plan |
| Worker creation | Suspendido con PROC_THREAD_ATTRIBUTE_JOB_LIST; comprobar Job efectivo antes de resume |
| Job | KILL_ON_JOB_CLOSE, sin flags breakaway, broker único poseedor de handle de control |
| Procesos | Un worker por contexto; hijos solicitados al broker en otro contexto ligado, suspendidos y verificados |
| Herencia | FALSE sin lista; TRUE + HANDLE_LIST cuando se heredan stdio/IPC explícitos; no pseudo handles |
| Filesystem | Solo scratch de output y entradas selladas; ningún handle writable al target real |
| Desktop/UI | Worker sin interfaz, clipboard ni acceso al desktop de consentimiento; no hereda objetos UI |
| Entorno | Allowlist construida; nunca entorno completo del usuario ni credenciales |
| Mitigaciones | DEP, ASLR donde aplique, STRICT_HANDLE_CHECKS, EXTENSION_POINT_DISABLE y CHILD_PROCESS_RESTRICTED |
| Carga | Prohibir DLL/plugins cargados desde cwd/scratch/ubicación mutable; search path de runtime ligado al manifest |
| Cleanup | Terminar Job y comprobar salida completa antes de retirar profile/scratch; cleanup owner-specific |

Presupuesto inicial elegido: worker activo máximo 1 por contexto, Job 512 MiB,
staging 64 MiB, stdout/stderr 1 MiB cada uno, ejecución 120 s, preparación 30 s,
espera de consentimiento 120 s, contexto completo máximo 300 s. Valores son
límites propuestos, no mediciones. Se ligan a attestation y descriptor; tools
que requieren más recursos preparan otra operación explícita, sin ampliar un
contexto emitido. No activar dynamic-code prohibition o Microsoft-signed-only
indiscriminadamente: debe demostrarse su compatibilidad con la imagen sellada.

Spawn de hijos: cada descendiente tiene máximo un proceso y su propio sub-Job
anidado bajo el Job raíz sin breakaway; requiere identidad/plan ya aprobados
o nueva ronda. El límite del árbol completo se sella en la operación padre.
Sin hijos, raíz ACTIVE_PROCESS_LIMIT=1; con un plan de hijos, el límite de raíz
es la suma sellada del árbol y los sub-Jobs limitan sus propias ramas. No imponer
1 al Job raíz y esperar que deje crear descendientes. El perfil base no autoriza
descendientes; un presupuesto nuevo exige un contexto raíz y consentimiento nuevos.
Una herramienta que no pueda cumplir el perfil queda no elegible; no cambiar
flags, grants o capabilities después del consentimiento para hacerla funcionar.

Interfaces nativas propuestas, sin implementación actual:
`prepare_capsule`, `inspect_capsule`, `resume_capsule`, `terminate_capsule`,
`seal_output`. Aceptan referencias privadas de owner/contexto; no callables,
handles numéricos aportados por cliente ni un command string de shell.
Se alojarán detrás de ProcessExecutionEffectAdapter, que ya posee process.execute.
No se entrega shell abierto con autoridad del broker.

## 4. D-PERMIT — integración elegida

El Boundary de la instancia backend de la sesión conserva autoridad en memoria.
Broker nativo y helpers son clientes autenticados de esa instancia, no emisores.
Se registra `authority_instance_id` y epoch aleatorio por arranque; API/clientes
no escogen el Boundary ni lo reconstruyen leyendo JSON. El protocolo no afirma
que hoy exista un servicio único entre todas las instancias de BAGO.

Mantener JSON como proyección no autoritativa. No añadir un segundo ledger
para emitir Permits. Añadir un journal durable de ejecución/reconciliación
interno al mismo Boundary según sección 4.1, que solo puede imponer bloqueos
y reconstruir resultados, jamás emitir o revivir autoridad. Serializar el claim
y admisión en el mismo Boundary;
los clientes multiproceso llegan a él por IPC autenticado a la instancia/sesión.
El `ExecutionClaimStore` solo coordina recursos, nunca valida consentimiento.

API propuesta de extensión, interna a Boundary y llamada desde Gateway:

```text
issue_context_permit(request, registered_attestation_ref, verified_proof_ref)
claim_context_permit(token, request, context_ref, execution_id) -> admission_ref
admit_final_commit(admission_ref, sealed_manifest_ref, resource_guard_ref)
finish_context_permit(admission_ref, effect_result)
revoke_context_permit(permit_id, reason)
```

Las referencias se resuelven en registros privados backend-owned. Ningún
`resource_guard_ref` declarativo del worker prueba exclusión; D-FS debe haber
cerrado antes de crear un guard elegible. Gateway resuelve adapter antes de
claim, vuelve a validar world state y liga a los servicios internos. El broker
recibe una orden de admisión por canal autenticado; nunca el bearer Permit.

Para evitar hash recursivo: `operation_digest` identifica semántica base del
ExecutionRequest sin attestation; el fingerprint final liga ese digest y
execution_context_digest. La attestation contiene operation_digest base. El
descriptor final de consentimiento liga fingerprint final y manifest. Todo
campo nuevo entra en fingerprint; no meterlo solo en request_id, que el código
actual excluye de la identidad semántica. Requerirá versión nueva del contrato
ExecutionRequest y policy derivada del registro, no reinterpretar v3 silenciosamente.

Máquina elegida:

| Fase | Estado y acción |
| --- | --- |
| Issue | VALID; contexto sellado registrado y proof válido |
| RUN claim | VALID -> IN_FLIGHT; único execution_id, epochs, ronda y sesión |
| RUN finish | IN_FLIGHT -> CONSUMED; output aún no es autoridad final |
| COMMIT claim | Otro Permit para resultado desconocido: VALID -> IN_FLIGHT |
| Commit admission | Validar todo bajo Boundary y guard; commit_started false -> true una sola vez |
| Commit finish | IN_FLIGHT -> CONSUMED; resultado success/failed/denied/unknown |
| Revoke | VALID -> REVOKED; IN_FLIGHT antes de commit_started -> abort/CONSUMED denied |
| Revoke tras admission | Registrar sin prometer deshacer efecto; resultado/reconciliación determinan estado |
| Restart/crash | Epoch nuevo, tokens viejos rechazados; efectos admitidos sin receipt UNKNOWN y sin retry automático |

La transición del Permit se distingue de la vida del worker. Un Permit RUN
consume la capacidad de ejecutar y producir scratch. COMMIT requiere autoridad
sobre manifest exacto y target actual; no reutiliza el RUN consumido. Si los bytes
finales ya eran conocidos antes de RUN, un solo Permit podría cubrir fases de
la misma operación en IN_FLIGHT, pero esa optimización queda fuera de esta
versión: se seleccionan siempre RUN y COMMIT separados para eliminar ambigüedad.

Revocación y commit_started linealizan en Boundary. Denegación o fallo nunca
vuelven a VALID. Expiry se comprueba también antes de admisión final; el tiempo
no equivale a permiso renovable. Una llamada que perdió su reply no recupera
token usable; solo consulta estado por execution_id autenticado, incluso tras
restart desde el journal de reconciliación, sin recuperar un Permit.

### 4.1 Journal durable y fence de reemisión

Almacenamiento elegido: journal transaccional SQLite privado, propiedad del
mismo AuthorizationBoundary, separado de su proyección JSON y del
ExecutionClaimStore. SQLite contiene **historia y fences**, no la autoridad
activa. Se propone WAL y synchronous=FULL; su garantía de durabilidad requiere
prueba de fallos en el volumen local. No usar almacenamiento remoto.
Una sola instancia Boundary activa posee cada root protegido de journal, con
guard OS entre procesos ligado a la identidad canónica del root. Si otra ya lo
posee, la segunda no emite ni admite esta ruta. Solo el propietario abre la
conexión writer/readers del journal; helpers consultan por IPC. Los fences se
buscan a través de todas las sesiones del root, no solo la sesión nueva. Cambiar
root no autoriza reintentar un recurso incierto: su binding de workspace/owner
al root protegido debe verificarse antes de preparar o emitir.

Registros mínimos: contract_version, record_sequence, authority_instance_id,
epoch, session/principal/round, execution_id, phase, operation_digest,
semantic_effect_key, resource_set_digest, attestation_digest, manifest_digest,
idempotency_key owner-specific, timestamp, event, result y reconciliation_ref.
No bearer tokens, contraseñas, approval credentials ni handles numéricos.

Eventos: PREPARE_INTENT, RESOURCE_INTENT, RESOURCE_CREATED, PREPARED,
RUN_ADMITTED, COMMIT_ADMITTED, EFFECT_RESULT, UNKNOWN, CLEANUP_PENDING,
CLEANUP_RESULT, RECONCILED. Una transacción durable COMMIT_ADMITTED se completa
antes de la primera instrucción del efecto; contiene admission_id único y
commit_started=true. Si la persistencia falla, cero efecto y DENY. Si persistió
y falla la respuesta al broker, la admisión no se vuelve a enviar; se consulta
estado y se reconcilia. No se afirma atomicidad entre SQLite y efecto OS/remoto.

Tras restart, Boundary crea epoch nuevo e invalida todos los Permits vivos;
reconstruye exclusivamente resultados y fences desde el journal. Todo ADMITTED
sin resultado terminal verificable se clasifica UNKNOWN. PREPARE_INTENT sin
PREPARED activa cleanup y bloqueo de RUN según sección 5.1. Un EFFECT_RESULT
que no tenga prueba owner-specific de completar el efecto también queda UNKNOWN.

Fence de reemisión: UNKNOWN bloquea no solo el token viejo, sino operaciones
semánticamente equivalentes y todas las mutaciones que afectan a sus recursos.
La llave no incluye nonce, epoch, request_id ni round; cambiar IDs no evita el
bloqueo. Se deriva de effect/owner, namespace e identidad del recurso y acción
material. El owner fija cómo detectar equivalencias externas (por ejemplo,
repo/ref para Git; destinatario/message-id/body para email). Si no puede
determinarlas, deniega todas las nuevas mutaciones de ese owner/root hasta
reconciliar. Boundary consulta fences antes de emitir y antes de admitir.

Reconciliación: el owner inspecciona el estado real sin repetir el efecto y
produce una prueba referenciada en RECONCILED. Solo Boundary libera el fence.
Una nueva ejecución requiere nuevo contexto, nueva prueba y nuevo Permit;
nunca se cambia UNKNOWN a VALID ni se reanuda un antiguo admission_id. Si el
proveedor no permite demostrar efecto ocurrido/no ocurrido, fence permanece.
Una decisión humana de resolver incertidumbre debe tener operación y prueba
propias; no equivale a prueba de no efecto.

La persistencia del journal es autoridad interna del Boundary, igual que su
persistencia de ledger; no se delega a un worker ni a un caller. Root protegido,
identidad e integridad del backing store son precondiciones de arranque. Worker
LPAC no obtiene acceso. Corrupto, perdido o rollback sospechoso implica
EXECUTION_QUARANTINED, no crear una base vacía y continuar. El mecanismo de
protección/continuidad del backing store debe demostrarse en implementación;
ACLs o DPAPI del mismo usuario no se presentan como defensa contra administrador
o proceso del usuario que comprometa al broker. Si el almacenamiento protegido
no está disponible, esta ruta no puede admitir efectos.

Gate: crash antes/después de commit durable, durante efecto y antes de receipt;
reiniciar; intentar operación equivalente con nuevos IDs/ronda/epoch; debe
denegar hasta reconciliación. Journal no contiene funciones ni datos suficientes
para emitir una capacidad de ejecución, incluso si un cliente copia sus bytes.

## 5. D-CONSENT — preparación, RUN y COMMIT

Se elige una ceremonia por operación material conocida:

1. **PREPARE**: autoriza la preparación del entorno por código trusted, sin
   ejecución del worker. Su contexto es el host trusted ya existente y sellado,
   no el worker futuro. Declara profile, scratch exacto, presupuesto y cleanup.
2. **RUN**: después de prepare_capsule e inspect_capsule, aprobar el worker
   exacto suspendido y las restricciones reales. Claim y resume solo por Gateway.
3. **COMMIT**: después de terminar writers y sellar output en staging privado,
   construir nueva operación con manifest/digests y estado de target vigente.
   Si hubo STATE_DRIFT respecto del contexto que produjo la salida, abortar y
   rehidratar; no pedir aprobación nueva para legitimar una salida stale.

PREPARE es una extensión de las operaciones del owner process, con efectos de
scratch escritos por el owner filesystem/state correspondiente. No delegar a
process.inspect ni asumir que su policy read-only permite crear profiles.
Un plan de preparación con hijos materiales resuelve `inherit_max_child` por
el registro. Mapear todos esos efectos y roots es requisito previo al registro
de la operación; no existe hoy un nuevo effect_id aprobado por este documento.

La invariante NO PERMIT BEFORE CONTEXT SEALED se aplica a cada contexto:
PREPARE liga contexto trusted preparador sellado; RUN liga capsule real; COMMIT
liga output y recursos sellados. No exige preparar un worker antes de autorizar
su preparación ni crea una excepción implícita a la autoridad de efectos.

Surface elegida para esta ruta: `CredUIPromptForWindowsCredentialsW` con
`CREDUIWIN_SECURE_PROMPT`, sin GENERIC, save ni enumeración de admins. Mostrar
descriptor canónico y digest en el prompt; no tratar su retorno ERROR_SUCCESS
como autenticación del principal. Microsoft lo define como diálogo para
recoger credenciales y devolver un blob [M4]. Su autenticación debe completarse
por un verificador OS/paquete compatible en el host trusted; no se selecciona
desempaquetar contraseña o impersonar al usuario para ejecutar efectos.

No inventar que cualquier Credential Provider muestra el texto BAGO o valida
la misma identidad. El spike de proveedor debe probar rendering real sin
truncamiento, validación del SID principal y vínculo entre transcript/nonce y
descriptor; si el paquete no admite verificarlo sin filtrar credenciales o
si omite el descriptor, esa combinación es no elegible. Elegir esta API fija
la superficie objetivo; la compatibilidad del verificador es un gate abierto,
no una garantía inferida del nombre secure prompt.

`approval_digest` = digest versionado del descriptor final mostrado, decision,
challenge nonce, principal SID verificado, session, round, context, manifest y
authority epoch. Proof se crea por el verificador trusted, no desde JSON HTTP.
Single active challenge por instancia; cancelar/timeout quema challenge. Nuevo
contexto tras drift necesita una nueva ceremonia, sin replay de credenciales.
Limpiar/free del blob según API, nunca guardarlo en ledger, receipt o worker.
CredUI y verificador no emiten Permit; únicamente Boundary evalúa su prueba.

Current native_approval.py usa MessageBoxW y no cumple este protocolo. Migración
futura agrega una ruta versionada; no reinterpretar sus booleans existentes
como proofs CredUI. Modos `policy`, `explicit`, `strong`, `inherit_max_child`
siguen siendo los únicos canónicos. Esta ruta aislada puede exigir procedencia
más estricta dentro del modo resuelto; no rebajar `strong` ni delegación.

### 5.1 Máquina de preparación, fallos y cleanup

```text
NEW -> PREPARE_AUTHORIZED -> ALLOCATING -> WORKER_SUSPENDED
    -> CONFINED -> INSPECTED -> PREPARED
cualquier fase no terminal -> ABORTING -> CLEANUP_PENDING -> CLOSED
```

PREPARED solo se publica tras inspección efectiva, attestation registrada y
journal durable PREPARED. Un error/timeout/cancel o epoch viejo revoca el
challenge de RUN y terminaliza la admisión de PREPARE; el contexto nunca vuelve
a PREPARE_AUTHORIZED ni es reutilizable. Una tentativa nueva usa otro context_id
y permisos nuevos. RUN rechaza toda fase distinta de PREPARED, cleanup pendiente,
error previo, owner desaparecido, attestation ausente o inspección stale.

Orden elegido: journal PREPARE_INTENT -> scratch/input staging -> perfil LPAC
-> Job configurado -> worker suspendido con JOB_LIST -> comprobación de Job
-> inspección token/handles/mitigaciones/imagen -> attestation -> PREPARED.
Antes de cada creación, RESOURCE_INTENT durable con identidad anticipada y owner;
después, RESOURCE_CREATED con identidad efectiva. Si falla el journal, abortar
sin crear el siguiente recurso. Los nombres/SIDs/profile monikers dependen del
context_id y son registrados antes de la creación para descubrir recursos cuando
el broker cae entre create y RESOURCE_CREATED.

| Fallo | Código estable propuesto | Acción inmediata y owner |
| --- | --- | --- |
| Root/scratch/inputs | IEB_PREPARE_SCRATCH_FAILED | filesystem/state owner limpia solo recursos registrados de ese contexto |
| Perfil/token LPAC | IEB_PREPARE_PROFILE_FAILED | process owner retira perfil propio, nunca un perfil ajeno |
| Job/config | IEB_PREPARE_JOB_FAILED | process owner cierra handle/control y registra estado |
| CreateProcess suspendido | IEB_PREPARE_WORKER_FAILED | process owner termina cualquier proceso creado; ningún resume |
| Asignación/comprobación Job | IEB_PREPARE_CONFINEMENT_FAILED | process owner termina por handle exacto antes de cerrar Job |
| Token/handles/mitigaciones/imagen | IEB_PREPARE_ATTESTATION_FAILED | process owner termina Job/proceso; invalida cualquier attestation |
| Journal | IEB_PREPARE_JOURNAL_FAILED | cuarentena; no publicar PREPARED/RUN, cleanup conservador por identidad |
| Timeout/cancel/caída broker | IEB_PREPARE_ABORTED | terminalizar admission; reconstruir cleanup desde journal |

Receipt de PREPARE: execution/context IDs, estado terminal, código, fase que
falló, recursos creados confirmados e inciertos, cleanup owner/status y pruebas
de identidad/terminación. No promover success parcial a PREPARED. Error en
cleanup genera CLEANUP_PENDING, receipt de fallo y fence sobre contexto/recursos;
no se oculta ni se borra el journal para producir un resultado limpio.

Cleanup idempotente, por owner: invalidar admissions/challenges -> terminar
worker y descendientes por Job/handles exactos -> comprobar terminación ->
cerrar canales/handles -> retirar perfil y scratch registrados -> CLOSED.
Cada paso registra intent/result. No borrar por PID/nombre solamente: comparar
creation time, SID/context y identidad persistida; si no se puede demostrar
propiedad, registrar UNKNOWN y conservar fence, sin eliminar recurso ajeno.

Para cerrar la ventana CreateProcess->AssignJob se elige
`PROC_THREAD_ATTRIBUTE_JOB_LIST` al crear suspendido: la API documenta la lista
de Jobs que se asignan al nuevo proceso. Mantener el handle de Job únicamente
en el broker permite aplicar KILL_ON_JOB_CLOSE si este cae después de crear.
No seleccionar un supervisor nuevo ni CreateProcess seguido de AssignJob como
fallback. Fallo del atributo o incompatibilidad con nesting implica DENY.
Debe demostrarse nativamente creación/confinamiento y caída del broker en cada
frontera; documentación de API no prueba por sí sola esa propiedad en BAGO.

Gate: fallar en cada frontera de creación/registro/inspección/cleanup y matar
broker; después de restart RUN debe denegar y el owner debe probar
terminación o retener fence UNKNOWN. Ningún retry de PREPARE reutiliza recursos
inciertos sin reconciliación y nueva autoridad canónica.

## 6. Secuencia de implementación definida, todavía no ejecutada

| Paso | Owner / integración | Criterio previo |
| --- | --- | --- |
| A | Contracts + Boundary + Gateway, cambios seriales | Revisar esta especificación y resolver epochs/fingerprint sin recurrencia |
| B | ProcessExecutionEffectAdapter + nativo capsule | Preparación con authority/owners exactos; perfil LPAC y recursos efectivos |
| C | Verificador nativo + native_approval | Spike secure prompt, provider, SID y descriptor completo |
| D | Boundary claims/IPC y RUN en scratch | Carrera clients, replay/restart/revoke sin admisiones duplicadas |
| E | FilesystemEffectAdapter + primitiva real | D-FS cerrado con exclusión/CAS y recuperación, no os.replace por pathname |
| F | Owner-specific red/Git/email/release | Gates de operación/preconditions/idempotencia y pruebas correspondientes |

Puntos compartidos Boundary/Gateway/registry/contracts siempre serializados.
No crear lanes paralelas que editen esas autoridades. No iniciar reparación
global de sinks ni bootstrap a partir de este documento.

## 7. Evidencia y límites

Probe final SHA-256:
`b20e9fa52cfe8cae5d755ae116481f771d0cd2fa7f5c3bdaad80cb53cbc26dac`.
Observations final SHA-256:
`b0fa96dc2a06fe8e2b4dcc8f90dc1c87f5d8759bf701ff830c8e50b399242402`.
Un rerun genera otro directorio, FileIds y evidence hash; no mezclar resultados.

Fuentes locales nuevas trazadas:
`execution_request.py` v3, effect registry JSON, adapters filesystem/process y
`filesystem_effects.py`. El writer observado materializa temp y os.replace por
ruta; no ofrece el gate de objetos propuesto. No se modificó ese writer.
Hashes completos de fuentes y artefactos se registran en companion review.

NOT_RUN: creación LPAC/Job, herencia efectiva, CredUI, verificación credencial,
CAS Boundary/IPC, adversarial race multiproceso, full suite y build del producto.
El experimento de rename no es ninguna de esas verificaciones.

## 8. Fuentes primarias

Consulta: 2026-10-01. Reglas BAGO de este documento son decisiones propuestas;
la documentación de APIs solo soporta las propiedades expresamente citadas.

- [M1 FSCTL_REQUEST_OPLOCK](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_request_oplock)
- [M2 Transactional NTFS](https://learn.microsoft.com/en-us/windows/win32/fileio/transactional-ntfs-portal)
- [M3 Launch an AppContainer/LPAC](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)
- [M4 CredUIPromptForWindowsCredentialsW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsw)
- [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information)
- [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
- [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute)
- [GetTokenInformation](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-gettokeninformation)
- [SQLite WAL](https://sqlite.org/wal.html) y [synchronous](https://sqlite.org/pragma.html#pragma_synchronous)
