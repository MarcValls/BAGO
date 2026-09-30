---
volume_number: 0
volume_title: "BAGO: contexto, arquitectura y auditoría actual"
subtitle: "Mapa mental completo, estado del código y fronteras de ejecución"
collection: "ARQUITECTURA DE CONTEXTO · BAGO"
author: "BAGO · 27 septiembre 2026"
cover_label: "INFORME EDITORIAL · 2026"
family: "doctrina"
---

# Lectura ejecutiva

BAGO se presenta como un plano de control local centrado en la sesión. La sesión conserva contexto y estado; providers y modelos son motores intercambiables. La interfaz presenta la operación, mientras que el backend mantiene la autoridad sobre los efectos materiales.

La arquitectura que BAGO intenta consolidar conecta intención, elegibilidad semántica, autorización vigente, `ExecutionGateway`, owner del efecto y recibo. La existencia de cada componente por separado no demuestra que todas las rutas respeten esa cadena.

<div class="metric-grid">
  <div class="metric"><span class="metric-label">Sinks detectados</span><strong>{{total_sinks}}</strong><span class="metric-note">en el inventario de esta captura</span></div>
  <div class="metric metric-alert"><span class="metric-label">Runtime-unbound</span><strong>{{runtime_unbound}}</strong><span class="metric-note">el gate strict-runtime sigue abierto</span></div>
  <div class="metric"><span class="metric-label">Gateway-owned</span><strong>{{gateway_owned}}</strong><span class="metric-note">con owner reconocido por el inventario</span></div>
  <div class="metric"><span class="metric-label">Sin clasificar</span><strong>{{unclassified}}</strong><span class="metric-note">scope y binding combinados</span></div>
</div>

## Estado que puede afirmarse

Esta edición esta ligada a una fotografía local identificada en la página de evidencia. El inventario detecta **{{total_sinks}} sinks**, de los que **{{runtime_unbound}} siguen runtime-unbound**. Hay **{{gateway_owned}} gateway-owned** y **{{unclassified}} sin clasificar**. `strict-classification` termina con código {{classification_exit}}; `strict-runtime`, con código {{runtime_exit}}.

La clasificación estricta sin elementos desconocidos certifica la clasificación de lo que el scanner detecta; no demuestra por si sola cobertura completa. El gate runtime sigue abierto. Esta publicación explica el estado y no es una certificacion de cierre.

## Lectura de prioridad

El bloqueo P0 identificado es la ruta de instalación NSIS en máquina limpia: el instalador oficial puede materializar efectos antes de que la autoridad canónica gobierne esa ruta. La correccion requiere resolver primero un host de bootstrap confiable que reutilice el owner de instalación existente. No se ha aplicado una reparación de producción en esta fase.

<div class="editorial-callout"><span class="callout-kicker">P0 · Instalación</span><strong>La ruta NSIS puede producir efectos materiales antes de pasar por la autoridad de BAGO.</strong><span>El hallazgo está documentado; no se ha reparado en esta fase de partición.</span></div>

El inventario global tampoco esta particionado en clusters de reparación verificados, ni se ha cerrado el trace de habituación. Por tanto, los conteos brutos no deben interpretarse como un número de reparaciones ni como una lista lista para delegar.

\newpage

# Identidad y alcance de la fotografía

## Candidato observado

| Campo | Valor |
|---|---|
| Repositorio | `{{repo_root}}` |
| Rama | `{{branch}}` |
| HEAD | `{{head}}` |
| Versión canónica | `{{version}}` |
| Estado del worktree | {{worktree_state}} |
| Fingerprint reproducible del worktree | `{{fingerprint}}` |
| Fecha UTC | {{timestamp}} |
| Scanner SHA-256 | `{{scanner_sha256}}` |
| Effect registry | `bago.effect-registry.v1` · `{{registry_version}}` · SHA-256 `{{registry_sha256}}` |

## Conteos del inventario

| Medida | Conteo |
|---|---:|
| Sinks detectados | {{total_sinks}} |
| Runtime-unbound | {{runtime_unbound}} |
| Gateway-owned | {{gateway_owned}} |
| Scope sin clasificar | {{unclassified_scope}} |
| Binding sin clasificar | {{unclassified_binding}} |
| Unbound total | {{unbound_sinks}} |
| High-confidence unbound | {{high_confidence_unbound}} |

El scanner enumera los tipos de efecto y sus conteos en el manifiesto JSON asociado. Esta página conserva los totales ejecutivos y el enlace reproducible al candidato.

# Tesis y fronteras del producto

## Sesión como fuente de continuidad

La sesión agrupa conversaciones, contexto activo, provider/modelo y workspace. El runtime debe poder cambiar de motor sin delegar al modelo la identidad de la sesión ni el control de permisos.

## Separación entre cliente y autoridad

React y Electron pueden solicitar y presentar operaciones. La autorización y la ejecución material pertenecen al backend. La UI no debe convertirse en segundo emisor de permisos, session manager o executor.

## Capacidad, elegibilidad, autorización y ejecución

Un modelo o una herramienta puede ser capaz de realizar un trabajo sin ser elegible para el caso concreto. Ser elegible no concede autorización. La ejecución solo es posible cuando capacidad, ajuste semantico, autoridad vigente, runtime disponible y precondiciones coinciden.

La secuencia esperada es:

```text
intencion
  -> operacion y recurso
  -> capacidades compatibles
  -> candidatos elegibles
  -> seleccion
  -> autorizacion actual
  -> ExecutionGateway
  -> owner y efecto
  -> recibo y resultado
```

El historial, la puntuacion acumulada o el exito previo pueden ayudar a seleccionar candidatos. No pueden conceder un Permit ni sustituir la autorización actual.

# Selección de modelos y herramientas

## Comparación equivalente

Si la puntuacion recompensa el primer candidato usado, la herramienta que se ejecuta antes puede acumular ventaja. Las comparaciones deben asignar presupuesto y condiciones equivalentes y conservar resultados separados por tarea, modelo y herramienta.

Una bateria generica permite caracterizar capacidades del modelo. Las pruebas de cada combinacion modelo/herramienta comprueban el comportamiento de la composicion real: argumentos, aprobación, proceso, resultado y reingreso al historial. Ninguna puntuacion reemplaza la decisión de autoridad.

## Historial y aprobaciones

La ruta debe analizar como el historial y la política de aprobación influyen en la herramienta elegida, sus argumentos, el proceso invocado y el resultado reincorporado a memoria. Debe comprobar retries, decisiones cacheadas y aprobaciones previas; el trace global de habituación permanece pendiente.

# Contexto y memoria

## Persistencia conocida

La KnowledgeBase y EmbeddingStore tienen un owner `database.write` registrado para sus escrituras. La sesión JSON es la fuente canónica de sesión; la base SessionDB redundante se retiro al no tener lectores que justificaran un segundo índice persistente.

Los planes, recibos y otras escrituras de estado deben seguir sus owners existentes. Una fachada de solo lectura no autoriza a un caller a abrir una ruta paralela de escritura.

## Cadena de habituación por trazar

El trace pendiente debe seguir:

```text
estado historico
  -> decision o score
  -> seleccion de modelo/herramienta
  -> argumentos y operacion
  -> autorizacion vigente
  -> efecto y resultado
  -> historial/memoria actualizado
```

Examinar por separado history, memoria, RL, learning, confidence, trusted state, cache de decisiones, retry, reputacion, prior success y persistencia de sesión. El informe no emite veredicto global sobre esas rutas.

# Ejecución y ownership de efectos

## Cadena de autoridad esperada

1. El caller expresa una operación con `effect_id`, sesión y recurso.
2. La frontera de autorización evalua la solicitud actual.
3. El Permit queda ligado a operación y se consume.
4. `ExecutionGateway` resuelve el adapter server-owned.
5. El adapter revalida identidad, alcance y precondiciones antes del efecto.
6. Un recibo conserva el resultado y su identidad.

El inventario de esta captura reconoce **{{total_sinks}} findings**, incluidos **{{runtime_unbound}} runtime-unbound**. `strict-classification` pasa para los sinks descubiertos; `strict-runtime` falla porque siguen existiendo rutas sin owner gobernado. La partición global por callsite, causa y reparación no está cerrada.

## Regla de reparación

Clasificar primero por responsabilidad material y owner correcto. Reutilizar un adapter si su semántica y alcance son compatibles; extender el contrato si el owner es correcto pero incompleto; proponer un owner nuevo solo si los existentes no pueden poseer la operación correctamente. Eliminar código exige demostrar que no tiene reachability de producción. Reclasificar exige demostrar ownership exclusivo y mantener visible el sink.

No se deben ocultar resultados mediante exclusiones, cambios de confidence o movimientos de código.

# Instalación: bloqueo P0

## Ruta observada

La ruta NSIS oficial de clean install conserva operaciones de staging y materializacion antes de que el runtime BAGO pueda consumir el Permit mediante su `ExecutionGateway`. El inventario mantiene los sinks visibles. El riesgo se clasifica P0 por la posibilidad de producir efectos materiales fuera de la autoridad requerida.

En esta captura, los 33 hallazgos NSIS están concentrados en `releases/bago-installer.nsi`: 27 operaciones de instalación (`filesystem.write`, `process.execute` y `system.configuration.write`) y 6 de desinstalación (`filesystem.delete` y `system.configuration.write`). El mapa P0 acotado señala dos owners existentes que necesitan extensión: `system.install.apply` para instalación y `system.install.uninstall` para retirada. No implica que los otros 232 sinks runtime-unbound estén particionados.

El rastreo posterior de rutas relacionadas con instalación amplió el conjunto de revisión a 93 findings en 15 archivos: 33 de NSIS y otros 60 encontrados por un filtro amplio de nombres y callers. Esos 60 no son 60 bypasses de instalación confirmados: el conjunto incluye, entre otros, selección persistente de roles y preferencias de Electron. Sí hay rutas publicadas adicionales que requieren clasificación propia: `install-remote.ps1` descarga y lanza helpers; `Install-BAGO.ps1` está expuesto por wrappers y documentación del instalador; y el CLI tiene un caller de proceso para `install-v4.ps1`. La partición de esta familia ampliada sigue abierta.

La migración tendrá que sustituir las pruebas que codifican NSIS en rollback, firma y cierre de instalación; conservará el fixture que demuestra que el scanner detecta NSIS y ampliará las pruebas de ambos owners con identidad de paquete, denegación antes del primer efecto y lifecycle separado.

## Owner correcto y límite

El owner de instalación existente sigue siendo la frontera a reutilizar. Apply, rollback y uninstall mantienen identidades de efecto distintas. El adapter y el helper gobernado no transfieren sus garantias a una ruta NSIS que actua antes de ellos.

La propuesta de bootstrap exige un host confiable en máquina limpia, prueba auténtica de artefactos, binding entre host/manifest/sesión/interacción/operación, protección frente a cambios TOCTOU y ausencia de efectos de instalación antes del Permit. No es un plan aprobado ni un cambio ejecutado.

## Revisión independiente del candidato MSIX

La revisión arquitectónica independiente considera que el handoff MSIX puede ser compatible con una única autoridad BAGO si Windows solo provisiona el paquete seed y todos los efectos sobre el destino final siguen la cadena AuthorizationBoundary → Permit consumido → ExecutionGateway → owner existente. El dictamen es condicional; `P0-INS-NSIS-01` sigue abierto y la partición global no está habilitada.

Quedan ocho brechas de diseño: identidad autenticada del paquete y del manifiesto; prueba de interacción nativa no forjable; handoff elevado resistente a manipulación por procesos del mismo usuario; exclusión concurrente por destino; bootstrap inmutable sin mirror ni staging antes del Permit; lifecycle del seed separado del rollback/uninstall del producto; lanzamiento de Electron mediante el owner `process.execute`; y retirada de todas las rutas NSIS oficiales.

La revisión fue read-only y no ejecutó pruebas ni modificó código de producción. El contrato completo y la evidencia por frontera constan en `backend/docs/contracts/bootstrap_authority.v1.md`.

La comprobación remota confirmó que el entorno `release-signing` existe y tiene configurados los nombres de credenciales y variables que usa el workflow; sus valores no se leyeron. Al inicio permitía todas las refs. Se restringió a `main` y la API confirmó la regla. `main` exige el estado `validate` y bloquea force-push y borrado, aunque no exige aprobación de PR. Microsoft documenta Azure Artifact Signing como opción de producción para MSIX, pero BAGO aún no ha construido ni firmado uno con su perfil actual, ni ha verificado la igualdad entre el Publisher del paquete y la identidad firmante.

## Primeras causas locales fuera del bloqueo P0

La misma captura permite comprimir otros 25 findings sin confundirlos con una reparación global. Veinte (`secret_scan.py`: 11; `dead_code.py`: 9) están dentro de `_self_test`: preparan fuentes Python temporales, las escanean y las eliminan. La ruta normal `bago scan secrets/dead` llama a `main(argv)` sin `--test`; el modo de prueba se activa en el entrypoint independiente con `--test`. Propuesta: mover esos fixtures al árbol de tests y mantenerlos visibles al scanner bajo scope `test`. Son 20 callsites de prueba, no escrituras de workspace de la operación normal; no deben borrarse ni reclasificarse mediante una exclusión. Riesgo P2 hasta corregir esa separación.

Otros cinco findings pertenecen a `bago_backup_vault.py`, alcanzable desde `bago backup` por dispatch directo. Cuatro producen el archivo ZIP o restauran sus miembros; el quinto borra backups antiguos durante la rotación. `list_backup_files()` también llama a `backup_dir()`, cuyo `mkdir` convierte `bago backup list` en una escritura. No hay un `ExecutionGateway` en esa cadena. `FilesystemEffectAdapter` solo posee una escritura de archivo de texto; `ProjectWriteEffectAdapter` tiene operaciones de archivo/proyecto y requiere autorización consumida, pero no se ha demostrado que sus contratos puedan generar y restaurar un archivo ZIP completo. `filesystem.delete` exige autorización strong y no tiene adapter registrado en el runtime actual. El adapter `system.install.archive.rollback` se limita al lifecycle de instalación y no es dueño compatible del backup de workspace. Disposición: `BLOCKED`, riesgo P1; revisar primero extensión reuse-first de los owners de workspace/filesystem y separar lectura/listado de materialización. No justificar todavía un owner nuevo.

El backup puede incluir datos de `.bago` distintos del propio directorio de backups; restaurarlo puede reponer estado y preferencias antiguos. Para el trace posterior de habituación: `backup previo → índice elegido → restore → configuración/historial persistido → decisión/ruta de autorización futura`. Un contrato de restore debe ligar sesión, workspace/root, digest del ZIP, lista exacta de miembros y fingerprint de destinos; la rotación necesita identificar el archivo exacto a eliminar. Los negativos deben probar denegación antes del primer efecto, cambio TOCTOU, archivo alterado, traversal/symlink, replay/retry y aislamiento entre raíces. Esta clasificación local no levanta el stop P0 ni autoriza reparaciones.

# Mapa del código

## Capas principales

| Capa | Responsabilidad observable |
|---|---|
| `backend/bago_core/` | CLI, launcher, claims, releases y evidencia |
| `backend/.bago/core/` | SessionManager, contexto, providers y runtime |
| `backend/.bago/api/` | API local y handlers |
| `backend/docs/` y contratos | Contratos, decisiones, guias y evidencia |
| `frontend/` | React, TypeScript y Vite; presentacion cliente |
| `electron-viewer/` y `manager/` | Shell de escritorio y ciclo de vida |
| `releases/` | Instaladores, helpers y versionado de distribucion |
| `.github/workflows/` | Gates de build, instalación y CI |

La coexistencia de `bago_core` y `.bago/core` requiere vigilar imports historicos y wrappers. Consolidar modulos solo tiene sentido al preservar una autoridad, contratos y rutas de ejecución demostrables.

# Comparación de fronteras con el ecosistema

La comparación es conceptual y usa los roles descritos en la documentación de BAGO. No afirma que los repositorios externos se hayan vuelto a auditar en esta fotografía.

| Proyecto/superficie | Rol comparado | Frontera que BAGO debe preservar |
|---|---|---|
| `bago-knowledge` | Conocimiento versionable | El proveedor aporta conocimiento; la sesión BAGO retiene su propio estado. |
| `PANEL_ORQUESTADOR` | Cliente y UX de proyectos | Consumir API estable; no crear otro executor o SessionManager. |
| `BAGO_NEURAL_FABRIC` / `IALAP` | Experimentos de routing y evidencia | Transferir evaluaciones sin crear un segundo motor de permisos. |
| `MUSIC` / `SPRITE` / `WALLET` | Capacidades de dominio | Exponer capabilities con scope y permisos declarados. |
| `TELEGRAM_BOT` | Interfaz remota | Actuar como cliente autenticado, no como tunel de comandos sensibles. |
| Aider | Edición asistida con mapa de repositorio y flujo Git | Referencia para contexto de código, no para ownership de efectos BAGO. |
| Continue | Configuracion de modelos, reglas y herramientas | Referencia de extensibilidad; BAGO conserva autorización server-owned. |
| OpenHands | Runtime componible para agentes | Referencia para aislamiento y runtimes; verificar cada límite de despliegue. |
| Open Interpreter | Harness local con herramientas y aprobaciones | Distinguir sandbox/approval del ownership material de BAGO. |

# Orden de cierre

1. Resolver cobertura del scanner y conservar una fotografía con HEAD y fingerprint verificables.
2. Cerrar el diseño de bootstrap sin crear un segundo emisor de permisos ni owner duplicado.
3. Completar `CRIT-BAGO-SINK-REPAIR-PARTITION-01`: callsites, causas, clusters, DAG y lanes.
4. Ejecutar `CRIT-BAGO-HABITUATION-01-RUNTIME-TRACE` sobre las rutas que afectan decisiones y efectos.
5. Reparar por clusters, serializando los cambios a `AuthorizationBoundary`, `ExecutionGateway`, registries y contratos compartidos.
6. Ejecutar strict-runtime, strict-classification, suite backend completa y revisión independiente sobre el mismo candidato final.

Cada paso es una puerta. El plan no es evidencia de ejecución y un gate de clasificación no equivale al cierre del runtime.

# Evidencia y límite de afirmación

Los datos de esta edición proceden de `backend/.bago/tools/effect_sink_inventory.py`, `backend/.bago/contracts/bago.effect-registry.v1.json`, el worktree identificado en la tabla de snapshot, `backend/docs/contracts/bootstrap_authority.v1.md` y el mapa de `docs/architecture/bago_mind_map.data.json`.

El resultado de suite previamente comunicado (**1.670 passed, 16 skipped y 213 subtests**) corresponde a una ejecución anterior en CI y no se presenta como evidencia del worktree de esta edición. La suite completa ligada a este snapshot es NOT_RUN. El documento tampoco es recibo de release, certificacion de seguridad ni aprobación de reparaciones.

# Anexo · Mapa mental completo

Las ramas y nodos siguientes se cargan desde el mapa estructurado del repositorio. Su jerarquía, estado y detalle se conservan; la auditoría no altera el estado canónico declarado por cada nodo.

{{mind_map}}
