# IEB: reemplazo por identidad y gate CredUI — 2026-10-01

## Identidad y alcance

Repositorio BAGO; branch `fix/spbe-runtime-fix1-20260927`; HEAD
`b10178bf8a13d0035079e989e46c36760dbd2a46`; versión 4.11.1.
Windows 10.0.19045, Python 3.14.5, .NET SDK 10.0.300.
El worktree tenía cambios previos. Esta prueba agrega únicamente artefactos
aislados en este directorio. No integra adapters, no emite Permits y no
habilita mutaciones del broker propuesto. Los receipts son evidencia local,
no pruebas de consentimiento aptas para Boundary.

## Reemplazo: VERIFIED en experimento acotado

Secuencia ejecutada: capturar VolumeSerial + FileId128 + SHA256 del target;
abrir padre y target como writers transaccionales; comparar identidad y
contenido; retener exclusión en la transacción; abrir staged como writer;
cerrar handles sin cerrar transacción; `MoveFileTransactedW(REPLACE_EXISTING)`;
`CommitTransaction` o `RollbackTransaction`.

El CAS es una composición de comparación bajo exclusión TxF; la API de rename
no recibe por sí misma un expected FileId. La prueba usa archivos nuevos locales
con nombres simples en scratch, sin adversario que cambie ancestros.

Receipt final: `txf-e8f94c68083d4e9782da9110adae2eb4/observations.json`.
Fuente: `probe_txf_identity.py`, SHA256
`dc329bed6841382051b4832c8f42e040748f96f3102ef1068af1a33be55f7d13`.
Resultado ejecutado: exit 0, `PASS_SCOPED_EXPERIMENT`, diez checks positivos.

- Commit conserva original visible hasta el commit; después aparece contenido
  final y el FileId del staged.
- Drift de FileId deniega; drift de contenido conservando FileId también deniega.
- Rollback conserva contenido e identidad originales.
- 18 competidores en procesos separados intentan escribir, reemplazar target
  o renombrar padre. Todos fallan con error 32/6800. Cubiertas tres ventanas:
  handles abiertos, handles cerrados con transacción viva, y reemplazo realizado
  antes de commit/rollback. Son intercalados deterministas, no estrés concurrente.
- Tres controles sin transacción permiten las mismas operaciones.

`D-FS` sigue OPEN para producción: writers preabiertos, create/delete,
hardlinks, reparse, ADS, ancestros, identidad del padre, crash/recovery,
otros filesystems/builds, permisos/durabilidad y binding de output sellado no
están cubiertos. No se declara imposibilidad universal de otras primitivas.
TxF no se adopta como backend de producto; Microsoft recomienda alternativas y
advierte que puede desaparecer. [CreateFileTransactedW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createfiletransactedw),
[conceptos TxF](https://learn.microsoft.com/en-us/windows/win32/fileio/txf-basic-concepts).

Intentos anteriores fallidos permanecen en `txf-cf50...` y `txf-8ac...`:
`NtSetInformationFile` no proporcionó el reemplazo positivo requerido. Los
receipts anteriores no sustituyen el receipt final.

## CredUI: preflight VERIFIED; autenticación/rendering/proveedor OPEN

`CredUiProbe/` es un host independiente y limitado a un intento. Solicita
`CREDUIWIN_SECURE_PROMPT | CREDUIWIN_AUTHPACKAGE_ONLY` (0x1010), paquete Negotiate,
sin GENERIC ni save. El descriptor incluye nonce, SID hash esperado, paquete,
flags y SHA256 mostrado. Explica que autenticar puede crear una sesión Windows
y que un fallo puede contar para bloqueo de cuenta.

No desempaqueta ni descifra contraseñas, no impersona ni ejecuta efectos con
el token. Sólo admite serialización password interactive/unlock autocontenida,
dominio local y credencial protegida. Rebasa una copia nativa para
`LsaLogonUser` Interactive mediante conexión untrusted; compara el SID recibido
con el principal esperado y cierra el token devuelto. CredUI
success por sí solo nunca cuenta como autenticación. Rechazos y formatos no
soportados mantienen el gate cerrado. Blobs/copias se limpian antes de liberar;
puntero o tamaño inválido nunca se usa para copiar ni limpiar memoria.

Build final: exit 0, 0 errores, 0 warnings. Preflight final:
`credui-5a6cd04b27ad4fa399e5b58f581b2da7/observations.json`:
`LsaConnectUntrusted=0`, lookup Negotiate=0. Fuente SHA256
`4b7202f1921ce717f35bb70125271fcc449f95660896b24a4b9db8d147b7b0c4`;
DLL SHA256 `8539173cf97614bc41c863219b1aacfe9c93e1c0fce3d4da0117aedb1c4fed15`.

`provider-inventory.json` registra 22 providers y DLL/API hashes/signatures.
Las firmas observadas de credui.dll, secur32.dll y advapi32.dll son Valid,
Microsoft Windows. Registro y firma no prueban cuál provider selecciona el
diálogo. CredUI devuelve paquete y blob; no devuelve CLSID del provider.
No inferimos su identidad ni rendering a partir de los flags solicitados.

[CredUI](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-creduipromptforwindowscredentialsw),
[LsaLogonUser](https://learn.microsoft.com/en-us/windows/win32/api/ntsecapi/nf-ntsecapi-lsalogonuser).

## Gate de mutación

`mutations_enabled=false`. Éxito acotado TxF y preflight LSA no satisfacen
conjuntamente D-FS y D-CONSENT. La prueba interactiva y revisión final se
registran a continuación cuando exista su evidencia. No se han ejecutado
suites del producto: esta tarea demuestra primitivas aisladas.

## Revisión independiente previa al diálogo

`bago_final_verifier` revisó fuente, binario y receipts finales read-only.
Resultado: PASS P0 para UNA ejecución interactiva sin retry automático; no
certifica producto ni autoriza mutaciones. Corrigidos cuatro bloqueantes de la
primera revisión: rango/puntero de blob, advertencia de efectos de autenticación,
principal ligado al descriptor, y evidencia final ligada al binario.

Bindings revisados: TxF receipt SHA256
`b41077dfe488f93a67fd265cd56c0a5c3fc83a589b1bcac8fed5071601d9ad6a`;
preflight final SHA256
`cbf1cefdc1ca204258d3192b1657763feab4e24a58c18c891010acdc61a85666`.
Los gaps de D-FS, provider CLSID y rendering permanecen OPEN.

## Ejecución interactiva y corrección de contexto

Receipt `credui-d9731afe2a5e4ff3a9ebf126638808eb/observations.json`, SHA256
`58899ad31cd6d249a74013bf643d9a7690978cda9a29d638360ea69e28016a4c`:
prompt_return=0, package=Negotiate, serialization_type=2, protection_type=2
(SYSTEM). LSA devolvió `0xC000006D` / STATUS_LOGON_FAILURE. El mapeo de error
falló por import incorrecto de LsaNtStatusToWinError desde secur32.dll; el
NTSTATUS real se conservó en el receipt. Este intento está ligado al binario
853917... anterior, no al binario corregido posterior.

Usuario confirmó texto completo y proveedor contraseña, y después aclaró:
NO introdujo usuario/contraseña reales. Por tanto el resultado es una prueba
negativa con credenciales no reales; NO demuestra incompatibilidad del
verificador ni autenticación positiva. El rendering es un testimonio del
usuario para esa ejecución, no una atestación OS del provider/secure desktop.

El hash SID del proceso elevado difiere del preflight original. El probe
original derivaba el principal esperado del proceso que lo lanzaba. Se corrigió
para fijar el hash SID del preflight original y denegar cualquier deriva ANTES
del diálogo; la comparación del token usa también ese hash fijo. No es una
solución portable/producto: el hash fijo es únicamente de este experimento.
También se corrigió la DLL del mapper a advapi32.dll y se conserva substatus
antes del mapping.

Fuente corregida SHA256
`d850a3b40f8d6249984e5381b8efbfb5652afcb082291b4d1025b4d51f7eb847`;
DLL corregida SHA256
`ec85540ff8043822ca04c9b31c71c04fec9fb46ca653ab15ce6f0734665aed28`.
Rebuild exit 0, 0 errores, 0 warnings.
Nuevo lanzamiento elevado produjo
`credui-a7b09cf013d64cb7b160475f4a453e90/observations.json` con
`LAUNCH_PRINCIPAL_DRIFT_DENIED_BEFORE_PROMPT`; no hubo nuevo intento de credencial.

El proxy del entorno sandbox dejó de estar disponible tras el diálogo, por
lo que no fue posible lanzar desde el principal original mediante el tool.
`Run-CredUI-Once.cmd` permite al usuario ejecutar UNA prueba desde su sesión
normal sin elevar. Comprueba el hash DLL antes del prompt. No contiene retry,
no guarda credenciales y no habilita mutaciones. El positivo sigue NOT_RUN.
