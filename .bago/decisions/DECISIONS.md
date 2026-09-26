# Decisions

Record architectural or product decisions that affect canon here.

## 2026-09-26 — AgentGateway CLI commands use the process owner

- `agent_gateway.py` no longer launches BAGO with `subprocess.run`. Its local
  adapter sends the canonical launcher module, exact argv, active session,
  workspace, timeout and current launcher digest through `process.execute`.
  Execution requires a direct TTY challenge and a consumed Permit; absent
  session, absent TTY, rejected authorization, or invalid argv blocks before
  spawn. Ollama may validate the canonical intent argv, but its response is
  never interpreted as executable command text.
- The CLI dispatch restores the canonical active `SessionManager`. Cloud
  serialization explicitly omits that in-process authority object.
- Evidence: agent command + agent gateway + ExecutionGateway suites: 66 passed;
  `py_compile` and `git diff --check` pass. Inventory: `2329` total / `63`
  runtime-unbound / `0` unclassified; strict classification passes and strict
  runtime remains open. The block is committed, but it is not a final candidate
  for the global gate while runtime sinks remain.
- The new CLI import shifted one AST inventory line. The generated
  `import_migration_inventory.v1.json` was refreshed; import-consolidation and
  effect-sink-inventory suites then passed (36 tests).
- Boundary: this interface deliberately requires an interactive local TTY;
  non-interactive callers fail closed until they have a governed interactive
  approval surface.

## 2026-09-26 — Roles del repositorio tienen owner propio

- `role_factory.create_role()` construye una solicitud `role.definition.create`
  para una familia/nombre exactos y el digest previo del manifiesto. El CLI
  requiere desafío y Permit; el adapter separado valida raíz, enlaces, nombre,
  familia y deriva del manifiesto antes de escribir el rol y su índice.
- La creación no usa `state.write`: ese owner persiste estado de usuario, mientras
  que estas definiciones pertenecen al repositorio. Un fallo de publicación del
  manifiesto retira el archivo de rol creado durante la operación.
- Evidencia en worktree: 9 pruebas focales PASS, compile y diff-check PASS;
  inventario `2327 / 64 runtime-unbound / 0 unclassified`, con
  `--strict-classification` PASS. `--strict-runtime`, suite backend completa y
  revisión independiente permanecen OPEN.

## 2026-09-25 — Toolboxes materializan su carpeta por `state.write`

- `toolsmith.save_toolbox()` ya no hace `mkdir` en paralelo. La escritura JSON
  server-owned crea los padres y su resultado ahora se comprueba; un fallo del
  writer se propaga como error en vez de devolver una ruta no persistida.
- La prueba crea un toolbox con el directorio ausente y confirma que éste se
  materializa durante la delegación al writer. `test_orchestration_tools.py`:
  12 passed; `py_compile`, strict-classification y `git diff --check` PASS.
- Inventario: 2316 sinks / 68 runtime-unbound / 0 sin clasificar. Strict-runtime
  sigue OPEN. El segundo sink de `toolsmith.py` (`create_tool` genera un módulo
  Python) permanece runtime-unbound; no se reclasifica ni se retira.
- Duración estimada del cambio: ~1m neto, excluyendo pruebas y gates.

## 2026-09-25 — Node Control reutiliza writers y guard modular en proceso

- `_load_state()` ya no crea el registro Node Control con `Path.mkdir`; el
  primer `pieces.json` pasa por `state.write`, que materializa su parent.
  `run_modular_guard()` carga `backend/tools/check_modular.py` y llama a
  `run_all()` directamente: el guard es de solo lectura y no requiere un
  segundo proceso/runner.
- La primera prueba detectó que el código previo buscaba el script fuera de
  `backend/` y devolvía siempre R6. Se corrigió la raíz a `backend/tools`;
  el pase final de split + translator fue 31 passed en 13.20s. Las pruebas
  verifican materialización diferida y ausencia de `subprocess.run`.
- Compile, strict-classification y diff-check PASS. Inventario: 2314 sinks /
  66 runtime-unbound / 0 sin clasificar; strict-runtime sigue OPEN. Duración
  neta estimada ~2m45s, excluyendo pruebas y gates.

## 2026-09-25 — DirectoryContext lee Git por `process.inspect`

- `HybridRetriever` ya no ejecuta `git diff --name-only` directamente. Cuando
  pertenece a un `SessionManager`, usa el owner existente `process.inspect`,
  con cwd ligado al workspace activo, `safe.directory` absoluto y argv de
  solo lectura exacto. El SessionManager propaga su identidad a las dos rutas
  de construcción del contexto. Un retriever autónomo sin SessionManager omite
  ese enriquecimiento y no intenta iniciar Git.
- El allowlist Git añadió únicamente `diff --name-only`. Pruebas de
  DirectoryContext + ExecutionGateway: 65 passed en 5.11s; py_compile,
  strict-classification y diff-check PASS. Inventario: 2313 / 65
  runtime-unbound / 0 sin clasificar; strict-runtime continúa OPEN.
- Duración reconstruida del cambio: ~1m neto, excluyendo pruebas y gates.

## 2026-09-25 — La lectura del historial Copilot es de solo lectura

- Decisión: `rl_policies` abre la base existente de historial con URI SQLite
  `mode=ro`; el consumidor solo consulta transiciones y no materializa esa DB.
- Evidencia: `test_rl_contract.py` confirma `uri=True` y `?mode=ro`; scanner y
  RL focales pasan (37 tests). La finding runtime de `database.write` para ese
  callsite desaparece y el inventario queda en 2342 total / 133
  runtime-unbound / 0 unclassified.
- Límite: persisten 30 candidatos `database.write` runtime en KnowledgeBase,
  EmbeddingStore y SessionDB. La autoridad de escritura SQLite sigue abierta.

## 2026-09-25 — El origen de embeddings HTTP viene de la sesión activa

- Decisión: `POST /memory/embeddings/upsert` deriva `source_session` del
  `SessionManager` conectado; ignora cualquier valor enviado en el body. Sin
  sesión activa responde `409` antes de abrir KnowledgeBase o EmbeddingStore.
- Motivo: la procedencia persistida debe reflejar la autoridad de sesión del
  backend, no metadata declarada por el caller.
- Evidencia: prueba HTTP verifica que un `source_session` falsificado se
  sustituye por el ID activo y que ausencia de sesión no materializa stores;
  suite memory/embeddings `9 passed`; compile y `git diff --check` PASS.
- Límite: esto cierra la atribución de esa ruta, pero no su autorización de
  escritura. El handler y los demás mutadores SQLite siguen pendientes de un
  owner `database.write` y del dispatch por ExecutionGateway.

## 2026-09-25 — Persistencia de RL delegada al owner `state.write`

- El modelo BC y la ingesta JSONL de transiciones usan los writers
  `write_text_atomic` y `append_text_durable`, con root `state_root` y
  superficies/sesiones de RL distintas. `rl_policies` ya no crea directorios
  ni materializa esos archivos directamente.
- Evidencia: suites RL contrato/engine `8 passed` en 1.07s; el primer fixture
  de texto contenía `archivo`, que activa por substring la clave `hi` del
  clasificador chat. Se cambió a frase inequívoca; el test final cubre
  transiciones sintetizadas, policy y modo no ejecutable. Compile, strict
  classification y `git diff --check` PASS; inventario `2190 / 111
  runtime-unbound / 0 unclassified`; strict runtime FAIL/OPEN.
- Bloque neto: ~4m46s (~15:19:51–15:24:41 UTC), excluyendo pytest.

## 2026-09-25 — ContextStore difiere la materialización hasta guardar estado

- `ContextStore.__init__` ya no crea `sessions/<sid>` durante la carga. Los
  métodos persistentes existentes usan `atomic_json`/`state.write` y crean
  padres sólo al materializar metadatos, mensajes o timeline. Una carga pura
  de SID inexistente no deja directorio fantasma.
- Evidencia: contrato de conversaciones y persistencia atómica `8 passed`;
  compile, strict classification y `git diff --check` PASS. El primer test
  invocó `get_history`, que crea la proyección conversacional por el writer
  correcto; la prueba quedó ajustada para aislar carga pura. Inventario
  `2192 / 114 runtime-unbound / 0 unclassified`; strict runtime continúa OPEN.
- Bloque neto: ~3m54s (15:15:52–15:19:51 UTC), excluyendo pytest.

## 2026-09-25 — ToolLogger usa el root de sesión y `state.write`

- `SessionManager` liga `ToolLogger` al `state_dir` de la sesión. El logger
  conserva su JSONL y entradas in-memory, pero elimina `mkdir` eager y append
  local; delega cada línea a `append_text_durable` con root y session ID
  explícitos.
- Evidencia: `test_f4_guardrails.py` `29 passed`; Python compile, strict
  classification y `git diff --check` PASS. Inventario `2193 / 115
  runtime-unbound / 0 unclassified`; strict runtime continúa FAIL/OPEN.
- Bloque neto: ~2m00s (15:13:50–15:15:52 UTC), excluyendo 1.67s pytest.

## 2026-09-25 — Neural Bus del AgentGateway delega el append en `state.write`

- `AgentGateway._emit_event` conserva el registro in-memory y la semántica
  append-only de `neural_events.jsonl`; su materialización ahora usa
  `append_text_durable` con root `.bago/state` y sesión estable del gateway.
- Evidencia: prueba focal `1 passed`; los dos primeros intentos de harness
  resolvieron el homónimo de core y después omitieron registrar el módulo
  cargado por ruta en `sys.modules`; ambos problemas se corrigieron y el test
  final pasa. Compile, strict classification y `git diff --check` PASS.
  Inventario: 2195 / 117 runtime-unbound / 0 unclassified; strict runtime
  continúa OPEN.
- Bloque neto: ~5m46s (15:08:03–15:13:50 UTC), excluyendo pytest.

## 2026-09-25 — Los historiales REPL usan el owner `state.write`

- `repl_startup` conserva sólo la conexión de UI: ya no crea directorios ni
  registra los escritores directos de readline o Prompt Toolkit.
- `repl_history.py` preserva la lectura y el formato existentes. Readline
  obtiene sus entradas al salir y reemplaza su archivo a través de
  `state.write`; Prompt Toolkit añade el formato compatible con `FileHistory`
  a través del mismo efecto. Root y sesión se ligan al REPL activo.
- Evidencia: 10 pruebas focales pasaron en 0.79s; el primer fixture de lectura
  falló por CRLF introducido por `Path.write_text` en Windows y se cambió a
  bytes para representar el archivo binario real. Compile, strict
  classification y `git diff --check` PASS. Inventario: 2196 total / 118
  runtime-unbound / 0 sin clasificar. Strict runtime continúa OPEN.
- Bloque neto: ~5m51s (15:02:10–15:08:03 UTC), excluyendo pytest.

## 2026-09-25 — `credential.write` posee la única materialización de SecretStore

- `bago_core.secrets.SecretStore` conserva lectura, resolución de identidad y
  cifrado puro; `set_secret` y `delete_secret` ahora fallan cerrados. El único
  escritor es `CredentialWriteEffectAdapter`, detrás de Permit fuerte
  `credential.write`; valida el target canónico y links/reparse points y hace
  reemplazo atómico o borrado dentro de ese root.
- `CredentialWriteEffectAdapter` ya no delega la autoridad material a métodos
  públicos de SecretStore. La identidad `providers/<provider>/<key>` y el
  fichero canónico no cambian.
- Evidencia final: 10 pruebas de credenciales + 31 de estado legado/inventario
  pasaron; las corridas anteriores también pasaron. Compile, strict
  classification y `git diff --check` PASS. `secrets.py`: cero sinks; los 4
  sinks materiales del adapter clasifican `gateway_owned`. Inventario: 2260 /
  223 runtime-unbound / 0 sin clasificar; strict runtime sigue OPEN.
- Bloque: 8m28s (11:23:45–11:32:57 UTC), excluyendo 44.15s de pytest.

## 2026-09-25 — Code Forge delega el staging temporal al Gateway

- Los efectos de `open_staging_workspace` usan el efecto policy-only
  `workspace.validation.stage` y un único `ValidationStagingEffectAdapter`.
  El owner crea la copia en el temp BAGO canónico, filtra directorios,
  descarta enlaces/reparse points y liga cleanup a una identidad aleatoria que
  solo registra tras crear correctamente el staging. El facade no materializa
  ni elimina archivos y rechaza `parent_dir` fuera del root canónico.
- Evidencia: 42 pruebas focales pasaron en 21.69s; una corrida anterior falló
  en seis tests por jerarquía de destino y alias 8.3 de Windows; ambos defectos
  se corrigieron. Compile, strict classification y `git diff --check` PASS.
  Inventario: 2260 sinks, 227 runtime-unbound y cero sin clasificar; strict
  runtime sigue OPEN.
- Bloque: 13m10s (11:09:29–11:23:45 UTC), excluyendo 66.12s de pytest.

## 2026-09-25 — Structured API logs usan un owner Gateway canónico

- La escritura JSONL y la rotación de `bridge.jsonl` pasan por el único efecto
  server-policy `logging.append` y `StructuredLoggingEffectAdapter`. El logger
  solo admite `logs_root()` canónico; el owner valida target, operación,
  registro JSON, tamaño y backups antes de crear, rotar o añadir archivos.
- El logger ya no crea directorios ni ejecuta append/rename/unlink. Conserva
  su semántica best-effort si el Gateway no puede registrar la entrada.
- Evidencia: 30 pruebas focales pasaron en 20.79s; una corrida inicial falló
  por expectativa del registro en 1.16.0 y se corrigió a 1.17.0. Compile,
  strict classification y `git diff --check` PASS. Inventario: 2252 sinks,
  233 runtime-unbound, cero sin clasificar; strict runtime sigue OPEN.
- Bloque: 6m36s (11:02:10–11:09:29 UTC), excluyendo 42.52s de pytest.

## 2026-09-25 — Enrutar la materialización del mirror de sesión

- Decisión: el mirror automático de sesión usa el efecto policy-only
  `workspace.mirror.prepare`. `SessionManager` conserva la preparación y la
  proyección del resultado; `SessionWorkspaceMirrorEffectAdapter` es owner de
  `rmtree/copytree/mkdir` y vuelve a validar identidad de sesión, raíz activa,
  destino canónico y política de espacio/tamaño antes de materializar.
- La policy authority es propia de esta copia temporal de sesión. El efecto no
  cubre `attach_context`, `sync_workspace_mirror` ni el `state_dir.mkdir`, que
  permanecen visibles como runtime sinks y requieren su propia autoridad.
- Evidencia: mirror/gateway/workspace/canonical-contract `60 passed`; safety
  suite de constructores/callers final `260 passed, 1 skipped, 8 subtests` tras
  corregir normalización Windows de rutas largas; scanner
  `2108` findings / `433` runtime-unbound / `0` sin clasificar.
- Estado: `EXECUTED` en worktree sucio. `--strict-runtime` sigue abierto; no es
  cierre de `SessionManager` ni de la unicidad global.

## 2026-09-25 — Enrutar `PlanEngine.run_command` por `process.execute`

- Decisión: `ExecutionClaimStore` construye una clave de recurso por sesión,
  cwd y operación de proceso; `ExecutionGateway.execute_nested()` la vuelve a
  calcular y valida la claim antes del adapter. El adapter acepta el Permit
  directo exacto o el contexto hijo que el gateway valida bajo `plan.execute`.
- El parent compuesto hereda el máximo riesgo de los child effects declarados;
  el comando y sus argumentos quedan ligados al fingerprint del workflow y a
  la claim de ejecución. `shlex` separa argv y la ejecución usa `shell=False`.
- Evidencia focal: pipeline/gateway/inventory `68 passed`; scanner clasifica el
  sink `subprocess.run` dentro del adapter como `gateway_adapter`. El inventario
  global sigue en `2104 / 437 runtime_unbound`; strict runtime continúa abierto.
- La contract `backend/docs/contracts/execution_claims.v1.md` documenta esta
  clave de claim y separa coordinación de autorización. El parent Permit y el
  adapter siguen siendo autoridad; las claims no autorizan efectos ni cubren
  callers directos fuera del pipeline.
- Límite: `install-v4.ps1` y los demás callers directos de Electron/Python aún
  no están migrados. No se extiende el claim de esta tranche a ellos.

## 2026-09-25 — Registrar owner para `process.execute`

- Decisión: el default `ExecutionGateway` registra
  `ProcessExecutionEffectAdapter`; ejecuta argv con `shell=False`, resuelve
  executable, limita el cwd a raíces activas del workspace y exige un Permit
  consumido ligado a efecto, sesión y fingerprint antes de `subprocess.run`.
- La prueba positiva ejecuta un proceso inocuo dentro del workspace; la
  negativa demuestra que un cwd externo queda bloqueado antes del spawn. El
  inventario conserva el sink del adapter como `gateway_adapter`.
- Evidencia: `test_execution_gateway_v2.py` `43 passed`; la classification
  global sigue PASS y runtime sigue OPEN con `437` sinks. Este owner aún no
  migra callers de Electron, scripts ni otros runners.
- Estado: `EXECUTED`; sin claim `VERIFIED`/`VALIDATED` global.

## 2026-09-25 — Mantener los fixtures de sinceridad fuera del runtime

- Decisión: los cinco escenarios del self-test de `sincerity_detector.py`
  viven en `backend/tests/test_sincerity_detector.py` y usan `tmp_path`. El
  módulo de producción ya no conserva una ruta CLI que cree/borre fixtures.
- La separación elimina ocho sinks runtime que solo existían por los fixtures;
  el detector y sus reglas de análisis no cambian.
- Evidencia focal: `5 passed`; inventario global `2103` total / `437`
  runtime-unbound; cero clasificaciones scope/binding sin resolver. El gate
  strict-runtime sigue abierto.
- Estado: cambio `EXECUTED` en worktree sucio; candidato final y revisión
  independiente aún abiertos.

## 2026-09-25 — Encaminar `/update` por el actualizador canónico

- Decisión: el comando de chat `/update` prepara descarga/verificación con
  `update_manager`; instalar y reiniciar queda detrás del challenge/approval
  del backend y la confirmación visible de Sistema → Actualización de BAGO.
- La clasificación de `backend/install-remote.ps1` permanece
  `runtime_authority / runtime_unbound`: Electron preload y el manager legado
  todavía exponen una ruta de instalación. No se excluye como administración
  externa ni se declara cerrada hasta migrar o demostrar que esa ruta no puede
  ejecutar desde BAGO.
- Evidencia focal: chat e inventario `17 passed`; inventario total `2109`,
  `445 runtime_unbound`, cero scope/binding sin clasificar; strict
  classification PASS y strict runtime FAIL/OPEN.
- Estado: `EXECUTED` en worktree sucio; suite backend completa, candidato
  comprometido y review final independiente permanecen abiertos.

## 2026-09-25 — Encaminar descarga y aplicación de releases por ExecutionGateway

- Decisión: las lecturas de metadata/checksum/payload usan el transporte
  `release_metadata` / `release_asset_download`; la materialización del ZIP
  pertenece a `ReleaseDownloadEffectAdapter` y deriva su caché desde la
  política del servidor. El caller solo aporta URL, digest, tamaño y nombre
  validables; no el destino absoluto.
- Decisión: aplicar una release usa `system.update.apply` con target que liga
  bundle y helper por SHA-256, versión, instalación, estado y proceso. El
  `SystemUpdateApplyEffectAdapter` revalida el descriptor después de consumir
  un Permit de interacción directa y es el único owner del lanzamiento del
  helper. El endpoint y el cliente React comparten challenge → approve → execute.
- Seguridad: URLs de assets y redirects quedan restringidos a HTTPS y hosts
  aprobados; rutas de destino, symlinks, tamaño y digest se comprueban antes de
  materializar. El frontend conserva su acción explícita de instalación.
- Evidencia focal: backend release/gateway/LLM `94 passed`; frontend
  `api-client.test.ts` `21 passed`; `typecheck`, producción Vite (`123 modules`)
  y `py_compile` pasan.
- Inventario global: `2112` sinks totales, `463` runtime-unbound y `0`
  clasificaciones scope/binding abiertas. `--strict-classification` pasa;
  `--strict-runtime` sigue FAIL/OPEN (exit `1`).
- Límite: no declara unicidad global. Quedan `463` sinks runtime, incluido el
  camino de instalación, Electron y persistencia de sesión; suite backend
  completa y revisión independiente permanecen pendientes.
- Estado: esta tranche queda `EXECUTED`; el gate global sigue abierto y no se
  afirma `VERIFIED` ni `VALIDATED`.

## 2026-09-25 — Cerrar el bypass REPL y blindar materializadores de proyecto

- Decisión: `project_memory.py` conserva sus sinks en el inventario y como
  implementación materializadora del único `ProjectWriteEffectAdapter`; cada
  entrypoint público init/link/seed/demo exige autorización consumida,
  fingerprint de `project.write` y coincidencia exacta de operación/target
  antes de tocar disco.
- Decisión: el asistente REPL ya no invoca `init_project`/`link_project`
  directamente; delega a los entrypoints CLI, que ejecutan `project.write`.
  Los self-tests de la herramienta hacen lo mismo y usan un directorio temporal
  administrado por `TemporaryDirectory`.
- Evidencia de unicidad local: las 14 findings del módulo siguen presentes y
  quedan ligadas como `gateway_adapter`; una prueba AST exige que las cuatro
  llamadas productivas a sus materializadores solo aparezcan desde
  `execution_adapters/project.py`. La prueba negativa demuestra que llamar al
  materializador sin autoridad se bloquea antes de crear archivos.
- Evidencia focal: proyecto/inventario/seed/menú `34 passed`; self-test CLI
  `8/8`; `py_compile` y `git diff --check` pasan.
- Inventario global: `2110` findings, `446` runtime-unbound y cero
  clasificaciones incompletas. `--strict-classification` pasa;
  `--strict-runtime` continúa FAIL/OPEN.
- Límite/estado: se cierra solo la familia `project_memory`; instaladores,
  Electron, SessionManager y el resto de los `446` sinks siguen pendientes.
  Esta tranche queda `EXECUTED`, sin declarar unicidad global, `VERIFIED` ni
  `VALIDATED`.

## 2026-09-25 — Unificar proyecciones de workspace y selección de claims

- Decisión: el snapshot estable de identidad para `workspace.bind` lo define
  `WorkspaceBinding.execution_descriptor()` en `workspace_binding.py`; el
  adapter del gateway consume esa proyección para crear y revalidar el digest.
  `to_dict()` conserva la proyección completa del estado observado.
- Decisión: `execution_claims.py` resuelve y cachea el store SQLite por el
  `state_root` confiable; `ExecutionGateway` conserva solo el override inyectado
  y delega allí la selección por defecto. El ledger de operaciones sigue en su
  artefacto y las autoridades de binding/Permit siguen separadas.
- Decisión: separar el contrato compartido de adapters en
  `execution_adapter_contract.py` y sus implementaciones por dominio en
  `execution_adapters/` (filesystem, workspace, session state, network, plan,
  project, credentials, capability y delegation). El gateway mantiene el único
  registro, consumo de Permit y despacho; los exports existentes se conservan.
- Inventario: el scanner reconoce las clases `*EffectAdapter` en esos módulos
  como `gateway_owned`; los sinks permanecen contados y no se crea una segunda
  vía de ejecución.
- Límite: este refactor no certifica unicidad global de todos los sinks ni
  `VALIDATED`.
- Evidencia focal: `python -m pytest backend/tests/test_execution_claims.py
  backend/tests/test_execution_gateway_v2.py
  backend/tests/test_workspace_persist_activation.py
  backend/tests/test_effect_sink_inventory.py -q` -> `64 passed, 1 skipped`;
  suite completa `python -m pytest backend/tests -q` -> `1342 passed, 3
  skipped, 198 subtests passed`. `py_compile` y `git diff --check` pasan.
- Inventory `--strict-classification`: PASS, `0` scope/binding sin clasificar;
  `478` runtime-unbound permanecen y mantienen abierta la unicidad global.
- Estado: `EXECUTED`; la proyección y la selección de store quedan verificadas
  dentro del gate focal, sin afirmar unicidad global ni `VALIDATED`.

## 2026-09-24 — Registrar y reconciliar escrituras gobernadas ambiguas

- Decisión: cerrar la brecha local con `execution_operations` en la misma base
  SQLite canónica de claims. Cada `filesystem.write` durable prepara una fila
  `PENDING` ligada a operation key, recurso canónico y digest del contenido;
  tras el receipt del sink se marca `COMMITTED` con el payload del receipt.
- Recuperación: solo una nueva autorización puede reanudar un outcome sin
  resolver (`PENDING` o `OUTCOME_UNKNOWN`) cuando existe una fila durable con
  la misma key, recurso y digest. Si el ledger está `PENDING`, reaplica el
  desired state idempotente y guarda el receipt; si está `COMMITTED`, repara
  el outcome sin repetir el efecto. Si falta o no coincide el registro,
  permanece fail-closed.
- Límite: el ledger y el replace filesystem no son una transacción atómica;
  se soporta recuperación at-least-once por contenido, no exactly-once. El
  adapter filesystem no tiene fencing distribuido atómico: PostgreSQL sigue
  bloqueando el efecto material; sus pruebas de integración continúan
  `NOT_RUN` sin DSN/driver.
- Implementación: `SQLiteExecutionOperationStore` mantiene el ledger durable
  desde `execution_operations.py`; `SQLiteExecutionClaimStore` conserva la
  autoridad sobre claims y fencing. `ExecutionGateway` delega la normalización
  de claims entre imports a `execution_claims.py`; el store seleccionado
  revalida su identidad canónica antes del efecto.
- Evidencia focal candidate-bound: `python .bago/bin/bago.py verify -- python
  -m pytest backend/tests/test_execution_claims.py
  backend/tests/test_execution_operations.py
  backend/tests/test_governed_work_pipeline.py
  backend/tests/test_execution_gateway_v2.py
  backend/tests/test_claim_ledger_split.py
  backend/tests/test_evidence_claim_authority.py
  backend/tests/test_claims_docs_sync.py -q` -> `76 passed, 1 skipped, 9
  subtests passed`.
- Estado: `EXECUTED / SQLITE_LOCAL_SLICE_WITH_WRITE_RECONCILIATION`; PostgreSQL
  integration remains `NOT_RUN`, distributed filesystem execution remains
  fail-closed, and global `VERIFIED`/`VALIDATED` are not claimed.

## 2026-09-24 — Introducir contrato acotado de Execution Claims para 04

- Decisión: desacoplar la coordinación de recursos de 04 mediante
  `ExecutionClaimStore`, con `SQLiteExecutionClaimStore` en el runtime de un
  `SessionManager` y `InMemoryExecutionClaimStore` para harnesses sin estado
  canónico o stores inyectados. SQLite persiste owner, lease, status y
  generación fencing por recurso para los hijos gobernados de
  `filesystem.read` y `filesystem.write`.
- Frontera: el gateway valida identidad, recurso, operación, claim y token
  antes del adapter y mantiene una guarda por recurso durante el efecto local.
  El lock por plan sigue existiendo para proteger el estado mutable de
  PlanEngine; el claim no sustituye autorización 03A, Permit, DelegationGrant
  ni receipt.
- Frontera: SQLite coordina procesos de una máquina que comparten el mismo
  archivo de estado. `execute_if_valid` conserva una transacción de escritura
  durante el callback para no transferir el lease durante el efecto; por el
  escritor único de SQLite esto serializa los callbacks de ese DB incluso con
  recursos distintos. No es coordinación multimáquina ni atomicidad entre DB
  y efecto de filesystem; no se afirma exactly-once ni idempotencia durable.
- Evolución: la etapa SQLite sustituye el rechazo previo de persistencia local,
  pero conserva como futuro el store servidor, el fencing validado por cada
  sink distribuido y la recuperación idempotente.
- Distinción: `backend/bago_core/claim_storage.py` permanece como ledger de
  afirmaciones/evidencias y no implementa coordinación de ejecución.
- Implementación: `backend/.bago/core/execution_claims.py`, integración en
  `governed_work_pipeline.py` y `ExecutionGateway`, y contrato
  `backend/docs/contracts/execution_claims.v1.md`.
- Evidencia focal candidate-bound: gate por `python .bago/bin/bago.py verify --`
  sobre claims SQLite, pipeline, gateway y el ledger de evidencia existente:
  `73 passed, 9 subtests passed`; `py_compile` y `git diff --check` pasan.
- Estado: `EXECUTED / SQLITE_LOCAL_SLICE`; no equivale a coordinación
  multimáquina, idempotencia exactly-once, `VERIFIED` global ni `VALIDATED`.

## 2026-09-24 — Preparar coordinación PostgreSQL sin abrir sinks sin fencing

- Decisión: añadir `PostgresExecutionClaimStore` como adapter explícito y
  opcional de claims compartidos, usando reloj PostgreSQL, adquisición atómica
  por recurso y row lock durante el callback. No se convierte en el default;
  el runtime sigue en SQLite local.
- Seguridad: el pipeline bloquea el efecto material si el store exige fencing
  distribuido y el adapter no declara soporte atómico de fencing en el sink.
  El filesystem actual no declara ese soporte, así que PostgreSQL no habilita
  todavía ejecución filesystem entre máquinas.
- Recuperación: `filesystem.write` usa temporal + flush + replace atómico y
  repetir el mismo contenido no vuelve a escribirlo. PostgreSQL y filesystem
  siguen siendo transacciones separadas; no se afirma exactly-once. La
  recuperación durable requiere operation ledger/reconciliación e idempotencia
  del sink.
- Evidencia: el test PostgreSQL requiere `BAGO_TEST_POSTGRES_DSN` y `psycopg`;
  ambos están ausentes en este entorno, por tanto ese gate queda `NOT_RUN`.
  SQLite/fencing local se vuelve a cubrir en el gate focal de esta tarea.
- Estado: `EXECUTED / POSTGRES_ADAPTER_NOT_RUN`; no implica coordinación
  multimáquina validada, efecto filesystem distribuido, `VERIFIED` global ni
  `VALIDATED`.

## 2026-09-23 — Wave B2: cerrar workspace.bind en /workspace/persist

- Decisión: cerrar primero la superficie `POST /workspace/persist` como el
  único lifecycle de `workspace.bind` para este corte. El handler construye la
  request, pero no puede llamar a `rebind_project_root()`, `save()` ni publicar
  `last_workspace.json`; esas tres fases pertenecen al adapter server-owned.
- Invariantes: challenge y approve no mutan sesión ni filesystem; el Permit
  liga effect, sesión, root canónico, identidad, scope y digest de binding;
  el adapter revalida todo dentro de un lock por sesión inmediatamente antes
  del rebind; un target inválido o cambiado bloquea antes de rebind/save;
  root ya activo es idempotente; la persistencia exige receipt y distingue
  JSON de sesión, índice SQLite y `last_workspace`.
- Implementación: `WorkspaceBindEffectAdapter` registrado en
  `ExecutionGateway`; `/workspace/persist` usa challenge → approve → Permit →
  execute; `atomic_json` devuelve receipts server-owned y `SessionManager.save`
  expone el estado de JSON/SQLite. La UI elimina el persist automático
  silencioso y el botón Persistir usa confirmación visible más el mismo
  lifecycle. Los callers `/project` y TTY siguen fuera de este corte y quedan
  para `project.write`.
- Evidencia candidate-bound sobre `fa7b1727216562fc51591b92e8d777b3ddd51a3f`:
  backend B2 ampliado `47 passed`; suite backend completa `1260 passed, 2
  skipped, 198 subtests passed` en `225.85s`; frontend cliente/
  ControlPlane/navegación `35 passed`; typecheck y build frontend PASS (`123`
  módulos); compile y `git diff --check` PASS. La inventory queda separada:
  `2104` findings, `473` runtime-unbound, `243` runtime high-confidence y `0`
  scope/binding unclassified; `--strict-classification` PASS y
  `--strict-runtime` continúa FAIL/OPEN por el backlog global.
- Estado: `EXECUTED / SCOPED`. No se promueve a `VERIFIED`/`VALIDATED` hasta
  repetir las gates sobre el commit final y completar la revisión independiente.

## 2026-09-23 — Iniciar Wave B1 con el borrado del override de modelo

- Decisión: abrir Wave B con el corte mínimo y aislable `state.delete` del
  override de modelo de sesión. El handler conserva challenge → approve →
  Permit de un solo uso → ejecución, y el borrado material queda únicamente
  en un adapter server-owned del `ExecutionGateway`.
- Invariantes: la operación queda limitada a la sesión activa, a su
  `state_root` autoritativo y al fichero exacto `.bago_session_model.json`;
  challenge/approve no mutan manager ni disco; el cambio al modelo automático
  ocurre antes del borrado; un fallo de ese cambio conserva el override; el
  evento solo se emite después del receipt de borrado.
- Implementación: `StateDeleteEffectAdapter`, ruta
  `/router/session-model`, cliente React y confirmación visible de UI. No se
  toca Scheduler/PlanEngine ni se mezclan todavía project/workspace/credential.
- Evidencia de ejecución: tests backend focales `30 passed`; frontend focal
  `34 passed`, typecheck PASS y build PASS. La inventory actual queda en
  `2099` findings, `473` runtime-unbound (`243` high-confidence runtime),
  `0` scope/binding unclassified; `--strict-classification` pasa y
  `--strict-runtime` permanece abierto con exit `1`.
- Estado: `EXECUTED / SCOPED`; el cierre global sigue sin promoverse a
  `VERIFIED`/`VALIDATED` hasta obtener gates sobre el commit final y revisión
  independiente. Wave B1 no cierra las restantes waves B-D.

## 2026-09-23 — Ejecutar primera oleada de migración de sinks runtime

- Decisión: ejecutar el plan de migración por ondas empezando por la familia
  interna de persistencia y por los transportes Python que ya forman parte del
  runtime activo. Cada efecto migrado debe resolver autoridad antes del efecto,
  usar un adapter server-owned registrado y conservar una prueba negativa de
  bloqueo previo.
- Implementación: `ServerStateEffectAdapter` centraliza los efectos de estado
  (`state.write`, `config.write`, `memory.write`, `agent.definition.write`), y
  `NetworkReadEffectAdapter` centraliza los transportes clasificados de
  provider, probe y discovery. Los helpers no materializan efectos por sí
  mismos ni aceptan callables del caller.
- Evidencia: la inventory pasa de `2201/587` findings/runtime-unbound a
  `2092/474`, con `0` hallazgos sin scope/binding; `--strict-classification`
  pasa. La suite focalizada da `99 passed` y la suite backend da
  `1251 passed, 2 skipped, 198 subtests passed`.
- Límite: `--strict-runtime` sigue abierto con `474` runtime-unbound (`305`
  filesystem.write, `78` filesystem.delete, `79` process.execute y `12`
  network.read de update/installer). Las waves B-D siguen abiertas; el ledger
  de autorización permanece `authority_internal`. Estado de esta decisión:
  `EXECUTED / SCOPED`, sin promoción global a `VERIFIED` o `VALIDATED` y sin
  PASS independiente todavía.

## 2026-09-23 — Reparar la evidencia de inventory de effect sinks

- Resultado: `effect_sink_inventory.py` conserva todos los findings y reconoce
  los sinks materializados dentro de adapters server-owned del
  `ExecutionGateway` como `gateway_owned`.
- Alcance: `filesystem_effects.py`, las clases concretas `*EffectAdapter` del
  gateway y los módulos de implementación `execution_adapters/`; el ledger de
  autorización continúa siendo `authority_internal`.
- No se excluyen tests, tooling, release trees ni sinks legacy para maquillar
  el contador. `handlers_github` y las demás superficies no migradas siguen
  `unbound` y hacen fallar `--strict`.
- La salida añade `scope`, `binding_class` y `binding_reason` por finding.
  `--strict-classification` pasa con `unclassified_scope_sinks=0` y
  `unclassified_binding_sinks=0`; `--strict-runtime` sigue fallando con
  `runtime_unbound_sinks=587`.
- Estado: inventory `CLASSIFIED / EXECUTED`; `UNBOUND_EFFECT_SINKS = 0` y
  `UNIQUE_EXECUTION_BOUNDARY` siguen abiertos hasta migrar las superficies
  runtime restantes. La clasificación cerrada no se presenta como gateway
  global.

## 2026-09-23 — Ejecutar integración bounded 04-FIX2 en ExecutionGateway

- Resultado: el sidecar runtime `bago.governed-work-pipeline/v0.2-FIX2` queda
  `EXECUTED` y `CONNECTED_SCOPED` con Scheduler y PlanEngine.
- Owners: 03A conserva challenge, decisión, Permit, DelegationGrant, consumo y
  revocación; 04 solo coordina budget/workflow/step/outcome y conserva
  referencias de autoridad.
- Boundaries: `plan.execute`, `filesystem.read` y `filesystem.write` tienen
  adapters server-owned; cada child material vuelve por `ExecutionGateway`.
  `process.execute` sigue sin adapter de plan y se bloquea antes de consumir
  presupuesto.
- Invariantes ejecutados: presupuesto monotónico con remaining/state,
  workflow/version/fingerprints, idempotencia y replay, `OUTCOME_UNKNOWN`,
  referencias delegated y dispatch nested con contexto gateway-owned.
- Evidencia: `.bago/audits/04-fix2-runtime-integration-20260923.md`,
  gate bounded `96 passed, 142 subtests passed`, suite backend completa
  `1240 passed, 2 skipped, 198 subtests passed`, compile PASS y
  `git diff --check` PASS.
- Límite: el candidato sigue dirty y no tiene verificación independiente en
  este cierre; el review queda `OPEN / EXECUTED` y no se promueve a
  `VERIFIED`/`VALIDATED`. La inventory global de sinks permanece separada.

## 2026-09-23 — Reconciliar identidad del paquete congelado de 04-FIX2

- Resultado: la identidad del baseline queda reconciliada localmente sin
  modificar sus bytes.
- Artefacto autoritativo local: `C:\Users\AMTEC_Terminal_1º\Documents\ARQUITECTURA_DE_CONTEXTO\BAGO_ARCONTEXT\RED_RAZONAMIENTO_LR_FROZEN_OPEN_2026-09-21.zip`.
- SHA-256 del paquete: `e50b310f2d9775979cce813f27fd92640cb4380290204b2da510d38653da60db`.
- SHA-256 del contrato 04 incluido:
  `5db2b02ce92b0618cc51559e275c7d12f8d297ce36831213bd2789a4b5288146`.
- Verificación: las siete entradas de `SHA256SUMS.txt` del paquete coinciden
  con los bytes contenidos; el `PACKAGE_MANIFEST.md` describe el baseline LR
  congelado.
- Referencia superseded: el hash anterior
  `748556bc39e5c41bec642d9812d31fc5fe78a436a9d8734931c1f975eb2a3d68`
  pertenece al bundle distinto
  `output/BAGO-causal-kernel-audit-20260921-a575291c.zip`, cuyo contrato
  interno es `bago.third-party-remediation.v1` y cuyo candidato es `a575291c`.
- Límite: la review externa conserva el hash histórico hasta que su autor la
  reemita; esta decisión local no modifica el paquete ni certifica 04-FIX2.
- Estado: la identidad está `RECONCILED_LOCALLY`; el review 04-FIX2 queda
  `OPEN / EXECUTED` con integración runtime `CONNECTED_SCOPED`, pendiente de
  verificación independiente.

## 2026-09-21 — Open bounded 04-FIX2 review

- Decision: open a formal bounded review of 04_GOVERNED_WORK_PIPELINE_CONTRACT
  v0.2-FIX1 as 04-FIX2 review.
- Authority: explicit current owner instruction to choose and execute the
  canonical opening option after the prepared gap matrix.
- Baseline: RED_RAZONAMIENTO_LR_FROZEN_OPEN_2026-09-21; package SHA-256
  748556bc39e5c41bec642d9812d31fc5fe78a436a9d8734931c1f975eb2a3d68;
  contract SHA-256
  5db2b02ce92b0618cc51559e275c7d12f8d297ce36831213bd2789a4b5288146.
- Scope: GWP-02-01 pipeline budget envelope; GWP-02-02 workflow
  version/fingerprint binding; GWP-02-03 pipeline/step idempotency; and
  GWP-02-04 delegated-authority references without authority inheritance.
- Excluded: changes to 01, 02, 03A or 03; STRONG_HUMAN_IDENTITY_PROOF as a
  04 field; PersistentCognitiveState; and any contract 05.
- Boundary: the frozen package, manifest, OPEN_CONTRACTS_STATUS and SHA256SUMS
  remain immutable. This is a sidecar review, not a rewrite of the baseline.
- Lifecycle: review OPEN; proposed contract changes PREPARED; no VERIFIED or
  VALIDATED claim is made.
- Evidence: RED_RAZONAMIENTO_LR_04_GAP_MATRIX_PREPARED_2026-09-21.md and
  RED_RAZONAMIENTO_LR_04_FIX2_REVIEW_OPEN_2026-09-21.md.
- Closure: explicit field and authority definitions, negative and concurrency
  retests for all four gaps, fresh candidate-bound evidence, and a separate
  verification decision.
- Reversibility: close the review without modifying the frozen baseline; no
  future contract is implied by this opening.

## 2026-08-30 — Adopt BAGOx v1.3-RC1-FIX2 Codex overlay

- Decision: adopt the stable Codex behavioral projection of `BAGOx Behavior Package v1.3-RC1-FIX2` as the BAGO repository overlay.
- Authority/provenance: external package status `ACTIVE · CANON`, manifest SHA-256 `f916e385ba55cff4b27dd9696c42b3d22dbb83ad00595572e77385766c9fb3eb`.
- Scope: `AGENTS.md`, the overlay verifier, and its contract fixture only.
- Excluded: BAGO runtime, application canon, persistent state, schemas, templates, hooks, and BAGOx-only state mechanisms.
- Verification: candidate-bound BAGO overlay gate passes on the adopted candidate; the repository-wide state remains subject to its own validation contract.

## 2026-09-03 — Adopt the single-maintainer governance exception

- Decision: the repository operates with one maintainer, so the default
  independent-review requirement is not satisfiable. `main` retains pull
  requests, enforced administrators, linear history, resolved conversations
  and the canonical `validate` check, while requiring zero approvals.
- Authority: explicit owner instruction selecting the previously presented
  single-maintainer mode.
- Receipt boundary: protected promotions require
  `bago.single-maintainer.github.v1`, generated by the configured owner while
  authenticated to GitHub and holding `admin` permission. The consumer
  re-queries GitHub policy, identity, PR state/base/SHA and package binding.
  This is an auditable exception, never independent review.
- Reversibility: teams with an eligible second reviewer restore the default via
  `pwsh backend/scripts/apply_branch_protection.ps1`.

## 2026-09-25 — Gate workspace mirror sync before copying into the project

- Decision: `/project/sync` must be an explicit `workspace.mirror.sync` effect
  dispatched by `ExecutionGateway`. Challenge, approval and one-time Permit
  bind the currently active session mirror and project workspace; a changed
  identity or target blocks before the first copy.
- Ownership: `WorkspaceMirrorSyncEffectAdapter` owns materialization and reuses
  the SessionManager mirror-exclusion policy. `SessionManager.sync_workspace_mirror`
  and the generic `/project sync` command are fail-closed compatibility
  surfaces. The React activation path asks for visible confirmation before
  invoking the authorized endpoint.
- Evidence: gateway negative-target test and HTTP challenge/approval/execute
  test pass; backend focal gate `68 passed` plus final adapter/HTTP retest `3 passed`, frontend client `22 passed`,
  typecheck PASS. Inventory is `2114` findings / `430` runtime-unbound with
  zero unclassified scope/binding; strict classification PASS, strict runtime
  FAIL/OPEN.
- Boundary: this tranche is `EXECUTED / SCOPED`; final full backend suite,
  committed candidate, `--strict-runtime` closure and independent final review
  remain required. No global `VERIFIED` or `VALIDATED` claim.

## 2026-09-25 — Authorize context bundle attachment through ExecutionGateway

- Decision: attaching files or folders to session context is the explicit
  `workspace.context.attach` effect; the generic `/context attach` command cannot
  materialize a bundle directly.
- Owner: `ContextAttachEffectAdapter` binds the active session workspace,
  canonical context destination, selected roots and selected content digest.
  It requires a Permit bound to that exact operation, rechecks before and after
  the copy, excludes symlinks using the SessionManager policy, stages the
  bundle and publishes it atomically.
- Surface: `/context/attach` implements challenge → approve → execute. React
  asks for visible confirmation, keeps a selected path as one data value (so
  spaces are preserved), and invokes that endpoint. Direct manager and generic
  command paths fail closed.
- Evidence: adapter/API pre-effect gate `5 passed`; route metadata `22 passed,
  143 subtests`; frontend API/context tests `30 passed`; typecheck, compile,
  registry JSON and diff checks PASS. Inventory `2120` total / `425`
  runtime-unbound; strict classification PASS, strict runtime FAIL/OPEN.
- Boundary: this is `EXECUTED / SCOPED`. Full backend suite, committed
  candidate, strict-runtime closure and independent final review remain open.

## 2026-09-25 — Bind detached release update helper to consumed Permit

- Decision: the detached `apply_release_update.ps1` is only an implementation
  detail of `system.update.apply`; it must not materialize an update from a
  direct invocation.
- Authority: `SystemUpdateApplyEffectAdapter` consumes the strong direct-user
  Permit, revalidates the prepared target, writes a one-use helper ticket and
  launches the exact helper whose SHA-256 is bound into the request. The helper
  resolves the canonical authorization ledger, verifies the consumed Permit,
  decision, proof and executed request target, checks its own hash, and claims
  the ticket before staging, deleting, replacing or launching anything.
- Verification: helper/application tests pass `6`; they cover Permit-bound
  launch, successful replacement, missing/forged ticket denial before any
  effect, and changed-target denial. Inventory retains all helper sinks as
  gateway-owned implementation findings; total `2131`, runtime-unbound `408`,
  strict classification PASS, strict runtime FAIL/OPEN.
- Boundary: the global goal remains `EXECUTED / OPEN`; full backend suite,
  committed candidate, strict-runtime zero and independent final review remain
  outstanding.

## 2026-09-25 — Keep debt-guard fixtures out of the runtime tool

- Decision: the debt guard CLI no longer contains a self-test implementation
  that writes temporary fixture files; pytest owns that test responsibility.
- Surface: `debt_guard --test` now points maintainers to
  `backend/tests/test_debt_guard.py` and performs no filesystem mutation.
- Evidence: the dedicated pytest module passes `3`; classification remains
  complete and runtime-unbound findings moved from `408` to `403` while the
  five fixture sinks remain visible in test scope. The seven real guard
  configuration, Git and hook sinks remain runtime-unbound.
- Boundary: scoped inventory progress only. Global strict runtime, full
  backend suite, committed candidate and independent review remain open.

## 2026-09-25 — Route Electron release verification and staging through ExecutionGateway

- Decision: Electron release jobs must not run GPG or `Expand-Archive` in the
  job manager. The local release-job API constructs fixed server-owned requests
  for `release.signature.verify` and `release.bundle.stage`; the registered
  adapters are the only process/extraction owners for those operations.
- Identity: Electron calls the existing local BAGO API bridge. The handlers
  bind the BAGO release-manager principal and server surface; adapters require
  server-policy authorization and confine inputs/destinations to the canonical
  per-user release-job cache and staging roots. No manager-owned Permit or
  second authorization ledger is introduced.
- Pre-effect checks: signature inputs must be existing non-symlink cache files;
  ZIP entries are fully preflighted for traversal, links, collisions, entry
  count and expanded size before staging writes. Extraction publishes a
  completed temporary tree and restores the prior stage if publication fails.
- Evidence: gateway/adapter/route tests `37 passed, 145 subtests`; Electron
  release-job regression PASS; JS syntax, Python compile and diff checks PASS.
  Inventory is `2155` sinks / `400` runtime-unbound / `0` unclassified;
  strict classification PASS and strict runtime FAIL/OPEN (exit `1`). The manager still has
  direct job/cache/rollback filesystem sinks, installer spawn and taskkill.
- Boundary: only signature verification and archive staging moved in this
  tranche. Full backend suite, commit, strict-runtime zero and independent
  review remain open.

## 2026-09-25 — Route Electron release-job state and log writes through ExecutionGateway

- Decision: the Electron release manager no longer creates or replaces job
  state JSON or appends job logs directly. It calls fixed local API routes for
  `release.job.persist` and `release.job.log.append`; each request is dispatched
  through a registered server-policy adapter.
- Target binding: adapters derive `jobs/<job_id>.json` and
  `logs/<job_id>.jsonl` under the canonical per-user release-job root. They
  reject mismatched state IDs, invalid job IDs, symlinked paths, invalid log
  levels, and oversized records before materialization. State replacement is
  atomic; the manager serializes state/log commits per job and emits changed
  events only after persistence receipts return.
- Evidence: focused gateway/API/registry/security tests `57 passed, 147
  subtests`; Electron manager cancel/resume/install/rollback/delete regression
  PASS; crash-boundary resume regression PASS; JavaScript syntax, Python
  compile and diff checks PASS. Inventory: `2168` sinks, `396`
  runtime-unbound, `0` unclassified; strict classification PASS and strict
  runtime FAIL/OPEN (exit `1`).
- Boundary: archive/delete and staging/cache/download/install/rollback effects
  remain open in the manager. This is scoped progress; the full backend suite,
  commit, strict-runtime zero and independent review remain outstanding.

## 2026-09-25 — Route terminal Electron release-job archival through the explicit gateway

- Decision: `release.job.archive` is a canonical explicit effect. Electron's
  job manager no longer creates archive directories, writes archive manifests,
  or moves active state/log/staging paths itself.
- Authority and identity: the renderer requests archival only after the main
  process shows a native confirmation naming the exact job ID. The fixed API
  handler builds the request; the existing `AuthorizationBoundary` challenge,
  direct-interaction approval, one-time Permit and `ExecutionGateway` dispatch
  remain the sole authority path.
- Pre-effect checks: the Permit fingerprint binds the job ID, persisted-state
  SHA-256 and archive timestamp. The adapter verifies direct-user provenance,
  consumed decision/effect/fingerprint, symlink-safe canonical paths, exact
  persisted identity, terminal state and absence of an existing archive before
  its first material write. If a later move fails, it restores already-moved
  paths; if rollback itself fails, it preserves partial recovery data and
  reports the archive path instead of deleting moved data.
- Evidence: gateway/API/registry/route tests `38 passed, 148 subtests`; Electron
  release manager, persisted-restart and IPC confirmation regressions PASS;
  JS syntax and diff checks PASS. Inventory is `2178` sinks / `389`
  runtime-unbound / `0` unclassified; strict classification PASS and strict
  runtime FAIL/OPEN (exit `1`). The manager still has 10 direct runtime sinks
  for cache/download, backup/rollback, installer process and taskkill.
- Boundary: archival is closed for the scoped path only. Full backend suite,
  candidate commit, global strict-runtime zero and independent final review
  remain open.

## 2026-09-25 — Detect PowerShell .NET, registry and environment mutation sinks

- Decision: the inventory now recognizes `New-ItemProperty`, `Set-Item`,
  `Environment.SetEnvironmentVariable`, and `File.WriteAllText`/related static
  writes. Registry and persistent environment changes use canonical
  `system.configuration.write`; .NET file methods use `filesystem.write`.
- Evidence: scanner and registry tests `24 passed`; the five installer PATH /
  Explorer registry sinks and the .NET file write are now explicit findings.
  Global inventory is `2198` / `395 runtime-unbound` / `0 unclassified`;
  strict classification PASS, strict runtime FAIL/OPEN.
- Boundary: this closes scanner coverage for these concrete PowerShell call
  forms, not their gateway ownership. The five `system.configuration.write`
  sinks in `install-v4.ps1` remain unbound. Other installer effects and the
  complete global gate remain open.

## 2026-09-25 — One authorization owner for installer entrypoints

- Evidence: source tracing confirms `install-v4.ps1` is launched by Electron
  maintenance, release-job install, the `bago install` CLI, and the standalone
  assistant/remote installer wrappers. The latter also have independent
  network/extraction sinks. Direct callsite conversion in only Electron would
  leave production bypasses.
- Decision: prepare one canonical install effect behind `ExecutionGateway` and
  the existing `AuthorizationBoundary`. The adapter must bind source identity,
  destination, install/repair mode and options in a strong Permit, issue a
  one-use helper ticket, and require the elevated `install-v4.ps1` materializer
  to validate the consumed request and ticket before any sink. Every runtime
  caller must use this owner; direct helper invocation must fail closed.
- Limits: `system.update.apply` remains specific to applying a verified
  release update and is not reused as a catch-all installer identity.
  Bootstrap network/extraction remains separately owned. Keep PowerShell 5.1,
  same-source repair and current guided provider configuration behavior.
- State: design `PREPARED`; adapter/helper/caller migration and pre-effect
  denial evidence remain `PROPOSED/OPEN`. This is an ingress decision, not an
  implementation or gate-closure claim.

- Sequencing correction (2026-09-25): `install-v4.ps1` self-elevates via
  `Start-Process -Verb RunAs` before its main install flow, so that launch is
  itself a material process sink. The script must reject direct invocation
  before self-elevation unless the gateway ticket is valid; the elevated child
  independently revalidates the consumed authorization ledger record, exact
  helper hash, and bound install target before any install sink. Guided
  configuration/provider choices must also be bound before challenge/approval
  or collected in a non-material preparation phase. For remote installs,
  verified download and extraction remain separately owned and the staged
  bundle identity is bound before install authorization. The earlier design
  requiring only child validation is superseded on this ordering detail.
  Evidence: current-source inspection. Installer/global gates are `NOT_RUN` in
  this design-correction block; implementation remains `OPEN`. Change window:
  2m04s (05:44:49–05:46:53 Madrid); tests not run.

## 2026-09-25 — Proteger el helper de instalación tras el Permit fuerte

- Decisión: `system.install.apply` emite un ticket de un solo uso después de
  consumir el Permit fuerte. `install-v4.ps1` valida antes de autoelevarse el
  ledger canónico, ticket/nonce, request, proof, decision, sesión, hashes de
  fuente y helper, destino, modo, opciones y digest de configuración. El proceso
  elevado reclama el ticket y solo carga la configuración ligada al Permit;
  elimina la copia consumida que contiene secretos.
- Los digests de configuración y árbol de fuentes conservan el mismo formato
  canónico Python/PowerShell; se contrastaron con datos Unicode. La llamada
  directa al helper sin autorización falla antes de autoelevarse.
- Evidencia focal: install plan/gateway/registry `17 passed`; parser PowerShell
  PASS; rechazo sin autorización PASS; digests cruzados PASS.
- Inventario actual: `2213` sinks, `397 runtime-unbound`, cero clasificaciones
  scope/binding abiertas. `--strict-classification` PASS;
  `--strict-runtime` FAIL/OPEN.
- Límite: los callers existentes de Electron, CLI, asistente y remoto siguen
  sin migrarse y ahora fallan cerrado al invocar el helper. Esta tranche queda
  `EXECUTED`; gate global, suite backend completa, candidato comprometido y
  revisión independiente permanecen abiertos.
- Duración del bloque de implementación: `5m43s` (04:11:57–04:17:40 UTC);
  las pruebas se informan por separado.
- Límite adicional de autoridad: `handlers_install.py` deriva el canal de
  aprobación de `X-Bago-Channel`. La superficie desktop/frontend de confianza
  no está integrada ni atestada independientemente; por tanto, el recorrido de
  interacción directa de usuario y la operación instaladora utilizable siguen
  abiertos aunque el helper rechaza toda llamada sin ticket válido.

## 2026-09-25 — Ligar los sinks del helper de instalación a su owner gateway

- El inventario conserva todos los findings de `install-v4.ps1` y los clasifica
  como implementación del owner `system.install.apply`: el helper valida el
  ticket ligado al Permit antes de autoelevarse y el hijo reclama el ticket
  antes de la materialización. La prueba Windows sin ticket demuestra el rechazo
  pre-elevación; no se eliminan ni se excluyen findings.
- Evidencia: `test_effect_sink_inventory.py` y `test_system_install_gateway.py`
  -> `23 passed`; strict classification PASS; inventory `2213` total / `348`
  runtime-unbound / `0` sin clasificar; strict runtime FAIL/OPEN.
- Límite: la confirmación desde una superficie desktop confiable y todos los
  callers productivos siguen abiertos. Estado `EXECUTED`, no cierre global.
- Duración del cambio: `1m13s` (04:22:09–04:23:22 UTC); pruebas aparte.

## 2026-09-25 — Enrutar la instalación del release job por system.install.apply

- `ReleaseJobManager` ya no hace spawn de `install-v4.ps1`. La operación usa
  `/install/apply`; Electron obtiene challenge, verifica que el target coincide
  con el job y abre una confirmación desktop nativa que muestra bundle, fuente,
  helper y destino antes de aprobar. Cancelar no crea Permit ni mueve el backup.
  Tras aprobar se prepara el backup y se consume el Permit al ejecutar; el owner
  espera el exit code y solo devuelve `completed` con salida cero.
- La configuración ligada es neutra, sin secretos. El instalador conserva la
  configuración existente del runtime; una instalación nueva queda sin
  proveedores/credenciales y eso se informa en el diálogo. Cancelar durante el
  helper no está soportado y el control se oculta durante ese estado.
- Evidencia focal: client y release-job CJS tests PASS; suite gateway/inventory
  `24 passed`; sintaxis Node, `py_compile` y `git diff --check` PASS.
- Inventory: `2215` sinks / `347` runtime-unbound / cero scope/binding abiertos;
  strict classification PASS y strict runtime FAIL/OPEN.
- Límite: los renames de backup/rollback del manager siguen directos y abiertos;
  también quedan otros callers Electron/CLI/remote. La ruta HTTP aún deriva
  procedencia de `X-Bago-Channel`; la confirmación nativa existe en el IPC del
  release manager pero el backend no atesta criptográficamente esa cabecera.
  Esta tranche es `EXECUTED`, sin cierre global.
- Duración del cambio: `6m36s` (04:30:10–04:36:46 UTC); pruebas aparte.

## 2026-09-25 — Mover la copia del backup y la recuperación del helper al owner de instalación

- `SystemInstallApplyEffectAdapter` conserva el runtime existente en su lugar
  para que el instalador mantenga `.bago/config.json`, crea una copia recuperable
  nombrada con el Permit consumido y pasa `-GatewayBackupProvided` solo para el
  ticket `release-job`. El helper evita así producir un segundo backup.
- Si el helper falla, el owner restaura el backup y conserva el árbol fallido.
  Electron persiste el recibo devuelto para recuperar tras fallar la validación.
  Los renames del rollback manual y de esa recuperación posterior siguen
  directos en `_restoreAtomicBackup` y son la siguiente brecha del gate.
- Evidencia: 26 tests focales PASS en 22.73s; release-job CJS PASS; Node syntax,
  parser PowerShell y `git diff --check` PASS. Inventario: 2230 sinks / 345
  runtime-unbound / cero no clasificados. Strict classification PASS;
  strict runtime FAIL/OPEN.
- Duración del cambio: `6m45s` (04:39:22–04:46:07 UTC); pruebas aparte.

## 2026-09-25 — Autorizar rollback de release-job mediante system.install.rollback

- Añadido el efecto `system.install.rollback` (E5, destructive, strong,
  non-delegable) y su endpoint `/install/rollback`. Challenge, aprobación y
  consumo reconstruyen el mismo request; el adapter exige proof consumido para
  el efecto, fingerprint, sesión, decisión y canal de interacción directa.
- El adapter comprueba rutas absolutas y lexicales, backup hermano con nombre
  emitido por gateway, tipos de destino, enlaces/reparse points y colisiones
  antes de `os.replace`. Operaciones parciales son reintentables; Electron
  conserva el estado del job y deja `failed` con rollback disponible si no hay
  recibo confirmado.
- ReleaseJobManager dejó de mover destino/backup. El cliente Electron presenta
  confirmación nativa para rollback manual y para recuperación cuando falla la
  validación posterior a la instalación. Un rechazo conserva la instalación y
  su opción de rollback.
- Evidencia final focal: 41 passed en 23.14s; tests CJS del cliente y del job
  PASS; Node syntax, Python compile, strict classification y `git diff --check`
  PASS. Inventario: 2237 sinks / 343 runtime-unbound / cero sin clasificar;
  strict runtime sigue FAIL/OPEN.
- Límite: el job puede perder el path del backup si el proceso muere antes de
  persistir el recibo de `system.install.apply`; se conserva como brecha de
  recuperación. El gate global y otros callers siguen abiertos.
- Duración del cambio: `10m35s` (04:46:07–04:58:04 UTC); pruebas aparte.

## 2026-09-25 — Separar el owner de rollback y retirar cancelación de proceso muerta

- `SystemInstallRollbackEffectAdapter` queda en módulo propio y se registra
  aparte de `SystemInstallEffectAdapter`; cada adapter conserva una
  responsabilidad coherente.
- `ReleaseJobManager._killTree` y el `spawn(taskkill.exe)` asociado se
  eliminaron. Tras retirar el spawn directo del instalador ya no existía ningún
  productor de `runtime.child`; la cancelación efectiva de descarga conserva su
  AbortController.
- Evidencia: 41 tests focales PASS en 24.19s; release-job manager/client CJS,
  Node syntax, Python compile, strict classification y `git diff --check` PASS.
  Inventario: 2236 sinks / 342 runtime-unbound / 0 sin clasificar; strict
  runtime FAIL/OPEN.
- La descarga/caché del release job sigue abierta. `release.download` actual
  escribe en la raíz de updates y solo maneja el contrato de bundle, mientras
  release-job usa otro cache y descarga checksum/firma además del bundle.
- Duración del cambio: `2m08s` (05:03:10–05:05:42 UTC); pruebas aparte.

## 2026-09-25 — Enrutar assets y caché de release-job por release.download

- Se extendió el adapter canónico `release.download` para las tres clases de
  asset de release-job (`checksum`, `signature`, `bundle`), manteniendo un solo
  owner y reutilizando la política de host/transporte existente. Cada job usa
  `manager/release-jobs/cache/<job_id>` con nombre de archivo validado.
- `ReleaseJobManager` ya no descarga con `fetch`, ni crea el directorio de
  caché, elimina parciales o renombra el asset final. Electron despacha la
  operación a la API local y recibe un recibo con path, SHA-256 y bytes.
- El adapter valida host, job, nombre, tamaño y tipo antes de tocar el destino;
  en reanudación exige rango exacto hasta el byte final y total publicado,
  vuelve a calcular el digest sobre el parcial y publica con reemplazo atómico
  solo tras coincidir tamaño y digest. Consulta cancelación persistida antes de
  red y durante la lectura, conservando `.part` al cancelar.
- Se conserva la ruta léxica del root de release-jobs: resolverla antes de
  validar los componentes aceptaría silenciosamente un enlace a otro árbol.
  Se añadió rechazo pre-red de un directorio de caché enlazado.
- Evidencia focal: 32 passed en 14.33s (descarga, storage y update manager);
  tests CJS del manager y del cliente,
  sintaxis Node, `py_compile`, strict classification y `git diff --check` PASS.
  Inventario: 2248 sinks / 338 runtime-unbound / cero no clasificados. Strict
  runtime sigue FAIL/OPEN. La búsqueda confirma que los sinks del snapshot
  `backend/release/v4/current` son `derived_release_snapshot`, fuera del runtime
  activo; no cuentan como migración de autoridad.
- Duración del cambio: `15m57s` (05:05:42–05:21:39 UTC); pruebas aparte.

## 2026-09-25 — Enrutar atomic_patch por el owner project.write

- La API pública `apply_patch_atomically` ya no escribe directamente. Exige
  SessionManager del workspace activo y Permit aprobado; el rollback también
  requiere autorización propia. Ambas operaciones se despachan por el mismo
  `project.write` y el `ProjectWriteEffectAdapter` ya registrado.
- `POST /project/patch` y `/project/patch/rollback` implementan
  challenge/approve/execute. El request enlaza la lista exacta de unified
  diffs, el root activo y el fingerprint de cada target antes/después.
  Rechaza paths prohibidas, escapes y enlaces antes del primer efecto.
- Se separó coordinación de request/rollback a `project_patch_operations.py`
  y materialización/recuperación a `workspace_patch_storage.py`; el facade
  `bago_core.execution.atomic_patch` quedó en 176 líneas y el adapter de
  project en 387. Snapshot previo conserva hashes y contenido; si una
  aplicación multipath falla, restaura lo ya escrito y preserva recuperación
  si la restauración falla. El rollback manual valida que el contenido siga
  exactamente como después del parche antes de reemplazarlo.
- Evidencia focal: 127 passed, 153 subtests en 27.54s; syntax/compile,
  strict-classification y `git diff --check` PASS. El inventario pasa de 338 a
  328 runtime-unbound; 2252 total y cero sin clasificar. `--strict-runtime`
  sigue FAIL/OPEN. El filtro del scanner dejó de marcar los 10 sinks del
  facade; los sinks en `workspace_patch_storage.py` aparecen como
  `gateway_adapter`. No hay caller frontend de atomic_patch en el checkout,
  así que no se añadió un flujo UI huérfano.
- Duración del cambio: `23m24s` (05:21:39–05:45:03 UTC); pruebas aparte.

## 2026-09-25 — Los botones de release del Manager usan release-job

- La UI Electron del Manager heredado no debe invocar `install-remote.ps1`
  con un comando PowerShell. Usa el release-job existente, que descarga,
  verifica y prepara el bundle bajo sus owners y solicita `system.install.apply`
  con confirmación nativa para materializar la instalación.
- Se elimina la ruta del preload que construía ese comando. El bootstrap
  standalone sigue siendo necesario para instalación sin backend; permanece
  explícito como superficie sin autoridad y no se disfraza como resuelto por
  `ExecutionGateway`. Su diseño de identidad/autoridad queda abierto.
- Duración de bloque: `9m23s` (05:46:49–05:56:12 UTC); tests: 15 passed en
  3.74s, reportados aparte. El inventario se mantiene en 328 runtime-unbound.

## 2026-09-25 — Electron instala mediante `system.install.apply`

- Decisión: la instalación inicial, reparación, reinstalación, copia nueva y
  actualización desde fuente del Manager no lanzan `install-v4.ps1` desde
  `dependency-service`. Todas preparan el operation plan, muestran confirmación
  desktop ligada a hashes y despachan `system.install.apply`; el helper valida
  el ticket consumido antes de elevarse.
- La reparación conserva `.bago/config.json` e `install_config.json` cuando
  existen. Un store externo de credenciales no se reemplaza cuando la
  operación no trae secretos; los nuevos installs empiezan con configuración
  neutral. El spawn duplicado `runInstallScript` fue retirado.
- Límite restante: source-update aún hace `git pull` directamente antes del
  challenge de instalación; la desinstalación también conserva su runner
  separado. Bootstrap remoto y backup receipt siguen pendientes.
- Evidencia: 26 tests focales, cliente Node, 5 parsers Node, parser PowerShell,
  strict classification y `git diff --check` PASS. Inventario: 2252 / 327
  runtime-unbound / 0 sin clasificar; strict runtime FAIL/OPEN.
- Duración del bloque: `17m20s` (05:56:12–06:13:32 UTC); pruebas reportadas
  aparte.

## 2026-09-25 — Source-update de Electron usa owner propio

- `git pull --ff-only` deja de ejecutarse desde `install-service.cjs` antes de
  pedir autorización. El checkout limpio, rama, HEAD y origen quedan ligados a
  `system.source.update`; el adapter exige Permit fuerte de interacción desktop,
  vuelve a revisar la identidad inmediatamente antes del pull y entrega recibo
  con HEAD previo y resultante. Rechaza checkout sucio, rama distinta y URLs de
  origen con credenciales; permite la identidad SSH convencional `git@`.
- El diálogo nativo muestra raíz, origen, rama, HEAD y digest del origen. El
  cliente solicita una segunda aprobación independiente para `system.install.apply`
  después del pull, porque el árbol/hash instalable solo queda definido entonces.
- Evidencia focal: 14 tests de gateway/instalación passed en 3.91s; cliente
  Electron, sintaxis Node, compile Python, resolución del endpoint,
  `--strict-classification` y `git diff --check` PASS. Inventario actual:
  2252 sinks, 326 runtime-unbound, 0 sin clasificar; `--strict-runtime` sigue
  FAIL/OPEN. Una escritura de preferencias en `install-service.cjs` permanece
  runtime-unbound; uninstall, bootstrap y rollback-bago siguen abiertos.
- Duración del bloque: `8m22s` (06:17:42–06:26:04 UTC); pruebas reportadas
  aparte.

## 2026-09-25 — La desinstalación Electron usa `system.install.uninstall`

- La desinstalación desde Manager solicita un plan que liga destino, digest del
  árbol instalado, CLI, backup y decisión de purgar estado. Un Permit fuerte,
  no delegable y aprobado en canal desktop emite un ticket de un solo uso;
  tanto el adapter como el helper validan la identidad antes de materializar.
- Backup ZIP recuperable, limpieza de PATH/menú Explorer, purga opcional y
  borrado viven en `install_uninstall_lifecycle.py`. El CLI sin ticket falla
  antes de mutar. El helper vuelve a calcular el digest tras reclamar el
  ticket. La elevación conserva el quoting de Windows y el proceso padre usa
  un cwd fuera del árbol que elimina.
- La desinstalación standalone PowerShell falla de forma cerrada y dirige al
  Manager. Se preservan backups anteriores. La UI pide confirmación nativa con
  destino, backup e impacto de purga; no hubo adaptación de frontend web porque
  el flujo propietario está en Electron/Manager.
- Evidencia focal: 32 passed en 20.77s; cliente Electron PASS; compilación
  Python y `git diff --check` PASS. Inventario actual: 2258 sinks, 322
  runtime-unbound, 0 sin clasificar; strict runtime sigue FAIL/OPEN.
- Duración del bloque: `31m06s` (06:26:04–06:57:10 UTC); pruebas reportadas
  aparte.

## 2026-09-25 — Electron delega credenciales y limpia probes del preflight

- La escritura de API key desde Electron usa `/providers/configure` y el owner
  `credential.write`; Manager muestra confirmación desktop ligada al proveedor
  y al digest de configuración y solo reporta éxito con recibo consumido. Se
  elimina el Python inline que escribía credenciales fuera del gateway.
- El preflight comprueba permisos y espacio mediante APIs de lectura del
  filesystem. Ya no crea/elimina probe files ni lanza PowerShell/df para el
  espacio libre.
- Evidencia: 40 tests focales passed en 21.34s; cliente Electron y sintaxis de
  cuatro módulos Node PASS; scanner strict classification PASS; `git diff
  --check` PASS. Inventario: 2253 sinks, 317 runtime-unbound, cero sin
  clasificar; strict runtime FAIL/OPEN.
- Duración del bloque: `6m56s` (06:57:10–07:04:06 UTC); pruebas reportadas
  aparte.
- Límite detectado: `install-remote.ps1` aún llama `install-v4.ps1` sin ticket.
  El instalador lo rechaza antes de elevar; el bootstrap standalone requiere
  definir una ruta real de autoridad antes de declararlo cerrado.

## 2026-09-25 — El Manager persiste selección y cadenas bajo ExecutionGateway

- Se añadieron `manager.settings.write` y un único
  `ManagerSettingsWriteEffectAdapter` para las escrituras de selección de roles
  de instalación y registro de cadenas. El owner deriva los destinos desde
  `user_root`, valida roles/launcher o IDs únicos de cadenas, rechaza enlaces,
  liga hashes al challenge y escribe atómicamente tras Permit consumido.
- La ruta `/manager/settings/write` usa challenge → aprobación desktop →
  ejecución. La confirmación muestra destino, rol o cantidad/IDs y digest. El
  preload solo lee los archivos; sus dos escrituras ahora llaman al IPC del
  Manager y este al endpoint gobernado.
- Evidencia: 52 passed y 156 subtests en 21.48s; cliente CJS, sintaxis Node y
  compilación Python PASS; scanner mantiene 2252 sinks, con 311
  runtime-unbound y cero sin clasificar; `git diff --check` PASS.
- Duración del bloque: `8m48s` (07:09:27–07:18:15 UTC); pruebas reportadas
  aparte. Global strict-runtime continúa FAIL/OPEN.

## 2026-09-25 — La autonomía coordina exclusión con `ExecutionClaimStore`

- `autonomous_loop.py` deja de materializar `autonomous.lock` con `mkdir/open`,
  `unlink` y exclusión de `fcntl`/archivo. `_LoopLock` comparte ahora el store
  SQLite canónico `execution_claims.sqlite3`, con clave estable por raíz BAGO,
  owner/operación únicos, lease de una hora, renovación por ciclo y liberación
  explícita. La claim solo coordina concurrencia; no se presenta como permiso.
- Los cuatro sinks del lock salen del módulo. Permanecen abiertos el
  `subprocess.run` de herramientas y los sinks de escritura del inbox/estado;
  esta tranche no atribuye su autoridad al `ExecutionGateway`.
- Evidencia focal: 14 passed, 1 skipped en 1.66s; Python compile,
  `--strict-classification` y `git diff --check` PASS. Inventario: 2248 total,
  307 runtime-unbound, cero sin clasificar; strict runtime continúa FAIL/OPEN.
- Duración del bloque: `5m25s` (07:18:15–07:23:40 UTC); pruebas reportadas
  aparte.

## 2026-09-25 — La importación de Capability Packages consume un Permit

- Se registra `capability.package.import` y un único
  `CapabilityPackageImportEffectAdapter`. La importación ZIP y la instalación
  de ejemplos comparten el owner. El materializador vive en el módulo del
  adapter; las entradas directas `import_package` e `install_example_package`
  fallan cerradas antes de tocar estado.
- HTTP emite challenge, aprueba con la sesión y canal presentes y consume el
  Permit antes de extraer/escribir. El target liga SHA-256 del archivo,
  identidad/versión/tipo y nombre saneado. El frontend ahora usa el flujo
  challenge → approve → execute en ambas acciones.
- La primera pasada focalizada falló por mocks frontend antiguos y porque las
  pruebas de paquete cargan módulos bajo alias que no sobreviven al limpiado
  de pytest; se ajustaron mocks y el acceso del helper de pruebas al estado del
  módulo llamante. La pasada final: 61 backend tests passed en 26.65s; 23
  frontend API tests passed, TypeScript typecheck, Python compile,
  `--strict-classification` y `git diff --check` PASS. El gate estricto global
  sigue FAIL/OPEN con 301 sinks runtime sin owner.
- Duración del bloque: `15m27s` (07:23:40–07:39:07 UTC); pruebas reportadas
  aparte.

## 2026-09-25 — Capability Runtime concentra los procesos en su adapter

- Las dos llamadas `subprocess.run` salen de `capability_packages.py` y pasan a
  `CapabilityRuntimeEffectAdapter`. Las llamadas privadas de capacidad y
  pipeline reciben el runner únicamente desde el adapter; las entradas
  públicas `execute_package` y `execute_pipeline_package` fallan cerradas.
- Antes del lanzamiento, el adapter exige autorización consumida que coincide
  con efecto, fingerprint y sesión, y vuelve a validar digest, tipo, versión y
  permisos del paquete. El pipeline conserva ese runner al ejecutar pasos de
  capacidad anidados, sin abrir una segunda ruta de autoridad.
- Evidencia: 69 backend tests focales passed en 27.58s, incluida ejecución
  API con challenge, aprobación y Permit consumido; Python compile,
  `--strict-classification` y `git diff --check` PASS. Inventario: 2247
  sinks, 299 runtime-unbound, 0 sin clasificar; strict runtime FAIL/OPEN.
- Duración del bloque: `7m40s` (07:42:14–07:49:54 UTC); pruebas reportadas
  aparte.

## 2026-09-25 — La persistencia de autonomía usa el owner de `state.write`

- `_atomic_write` deja de crear carpetas, temporales y reemplazos por su
  cuenta. Emite `state.write` mediante `execute_server_owned`; el target se
  limita a `inbox.json` o `autonomous_state.json` bajo el único root de estado
  del loop, y el adapter comprueba de nuevo el root y ejecuta la escritura
  atómica. Un target arbitrario y payloads que no sean objetos JSON se
  rechazan antes del gateway.
- Evidencia: 3 pruebas de autonomía passed en 0.34s; Python compile,
  `--strict-classification` y `git diff --check` PASS. Inventario: 2244 sinks,
  296 runtime-unbound, cero sin clasificar. El subprocess de herramientas de
  autonomía sigue abierto.
- Duración del bloque: `2m34s` (07:49:54–07:52:28 UTC); pruebas reportadas
  aparte.

## 2026-09-25 — La autonomía gobierna herramientas CLI por efecto

- El lanzamiento de procesos sale de `autonomous_loop.py` y pasa a dos owners
  registrados. `autonomous.observe` solo acepta comandos de lectura de una
  lista fija, sin argumentos, con intérprete, raíz backend y timeout ligados
  al request; usa `execute_server_owned` y autorización de política.
- `autonomous.repair` solo permite `heal`/`doctor`. Requiere `--unsafe`, TTY,
  challenge exacto con comando/cwd/timeout visibles, confirmación de terminal
  y Permit consumido. Se añadió `approve_cli_challenge`, que verifica TTY y no
  está expuesto por el aprobador HTTP; el canal HTTP `cli` sigue rechazado.
- Evidencia: 92 pruebas focales passed en 23.70s, incluidas autorización,
  gateway, scheduler, claim y scanner; Python compile,
  `--strict-classification` y `git diff --check` PASS. Inventario: 2244 sinks,
  295 runtime-unbound, cero sin clasificar; strict runtime FAIL/OPEN.
- Duración del bloque: `6m48s` (07:52:28–07:59:16 UTC); pruebas reportadas
  aparte.

## 2026-09-25 — El aprendizaje autónomo escribe mediante `learning.write`

- Las observaciones JSONL y los patrones promovidos de `LearningWriter` pasan
  por el `ServerStateEffectAdapter` bajo el efecto de política `learning.write`.
  El owner limita la operación a append/replace y a los dos destinos canónicos
  `.bago/state/auto_learnings.jsonl` y
  `.bago/knowledge/auto_patterns.md`, dentro de la raíz confiable.
- Se eliminó el auto-test ejecutable duplicado que escribía a rutas temporales
  por fuera del adapter. El flujo de aprendizaje y promoción queda cubierto en
  pytest; una ruta fuera de la allowlist se bloquea antes de crear el archivo.
- Evidencia: 59 pruebas focales passed en 2.66s; compile, strict
  classification y `git diff --check` PASS. Inventario: 2238 findings, 289
  runtime-unbound, 0 unclassified. `--strict-runtime` sigue FAIL/OPEN.
- Duración del bloque: `6m18s` (08:09:59–08:16:22 UTC), excluyendo 5.45s de
  ejecución de pruebas.

## 2026-09-25 — Los fixtures de Process Monitor viven en pytest

- Se retiró de `.bago/tools/process_monitor.py` el auto-test que creaba
  directorios y archivos temporales en runtime; esos fixtures y la verificación
  de estado/HTML viven ahora en `tests/test_process_monitor.py`. La opción CLI
  `--test` se elimina; `serve` y `generate` conservan su comportamiento.
- Los dos sinks de `generate` (`mkdir` de destino y escritura HTML) permanecen
  runtime-unbound y requieren una tranche separada de autorización; no se
  clasifican como pruebas ni como adapter.
- Evidencia: 1 prueba focal passed en 0.17s; Python compile, strict
  classification y `git diff --check` PASS. Inventario: 2237 findings, 285
  runtime-unbound, cero sin clasificar. `--strict-runtime` sigue FAIL/OPEN.
- Duración del bloque: `2m58s` (08:19:29–08:22:28 UTC), excluyendo 0.67s de
  pytest.

## 2026-09-25 — `monitor.generate` consume autorización CLI explícita

- La salida HTML de Process Monitor deja de escribir en el caller. El efecto
  `monitor.generate` usa el adapter propio y un Permit CLI de un solo uso que
  muestra destino, huella y tamaño en TTY. Un helper compartido centraliza el
  challenge/approve/execute y también lo usa `autonomous.repair`.
- El request liga proyecto, ruta normalizada, digest anterior y digest del HTML.
  El adapter rechaza salida fuera del proyecto, rutas enlazadas o un archivo
  cambiado después de la aprobación antes de crear directorios o reemplazar.
- Evidencia: 61 pruebas focales passed en 2.76s, incluidas las denegaciones
  previas al efecto para escape y target drift; compile, strict classification
  y `git diff --check` PASS. Dos intentos de prueba fallaron antes del cierre
  por expectativa de versión obsoleta y por fixture ya existente; ambos se
  corrigieron y la corrida final pasó. Inventario: 2244 findings, 283
  runtime-unbound, cero unclassified; `--strict-runtime` sigue FAIL/OPEN.
- Duración del bloque: `6m18s` (08:24:06–08:30:38 UTC), excluyendo 14.03s de
  ejecución pytest.

## 2026-09-25 — CredentialManager deja de persistir fuera del gateway

- `CredentialManager` ya no crea el directorio de estado ni escribe
  `credentials.json` durante la construcción/importación de entorno. Las
  escrituras explícitas `set/delete` ligan sesión, proveedor, clave, digest de
  configuración y valor al efecto fuerte `credential.write`; la aprobación CLI
  exige TTY y el adapter guarda en SecretStore. El valor canónico de SecretStore
  prevalece sobre el archivo legacy, que queda de solo lectura.
- Las claves de API legacy se mapean a `providers/<provider>/api_key`; otras
  claves registradas usan su propia identidad SecretStore. El borrado solo
  declara éxito cuando se borró un secreto canónico. Un valor que solo existe
  en el archivo legacy no se puede borrar desde este camino, porque eso exigiría
  conservar una escritura no gobernada.
- `store_mode=session` conserva su semántica volátil: modifica solo la memoria
  de la sesión y no invoca `credential.write` ni SecretStore.
- Evidencia: 56 pruebas (`test_user_state_legacy_contract.py` y
  `test_execution_gateway_v2.py`) passed en 2.99s; compile y `git diff --check`
  PASS. Inventario global: 2239 sinks, 278 runtime-unbound, cero sin clasificar;
  strict runtime continúa OPEN. La reducción de cinco findings cubre los sinks
  del constructor y del escritor legacy, no cierra el gate global.
- Duración del bloque: `6m03s` (08:34:50–08:41:02 UTC), descontando 9.39s de
  las tres ejecuciones pytest de este bloque.

## 2026-09-25 — Los fixtures de Doctor viven en pytest

- Quité de `.bago/tools/doctor.py` `run_self_tests()` y su opción `--test`;
  los casos de sintaxis, JSON, UTF-8, tamaño, orfandad y salida JSON limpia se
  trasladaron a `tests/test_doctor_tool.py`. La ejecución de Doctor conserva
  solo el diagnóstico solicitado sobre el root indicado.
- Evidencia: 7 pruebas pasaron en 0.25s, py_compile y `git diff --check` PASS.
  Inventario global: 2232 sinks, 271 runtime-unbound y cero sin clasificar;
  `--strict-runtime` permanece abierto.
- Duración del bloque: `1m15s` (08:43:09–08:44:24 UTC), excluyendo 0.25s
  de pytest.

## 2026-09-25 — Canaries sintéticos consumen un Permit fuerte

- Registré `security.canary.manage` como efecto E5 strong/no delegable y un
  único `SecurityCanaryEffectAdapter` para `deploy` y `purge`. El CLI liga root,
  tipos, timestamp, inventario/digest previo y digests actuales de cada archivo
  al request; pide aprobación directa en TTY. El owner verifica proof y sesión,
  paths canónicos, reparse points, estado y drift bajo lock de archivo
  cross-process antes de materializar o borrar. `list/check` son de solo lectura
  y ya no crean directorios; el self-test de runtime se eliminó.
- Evidencia final: 82 pruebas de canary, registry, gateway e inventario pasaron
  en 23.50s; `--strict-classification` PASS (2244 total / 0 sin clasificar),
  Python compile y `git diff --check` PASS. El inventario confirmó cero
  runtime-unbound findings en `bago_canary.py`; el gate global sigue OPEN con
  264 runtime-unbound.
- Primer intento falló porque el harness headless no satisfacía la exigencia
  de TTY de `approve_cli_challenge`; corregí el harness para simular ese límite
  sin relajar producción. La corrida final pasó.
- Duración del bloque: `11m19s` (08:49:04–09:01:15 UTC), descontando 51.73s
  de las cinco ejecuciones pytest del bloque.
## 2026-09-25 — Commit readiness inspecciona staged Git bajo `repository.inspect`

- Registré `repository.inspect` como efecto explícito, solo lectura, no delegable y con receipt. `commit_readiness.py` solo puede listar los archivos staged o leer el staged diff mediante argumentos Git exactos; requiere aprobación directa CLI en TTY y pasa por `ExecutionGateway`. El adapter desactiva shell y configuración/helpers Git ambientales, y liga root/sesión.
- Quité seis escrituras de fixtures del self-test embebido y trasladé los casos a pytest.
- Evidencia: 85 pruebas focales pasaron en 22.77s; compile, strict classification y `git diff --check` PASS. Inventario: 2245 total, 257 runtime-unbound, 0 sin clasificar; `--strict-runtime` sigue abierto.
- Duración del bloque: `7m53s` (09:05:56–09:14:12 UTC), excluyendo 22.77s de pytest.

## 2026-09-25 — Debt Guard persiste solo bajo owners de repositorio

- Registré `repository.guard.manage` para los dos recursos que Debt Guard puede mutar: `.bago/debt_guard_config.json` y `.git/hooks/pre-commit`. Un único adapter valida root/sesión, Permit CLI consumido, ruta allowlisted, digest anterior y contenido/digest nuevo; el borrado solo acepta hooks con el marcador BAGO. La escritura atómica, creación de padres, borrado y chmod del hook pertenecen al adapter.
- La enumeración de archivos staged reutiliza `repository.inspect`; eliminé el `subprocess.run` y el fallback que convertía una denegación de autorización en una lista vacía/éxito. Las operaciones persistentes exigen TTY y aprobación directa.
- La inspección de staged usa salida NUL-delimitada; Debt Guard rechaza escapes de raíz y symlinks antes de leer archivos staged.
- Evidencia: 73 pruebas focales pasaron en 4.23s en la corrida final; dos intentos previos encontraron y corrigieron fixtures incompletos de TTY y raíz Git. Compile, strict classification y `git diff --check` PASS. Inventario: 2246 total, 250 runtime-unbound, 0 sin clasificar; `debt_guard.py` y `commit_readiness.py` tienen cero runtime-unbound. `--strict-runtime` sigue abierto.
- Duración del bloque: `10m59s` (09:18:07–09:29:22 UTC), excluyendo 15.53s de las cuatro corridas pytest.

## 2026-09-25 — Auto Configurator reutiliza el owner de estado existente

- Eliminé las escrituras locales de `last_auto_config.json` y `config.json`. El estado terminal del job usa `state.write`; la aplicación de la configuración canónica usa `config.write`. Ambos pasan por las funciones de `bago_core.server_effects` y el mismo `ServerStateEffectAdapter`, sin registrar un segundo owner de configuración.
- Evidencia: dos pruebas nuevas ejercitan la persistencia a través del Gateway real. 76 pruebas focales pasaron en 22.49s; compile, strict classification y `git diff --check` PASS. Inventario: 2240 total, 244 runtime-unbound, 0 sin clasificar; `auto_configurator.py` tiene cero runtime-unbound. `--strict-runtime` permanece abierto.
- Duración del bloque: `5m09s` (09:30:00–09:35:32 UTC), excluyendo 22.49s de pytest.

## 2026-09-25 — Electron delega el vínculo de proyecto al owner `project.write`

- Eliminé la llamada directa de `runtime-service.cjs` a `project_memory.py`. El nuevo cliente modular `project-write-client.cjs` reutiliza `/project/link` para challenge, confirmación desktop ligada a raíz/ruta/digest, aprobación y ejecución; comprueba el receipt consumido de `project.write`. No se añadió otro owner ni camino de autoridad.
- Evidencia: 7 pruebas HTTP/Gateway de vínculo pasaron en 1.00s; prueba del cliente Electron, sintaxis Node, strict classification y `git diff --check` PASS. Inventario: 2239 total, 243 runtime-unbound, 0 sin clasificar. Quedan siete sinks directos en `runtime-service.cjs`; `--strict-runtime` sigue abierto.
- Duración del bloque: `4m01s` (09:40:13–09:44:15 UTC), excluyendo 1.00s de pytest.

## 2026-09-25 — Electron ejecuta launcher y SessionManager bajo `process.execute`

- Las invocaciones síncronas de launcher y SessionManager pasan por el cliente modular de proceso, challenge/confirmación nativa desktop/approve/execute y receipt consumido. El backend fija la sesión/cwd activo, liga el digest del módulo Python confiable, fija el `--base-path` de SessionManager y vuelve a comprobar la identidad del módulo antes de spawn.
- Las consultas automáticas de dashboard usan `process.inspect`, solo lectura con allowlist exacta del launcher y timeout fijo; el permiso de política del servidor se aplica por efecto, sin convertir el adapter compartido en autoridad para `process.execute`.
- Evidencia: 93 passed y 157 subtests en 8.30s; cliente Electron, IPC, sintaxis Node, compile, strict classification y `git diff --check` PASS. Inventario actual: 2247 sinks / 241 runtime-unbound / 0 sin clasificar. Quedan cinco sinks de ciclo de vida en `runtime-service.cjs`; gate global, suite backend completa, revisión independiente, commit y push continúan OPEN.
- Duración del bloque: `15m53s` (09:58:06–10:14:36 UTC), excluyendo las corridas pytest.

## 2026-09-25 — Electron ejecuta supervisor bajo `process.execute`

- `runSupervisorCmd` ya no invoca `bago_supervisor.py` directamente con `execFile`; reutiliza el cliente de proceso y el efecto `process.execute`. El backend solo permite `scripts/bago_supervisor.py` dentro del runtime de confianza y liga su digest, sesión, cwd y argv exactos al challenge. Confirmación desktop directa precede al Permit; el adapter vuelve a validar el digest antes del spawn.
- Evidencia: 56 pruebas focales pasaron en 3.81s; cliente Electron, sintaxis Node, compile, strict classification y `git diff --check` PASS. Inventario: 2249 total / 240 runtime-unbound / 0 sin clasificar. Cuatro sinks de ciclo de vida permanecen en `runtime-service.cjs`; la suite backend completa y revisión independiente continúan OPEN.
- Duración del bloque: `4m26s` (10:19:19–10:23:57 UTC), excluyendo 12.31s de pytest y el cliente Electron.

## 2026-09-25 — La limpieza manual de procesos usa `process.terminate`

- Registré `process.terminate` como E5, strong y no delegable. `cleanupZombies` dejó de construir/invocar PowerShell en Electron; reutiliza el cliente desktop y despacha al `ProcessExecutionEffectAdapter`. El API fija las raíces al runtime confiable y al state root del `SessionManager`, y no acepta argumentos del caller. El adapter revalida esas raíces y solo entonces ejecuta un comando PowerShell fijo; excluye el PID del backend actual y limita coincidencias a procesos Python cuya command line contiene una raíz aprobada.
- La confirmación nativa enseña las raíces afectadas y debe preceder al Permit. La prueba HTTP/Gateway verifica que no hay proceso antes de consumirlo.
- Evidencia: 62 pruebas focales pasaron en 4.79s; cliente Electron, sintaxis Node, compile, strict classification y `git diff --check` PASS. Inventario: 2249 total / 239 runtime-unbound / 0 sin clasificar. Tres sinks de ciclo de vida permanecen en `runtime-service.cjs`; suite completa y revisión independiente OPEN.
- Incrementé el registro de efectos a `1.16.0` para incluir el nuevo efecto canonical.
- Duración del bloque: `11m04s` (10:26:32–10:37:47 UTC), excluyendo 10.49s de ejecuciones de pruebas.

## 2026-09-25 — Cierre de Electron deja de barrer procesos de otras sesiones

- Eliminé `cleanupManagedRuntime`, que al salir buscaba por patrones Python/Node en todo el árbol y terminaba procesos con `taskkill`. También retiré la llamada automática a `cleanupZombies` en `shutdown` y el fallback de `main.cjs`; la limpieza sigue disponible desde el botón manual con `process.terminate` strong.
- El cierre automático conserva solo la parada del proceso webchat que esta instancia mantiene en su `ChildProcess`. Quité `execFile`, `os`, la resolución del runtime bundle y la dependencia `runVisiblePowerShell` del contexto de RuntimeService donde ya no se usaban.
- Evidencia: 17 pruebas pasaron en 4.50s; clipboard IPC, sintaxis Node, strict classification y `git diff --check` PASS. Inventario: 2248 total / 238 runtime-unbound / 0 sin clasificar. Quedan dos sinks de proceso directos en `runtime-service.cjs`; suite completa y revisión independiente OPEN.
- Duración del bloque: `3m43s` (10:39:09–10:42:57 UTC), excluyendo 5.12s de pruebas.

## 2026-09-25 — Electron detiene el webchat bajo `process.terminate`

- Eliminé el `spawn('taskkill.exe', ...)` de `stopWebChatProcess`. El API liga el PID actual del servidor, el puerto HTTP activo y el root confiable; el adapter comprueba que su `sys.argv` identifica `bago_core.launcher serve` en ese puerto/runtime. Con el Permit strong consumido programa un terminador PowerShell fijo que revalida la command line antes de `Stop-Process`. Electron valida el receipt y espera el evento exit del `ChildProcess`; cancelar o fallar aborta el cierre de la app.
- Amplié el inventario JavaScript para contar `.kill()` como `process.terminate` y excluir la sonda `process.kill(pid, 0)`. El inventario dejó visible `child.kill()` usado si el arranque del API no completa; no se ocultó bajo clasificación gateway.
- Evidencia: 63 pruebas focales pasaron en 4.99s y 22 pruebas del inventario en 22.51s; cliente Electron, sintaxis Node, compile, strict classification y `git diff --check` PASS. Inventario actual: 2253 / 238 runtime-unbound / 0 sin clasificar. Los dos sinks que quedan en `runtime-service.cjs` son spawn bootstrap y kill por fallo de arranque.
- Duración del bloque: `9m54s` (10:44:28–10:55:14 UTC), excluyendo 51.81s de ejecuciones de pruebas.

## 2026-09-25 — Seed materializer queda bajo la frontera `project.write`

- Los cinco sumideros de `.bago/seed.py` permanecen visibles en inventario y ahora se clasifican `gateway_owned`: el único cargador de producción es `project_memory.seed_project`, que requiere autorización `project.write` consumida antes de crear o escribir artefactos. La prueba existente limita las llamadas de materialización de ciclo de vida al `ProjectWriteEffectAdapter`; una prueba nueva impide que estos cinco hallazgos desaparezcan del inventario.
- Evidencia: inventario 2260 total / 218 runtime-unbound / 0 sin clasificar; strict classification PASS y strict runtime sigue OPEN. Suite de inventario: 24 passed; compile y `git diff --check` PASS.
- Duración: `1m10s` (11:36:37–11:38:08 UTC), excluyendo 21.16s de pytest.

## 2026-09-25 — Evidence bundle materializa solo bajo Permit CLI fuerte

- Registré `evidence.bundle.generate` (E5, strong, no delegable). La API pública exige autorización directa en TTY y liga destino, huella previa, modo, objetivo, provider/model, base path y overwrite. El adapter revalida destino y fingerprint después de generar, materializa en sibling temporal y hace el swap del bundle completo; si el swap falla, restaura el directorio anterior.
- El generador conserva materialización separada del request; solo el adapter llama la función privada. Los ocho sinks de `evidence_io.py` siguen visibles y pasan a `gateway_owned` mediante esta frontera probada. Quité `evidence --test`, que escribía en temporales por un camino de runtime paralelo; manuales y comandos exportados ahora apuntan a pytest.
- Evidencia: 46 pruebas focales pasaron en 35.35s; compile, strict classification y `git diff --check` PASS. Inventario: 2266 total / 210 runtime-unbound / 0 sin clasificar. Strict runtime sigue OPEN.
- Duración: `13m29s` (11:41:29–11:56:31 UTC), excluyendo pytest.

## 2026-09-25 — El rollback de ZIP usa `system.install.archive.rollback`

- Añadí un efecto E5 strong y no delegable. `bago rollback-archive` solicita aprobación TTY directa ligada al árbol de instalación/digest, raíz y ZIP/digest del backup, decisión sobre estado y destino del ZIP de seguridad. El adapter bloquea links, entradas especiales, traversal, duplicados, exceso de tamaño y drift antes del reemplazo; prepara al lado del destino y revierte al runtime anterior si falla el swap.
- El estado del runtime actual se conserva por defecto; restaurar el estado archivado requiere `--restore-backed-up-state`. `rollback-bago.ps1` ya no escribe ni borra: guía al comando gateway. Añadí cobertura de Gateway real, elección de estado, drift, Zip Slip e inventario.
- Evidencia: 37 pasaron en 26.62s; compile, strict classification y diff check PASS. Inventario: 2274 total / 201 runtime-unbound / 0 sin clasificar. Strict runtime sigue OPEN.
- Duración: `10m13s` (11:59:18–12:10:25 UTC), excluyendo las dos corridas pytest (53.59s).

## 2026-09-25 — GitHub state usa el writer persistente único

- Quité el `state.mkdir` directo de `handle_connect`. La persistencia del repositorio ahora depende solamente de `write_json_atomic` y su `state.write` owner, que crea el padre junto con la escritura atómica.
- Evidencia: 66 pruebas pasaron en 4.04s; compile, strict classification y diff check PASS. Inventario: 2273 total / 200 runtime-unbound / 0 sin clasificar. Strict runtime sigue OPEN.
- Duración: `41s` (12:12:47–12:13:32 UTC), excluyendo pytest.

## 2026-09-25 — GitHub comparte el dueño de procesos

- Decisión: mantener `process.inspect` y `process.execute` como única autoridad
  para los procesos GitHub CLI. Las lecturas de `gh` se limitan a auth status y
  endpoints GET allowlisted; login, logout y creación de repos pasan por el
  challenge de proceso con confirmación nativa Electron. El token de login no
  se muestra en el diálogo. Se retira la ruta de creación MCP duplicada y las
  antiguas rutas HTTP mutadoras quedan cerradas con 410.
- Evidencia: 44 tests focales Python passed en 32.03s; cliente de proceso PASS;
  TypeScript, compile Python, sintaxis Node, strict classification y
  `git diff --check` PASS. Inventario 2269 total / 196 runtime-unbound / 0 sin
  clasificar; `--strict-runtime` sigue FAIL/OPEN.
- Duración de cambios: `12m23s` (12:19:59–12:33:25 UTC), excluyendo 62.98s de
  pytest. El primer intento del comando incluyó incorrectamente un `.cjs` en
  pytest y se repitió con Node.

## 2026-09-25 — Sacar fixtures de `bago_infra_scan` del runtime

- Decisión: el scanner de infraestructura no expondrá `--test` ni creará/borrará
  workspaces de prueba dentro de su ruta de runtime. Los casos se ejecutan bajo
  pytest con `tmp_path` y servidor HTTP aislado.
- Evidencia: 3 pruebas focales passed en 3.24s; compile, strict classification y
  `git diff --check` PASS. Inventario 2266 total / 193 runtime-unbound / 0 sin
  clasificar; strict runtime permanece OPEN.
- Duración: `2m03s` (12:37:23–12:39:26 UTC), excluyendo pytest.

## 2026-09-25 — Retirar el autotest de `agent_router`

- Decisión: `agent_router` no mantendrá un modo runtime `--test` que recreaba
  archivos y manifiesto bajo el árbol real `BAGO_ROOT/roles`. Los tests se
  ejecutan con pytest; `configure_paths` sólo resuelve rutas y deja la creación
  del directorio al writer funcional cuando se registra una ruta.
- Evidencia: 26 pruebas focales pasaron en 2.54s; Python compile, strict
  classification y `git diff --check` PASS. Inventario: 2260 total / 187
  runtime-unbound / 0 sin clasificar; strict runtime OPEN.
- Duración: `3m42s` (12:39:26–12:43:11 UTC), excluyendo pytest.

## 2026-09-25 — Retirar autotests destructivos de herramientas de orquestación

- Decisión: `toolsmith`, `skill_engine` y `spiral_agent` no exponen autotests
  runtime que limpian/recrean scratch trees bajo el cwd. La plantilla generada
  por `toolsmith` tampoco propagará un `--test` trivial. La cobertura vive en
  pytest con `tmp_path`. Resolver rutas y construir un agente no crean estado;
  los writers siguen siendo responsables de materializar sus carpetas.
- Evidencia: 8 pruebas focales pasaron en 0.67s; Python compile y
  `git diff --check` PASS. Inventario: 2248 total / 175 runtime-unbound / 0 sin
  clasificar; strict runtime permanece OPEN.
- Duración: `3m56s` (12:45:22–12:49:19 UTC), excluyendo 0.67s de pytest.

## 2026-09-25 — El writer JSON compartido usa `state.write`

- Decisión: `bago_utils.save_json` conserva el punto común de escritura, pero
  entrega la materialización atómica al `ExecutionGateway`/adaptador
  `state.write`. El destino debe estar bajo un `.bago` del proyecto; el getter
  de estado sólo resuelve rutas. Se retiran `ensure_subdir` sin consumidores y
  el autotest CLI sin cobertura útil.
- Evidencia: 13 pruebas focales pasaron en 11.59s; compile PASS. Inventario:
  2244 total / 171 runtime-unbound / 0 sin clasificar; strict classification
  PASS, strict runtime OPEN. Una corrida amplia también detectó dos fallos de
  allowlist de argv de proceso en tests existentes de `test_execution_gateway_v2.py`;
  el test específico de `state.write` pasa y los dos fallos siguen pendientes.
- Duración: `2m48s` (12:51:55–12:54:55 UTC), excluyendo 11.59s de pytest.

## 2026-09-25 — Las pruebas de proceso respetan la allowlist operativa

- Decisión: las pruebas no deben exigir que `process.execute` ejecute código
  Python arbitrario. El caso positivo usa `gh auth status` bajo mock; el caso
  de cwd externo usa el mismo argv permitido y demuestra que se bloquea antes
  de llamar al proceso.
- Evidencia: los 51 tests de `test_execution_gateway_v2.py` pasan en 2.49s;
  Python compile y `git diff --check` PASS.
- Duración: `1m19s` (12:55:00–12:56:22 UTC), excluyendo 2.95s de pytest.

## 2026-09-25 — El CLI de continuidad escribe por `state.write`

- Decisión: el CLI `bago` no crea directorios de estado al arrancar. El handoff
  se reemplaza mediante `write_text_atomic`; PROJECT_STATE y recibos JSON de
  verificación pasan por `bago_utils.save_json` y su owner común.
- Evidencia: 53 pruebas de runtime pasaron en 1.41s; Python compile y
  `git diff --check` PASS. Inventario: 2240 total / 167 runtime-unbound / 0
  sin clasificar; strict classification PASS, strict runtime OPEN. Permanecen
  dos subprocesses directos para Git e invocación de la verificación pedida.
- Duración: `1m56s` (13:01:25–13:03:22 UTC), excluyendo 1.41s de pytest.

## 2026-09-25 — El CLI de continuidad gobierna procesos de verificación

- Decisión: `git rev-parse HEAD` usa el owner `process.inspect` con argv exacto
  y sólo lectura. `bago verify` admite `pytest`/`python -m pytest`; normaliza al
  Python activo, liga argv/cwd en `process.execute` y exige Permit directo TTY
  antes del spawn. Rechaza comandos genéricos e inline Python pre-efecto.
- Evidencia: 110 pruebas focales pasaron en 4.69s; compile, strict
  classification y `git diff --check` PASS. Inventario: 2238 total / 165
  runtime-unbound / 0 sin clasificar; strict runtime OPEN.
- Duración: `5m03s` (13:06:11–13:11:19 UTC), excluyendo 4.69s de pytest.

## 2026-09-25 — Retirada del adaptador GitHub de ejecución paralela

- Decisión: eliminar `backend/.bago/api/github_cli.py`. No tenía consumidores de
  producción; el handler activo usa `process.inspect` con argv de sólo lectura.
  Se retiran sus pruebas unitarias del adaptador para no conservar una segunda
  autoridad sobre el lanzamiento de `gh`.
- Evidencia: contrato GitHub, 5 passed en 0.32s; inventario 2237 total / 164
  runtime-unbound / 0 sin clasificar. Strict classification PASS; strict
  runtime sigue OPEN.
- Duración: `42s` (13:16:07–13:16:49 UTC), excluyendo 0.32s de pytest.

## 2026-09-25 — Autoprueba del motor preflight fuera del runtime

- Decisión: retirar `--test` y el workspace scratch fijo de
  `preflight_engine.py`; mantener sólo la evaluación preflight de producción.
  Las pruebas de la clase se ejecutan en pytest con `tmp_path`.
- Evidencia: 3 pruebas pasaron en 0.17s; compile, búsqueda de referencias,
  strict classification y `git diff --check` PASS. Inventario: 2233 total / 160
  runtime-unbound / 0 sin clasificar; strict runtime OPEN.
- Duración: `1m04s` (13:19:05–13:20:09 UTC), excluyendo 0.17s de pytest.

## 2026-09-25 — Estado de inicio LLM bajo el writer de estado

- Decisión: persistir `llm_start.json` vía `state.write` con raíz explícita;
  la resolución de la raíz headless no materializa directorios.
- Evidencia: 7 pruebas pasaron en 8.01s; compile, strict classification y
  `git diff --check` PASS. Inventario: 2230 total / 157 runtime-unbound / 0
  sin clasificar; strict runtime OPEN.
- Duración neta: `47s` (ventana 13:20:55–13:21:50 UTC), excluyendo pytest.

## 2026-09-25 — Autoprueba del security audit fuera del paquete runtime

- Decisión: retirar la opción `--test` y el fixture tree fijo de
  `bago_security_audit.py`; sus comprobaciones pasan a pytest y `tmp_path`.
- Evidencia: 3 pruebas pasaron en 0.21s; compile, búsqueda de referencias,
  strict classification y `git diff --check` PASS. Inventario: 2227 total / 154
  runtime-unbound / 0 sin clasificar; strict runtime OPEN.
- Duración: `59s` (13:22:48–13:23:47 UTC), excluyendo 0.21s de pytest.

## 2026-09-25 — Blocklist persistida por el writer de estado

- Decisión: `blacklist_models` usa `state.write` para materializar
  `model_blacklist.json`; el writer recibe como raíz permitida el directorio
  canónico del archivo.
- Evidencia: 9 pruebas pasaron en 1.26s; compile, strict classification y
  `git diff --check` PASS. Inventario: 2224 total / 151 runtime-unbound / 0
  sin clasificar; strict runtime OPEN.
- Duración neta: `54s` (13:25:37–13:26:32 UTC), excluyendo pytest.

## 2026-09-25 — RewardStore usa el writer append de estado

- Decisión: persistir recompensas RL como append mediante el owner
  `state.write`, con raíz limitada al directorio RL. Se retiró su mkdir local y
  la opción `--test` que truncaba el archivo para forzar caché fría.
- Evidencia: 2 pruebas pasaron en 0.35s; compile, strict classification y
  `git diff --check` PASS. Inventario: 2221 total / 148 runtime-unbound / 0
  sin clasificar; strict runtime OPEN.
- Duración neta: `1m43s` (13:27:31–13:29:39 UTC), excluyendo 0.35s de pytest.

## 2026-09-25 — Selftests de auto-heal y code metrics en pytest

- Decisión: retirar de ambos ejecutables `--test`, los árboles de scratch
  fijos y la limpieza recursiva; mover su cobertura a pytest con `tmp_path`.
- Evidencia: 4 pruebas pasaron en 0.19s en la corrida final (0.56s total de
  pytest incluyendo la corrida inicial con una aserción incompleta, corregida);
  compile, búsqueda de referencias y `git diff --check` PASS. Inventario:
  2218 total / 143 runtime-unbound / 0 sin clasificar; strict runtime OPEN.
- Duración neta: `1m44s` (13:34:53–13:36:38 UTC), excluyendo las dos corridas.

## 2026-09-25 — Orchestrator v4 elimina la escritura de ruta al configurar

- Decisión: `configure_paths` sólo resuelve el root; la creación ocurre al
  persistir briefs por el writer existente. Se retiró `--test` y su limpieza
  recursiva temporal.
- Evidencia: 11 pruebas pasaron en 1.04s; compile, búsqueda de referencias,
  strict classification y `git diff --check` PASS. Inventario: 2216 total / 141
  runtime-unbound / 0 sin clasificar; strict runtime OPEN.
- Duración neta: `1m24s` (13:38:31–13:39:56 UTC), excluyendo pytest.

## 2026-09-25 — Informe de infraestructura delegado a `state.write`

- Decisión: escribir `.bago/state/infra_status.json` mediante el writer
  servidor y limitar su root al directorio del informe; la ruta se resuelve sin
  crear el directorio por adelantado.
- Evidencia: 3 pruebas pasaron en 3.33s; compile, strict classification y
  `git diff --check` PASS. Inventario: 2214 total / 139 runtime-unbound / 0
  sin clasificar; strict runtime OPEN.
- Duración neta: `39s` (13:41:43–13:42:25 UTC), excluyendo pytest.

## 2026-09-25 — Definiciones dinámicas bajo `agent.definition.write`

- Decisión: generated agent code y `agents/manifest.json` se escriben mediante
  el efecto `agent.definition.write`. El adapter permite replace sólo de
  `agents/<nombre>.py` o `agents/manifest.json` bajo la raíz confiada por el
  helper. Se retiran mkdir y chmod directos.
- Evidencia: 2 pruebas pasaron en 0.23s final; compile, strict classification y
  `git diff --check` PASS. Inventario: 2211 total / 136 runtime-unbound / 0 sin
  clasificar; strict runtime OPEN. También se corrigió `agents` del manifest
  vacío para que sea un mapa, como esperan los consumidores.
- Duración: `5m54s` (13:45:26–13:51:23 UTC), excluyendo ~2.7s de corridas
  pytest. Varias pruebas intermedias fallaron al parchear una identidad Python
  distinta del adapter; se eliminó ese seam y pasó la prueba final.

## 2026-09-25 — El Electron Viewer delega sus diagnósticos al owner de logging

- Decisión: el viewer no materializa `boot.log`, `electron-requests.log` ni
  `.run`. Los diagnósticos se envían a `/desktop/viewer-log`; el handler sólo
  admite loopback, `source=electron-viewer`, tipos `boot`/`request` y mensajes
  acotados, y delega al `StructuredLogger` existente (`logging.append`).
  `scripts/dev.ps1` conserva la única creación de `.run` para el runtime.
- Evidencia: 28 pruebas y 158 subtests pasaron en 1.48s; smoke HTTP del cliente,
  Node syntax, Python compile, strict classification y `git diff --check` PASS.
  Inventario: 2208
  total / 133 runtime-unbound / 0 sin clasificar. Cuatro sinks directos de
  proceso/bootstrap siguen abiertos en el viewer; strict runtime OPEN.
- Duración del cambio: `3m09s` (13:58:35–14:01:44 UTC), excluyendo pruebas.

## 2026-09-25 — Los receipts del PI runner usan el owner `state.write`

- Decisión: los tres writes atómicos de eventos, receipts de herramientas y
  bundle se despachan mediante `server_effects.write_text_atomic`. El target
  debe quedar bajo `workspace/.gabo/integrations/pi/receipts`; el helper
  rechaza escape o componentes simbólicos antes de invocar al gateway y liga
  el request al execution id.
- Evidencia: suite PI: 229 passed, 1 skipped en 13.90s; Python compile, strict
  classification y `git diff --check` PASS. Inventario: 2205 total / 130
  runtime-unbound / 0 sin clasificar. El spawn del sidecar aún está abierto.
- Duración del cambio: `4m05s` (14:06:38–14:10:43 UTC), excluyendo pruebas.
- Nota de verificación: la primera combinación de comandos terminó con error
  por una ruta inexistente añadida por equivocación tras la compilación y el
  inventario; la reejecución separada de compile, strict classification y
  `git diff --check` pasó.

## 2026-09-25 — El WAL de PI usa append durable del owner de estado

- Decisión: `WALStore` deja de crear directorios y mantener handles. Cada
  evento se serializa como una línea y pasa a `append_text_durable` bajo
  `state.write`; se conserva append + fsync antes de aceptar el evento.
  `identity_paths.artifact_component` evita que IDs distintos colisionen al
  convertirlos a nombres de archivo; los IDs ya seguros conservan su ruta.
- Evidencia: 238 pruebas PI pasaron, 1 skipped en 14.93s; Python compile,
  strict classification y `git diff --check` PASS. Inventario: 2203 total /
  128 runtime-unbound / 0 sin clasificar.
- Duración: `1m54s` (14:19:53–14:21:47 UTC), excluyendo pruebas.

## 2026-09-25 — Sidecar de PI bajo el owner canónico de proceso

- Decisión: el spawn de `AgentRunner` usa el efecto server-policy
  `process.sidecar.execute` en el adapter de proceso ya registrado. No se crea
  un segundo owner; el adapter acepta únicamente el `main.js` canónico fijado
  por ruta y SHA-256 y valida identidad, entorno y límites antes de `Popen`.
- Límite de pruebas: shims arbitrarios de protocolo sólo se ejecutan en el
  harness de pytest. El dispatch productivo los bloquea.
- Evidencia: suite PI 238 passed / 1 skipped, registro 5 passed, compile,
  strict classification y diff check PASS. Inventario: 2202 / 126 runtime
  unbound / 0 unclassified. Strict runtime continúa OPEN.

## 2026-09-25 — Owner PI separado del adapter de procesos genérico

- Supersede la asignación de implementación anotada arriba: el efecto
  `process.sidecar.execute` tiene ahora su propio
  `PiSidecarProcessEffectAdapter`, registrado de forma única en el Gateway.
  `ProcessExecutionEffectAdapter` ya no anuncia ni despacha este efecto.
- Motivo: el scanner sólo acredita sinks dentro del span de una clase
  `*EffectAdapter`; la llamada Gateway -> helper no bastaba para enlazar el
  materializador `Popen`. El cambio expresa en el registro la separación que
  ya exige el flujo real, sin exención de inventario.
- Evidencia: PI 239 passed / 1 skipped; Gateway/registry 59 passed; inventario
  27 passed; strict classification PASS. Inventario: 2202 / 125 runtime
  unbound / 0 unclassified. Strict runtime continúa OPEN. La corrección tardó
  3m41s netos, excluyendo 30.30s de pytest en paralelo.

## 2026-09-25 — El buffer de providers no crea un directorio al importar

- Decisión: retirar `BAGO_BUFFER_DIR.mkdir` del import de
  `handlers_provider_buffer.py`; el buffer sólo se almacena en `_BUFFER_STATE`
  y esa ruta configurada no tiene lectores ni escritores.
- Evidencia: prueba de import aislado 1 passed; compile, strict classification
  y diff check PASS. Inventario: 2201 / 124 runtime-unbound / 0 unclassified.

## 2026-09-25 — Persistencia de modelos activos usa un solo owner y clave canónica

- Decisión: `_active_models_path` sólo resuelve la ruta; la escritura existente
  `atomic_json -> state.write` crea el directorio padre y materializa.
  Lectura/escritura requieren un ID exacto de `PROVIDER_CATALOG`; se retira la
  sanitización con pérdida que permitía colisiones entre nombres distintos.
- Evidencia: 12 pruebas de provider y estado legacy pasaron; compile, strict
  classification y diff check PASS. Inventario: 2200 / 123 runtime-unbound /
  0 unclassified. Strict runtime sigue OPEN. El bloque tardó 3m28s netos,
  excluyendo 1.42s de pytest.

## 2026-09-25 — La selección del modelo REPL usa el writer de estado existente

- Decisión: `repl_model_router.save_selection` mantiene su schema, pero
  materializa mediante `atomic_json -> state.write`, sin mkdir, temporal ni
  replace local.
- Evidencia: 11 pruebas de discovery/selection y provider-state pasaron;
  compile, strict classification y diff check PASS. Inventario: 2197 / 120
  runtime-unbound / 0 unclassified. Strict runtime continúa OPEN. El bloque
  tomó 3m08s netos, excluyendo 0.61s de pytest.

## 2026-09-25 — Un owner para memoria SQLite; retirar el índice de sesión duplicado

- Decisión: `database.write` queda registrado en un solo
  `DatabaseWriteEffectAdapter`, con operaciones acotadas a `KnowledgeBase` y
  `EmbeddingStore`. Las fachadas de lectura ya no crean schema ni escriben;
  API, chat y REPL piden autorización antes de mutar. El adapter revalida
  sesión, raíz y target; deriva `source_session` de la sesión activa, serializa
  escrituras por `state_root` y materializa schema/FTS/WAL y embeddings.
- Decisión: retirar `SessionDB`. Sólo lo escribía `SessionPersistenceMixin`; no
  tenía lectores de producto y duplicaba datos ya persistidos en la sesión JSON
  canónica. `ContextStore.list_sessions` usa `sessions/<sid>/meta.json`, no
  `sessions.db`. El receipt de workspace deja de exigir el índice derivado.
- Evidencia: 102 pruebas de memoria/RAG/gateway/inventory y 67 de sesión,
  workspace e inventory pasaron en sus bloques focalizados. `--strict-classification`
  PASS; inventario actual `2336` sinks / `100` runtime-unbound / `0`
  unclassified. `--strict-runtime` FAIL/OPEN (exit `1`); `git diff --check`
  PASS. No es evidencia de cierre global ni de candidato comiteado. La suite
  backend completa y la revisión independiente quedan pendientes. Tiempo de
  cambio reconstruido: ~15m, excluyendo 2m58s de pytest y ~48s de gates de
  inventory; la hora de inicio no quedó capturada con cronómetro.

## 2026-09-25 — El arranque del manager CLI pasa por el owner de proceso

- Decisión: el `Popen` de `bago manager` ya no vive en `cmd_content.py`.
  El CLI presenta challenge y pide confirmación en TTY; el permiso consumido
  se vincula al módulo launcher y su SHA-256, raíz runtime, workspace, UI,
  puerto y host loopback. `ProcessExecutionEffectAdapter` valida de nuevo
  esos datos inmediatamente antes del spawn desacoplado.
- El bloqueo de instancia (`bago.lock`) queda en `bago_core.instance_lock`.
  Sólo `cmd_serve` adquiere/libera el lock; el fichero contiene PID/tiempo para
  coordinación y no transporta autoridad de ejecución.
- Evidencia: prueba focal 4 passed en 4.42s con timeout externo de 60s;
  compile y `git diff --check` PASS; BAGO strict-classification PASS.
  Inventario: 2338 sinks / 96 runtime-unbound / 0 sin clasificar.
  Strict-runtime sigue FAIL/OPEN. No es evidencia de candidato comiteado; la
  suite backend completa y la revisión independiente siguen pendientes.
- Duración reconstruida del cambio: ~4m40s, excluyendo ~37s de compilación,
  pruebas y gates. Las interrupciones impidieron tomar cronómetro exacto.

## 2026-09-25 — Cierre de subprocess obsoleto y vaciado de eventos

- Decisión: `BagoContext.run_tool()` conserva su firma por compatibilidad, pero
  falla cerrado; no tenía callsites dentro del repo y ejecutaba comandos BAGO
  arbitrarios con `subprocess.run` sin autorización. `flush_events(clear=True)`
  deja de hacer `unlink` y reemplaza `events.jsonl` por vacío mediante el owner
  ya registrado `state.write` bajo la raíz del contexto.
- Evidencia: 2 pruebas focales pasaron en 0.23s con timeout externo de 60s;
  compile, BAGO strict-classification y `git diff --check` PASS. Inventario:
  2338 total / 94 runtime-unbound / 0 sin clasificar. Strict-runtime sigue
  OPEN; no existe todavía candidato comiteado ni revisión independiente.
- Duración reconstruida del cambio: ~3m30s, excluyendo ~11s de test y gate;
  aproximada por las interrupciones y el proceso de recuperación del entorno.

## 2026-09-25 — Los marcadores de archivo del modelo ya no escriben

- Decisión: `[WRITE:path]...[/WRITE]` se representa como contenido propuesto;
  no crea directorios ni materializa archivos. Se elimina ese sink directo de
  `SessionTurnMixin`; la escritura real debe pasar por `filesystem.write` y
  su challenge/Permit del Gateway. El flujo de chat no convierte una salida
  de provider en autoridad de filesystem.
- Evidencia: 1 prueba focal passed en 0.15s con timeout externo de 60s;
  compile, strict classification y `git diff --check` PASS. Inventario:
  2336 / 92 runtime-unbound / 0 sin clasificar. Strict-runtime continúa OPEN.
- Duración reconstruida del cambio: ~3m15s, excluyendo ~11s de compile,
  prueba y gate.

## 2026-09-25 — Resolver rutas de sesión deja de crear estado

- Decisión: `state_paths.resolve_state_root` solo resuelve identidad. Se
  retiraron los `mkdir` duplicados de `SessionManager.__init__` y
  `session_registry.mark_active_session`; los writers existentes crean la
  raíz cuando una escritura canónica debe materializarla.
- Evidencia: 19 pruebas de user-state, recuperación/persistencia de sesión y
  activación workspace pasaron en 3.62s; compile, BAGO strict-classification
  y `git diff --check` PASS. Inventario: 2333 / 89 runtime-unbound / 0 sin
  clasificar. Strict-runtime continúa OPEN.
- Duración reconstruida del cambio: ~1m58s, excluyendo ~14s de checks.

## 2026-09-25 — Git identity de sesión usa process.inspect

- Decisión: `_git_info()` deja de invocar `subprocess.run` directamente. Reusa
  `process.inspect`, el owner server-policy ya registrado, limitado a las tres
  consultas Git exactas de solo lectura: `rev-parse HEAD`,
  `rev-parse --show-toplevel` y `rev-parse --abbrev-ref HEAD`. No se crea una
  autoridad de ejecución adicional.
- Evidencia: 57 pruebas focales pasaron en 3.08s bajo timeout externo de 60s;
  `py_compile` y `git diff --check` PASS. El gate directo del inventario dio
  strict-classification PASS (2331 total, 0 sin clasificar) y strict-runtime
  FAIL/OPEN (87 runtime-unbound, antes 89). El wrapper `bago.py verify` no
  pudo arrancar su comando hijo en este Windows (`WinError 2`); por ello se
  ejecutó el scanner directamente bajo timeout de 90s. Sin candidato
  comiteado; suite backend completa y revisión independiente pendientes.
- Duración reconstruida del cambio: ~3m35s (18:48:31–18:52:30 UTC),
  excluyendo aproximadamente 25s de tests, compilación y gates.

## 2026-09-25 — El shim file-write no puede eludir la autorización

- Decisión: el tool legacy `file-write` falla cerrado después de su validación
  de argumentos y ruta; no crea directorios ni escribe, incluso con
  `BAGO_DEV_MODE`. La escritura material sigue disponible por la ruta de sesión
  `/files/write`, que usa challenge, aprobación, Permit y
  `FilesystemEffectAdapter`. El registro explica esa ruta; no se añadió una
  segunda implementación de autorización.
- Evidencia: 47 pruebas focales de tools pasaron en 4.05s bajo timeout externo
  de 60s; `py_compile`, strict-classification y `git diff --check` PASS.
  Inventario: 2329 total / 85 runtime-unbound / 0 unclassified; strict-runtime
  FAIL/OPEN (antes 87). Cambiar el shim limita el escritor standalone CLI; la
  ruta UI/API autorizada existente conserva la capacidad. Sin candidato
  comiteado ni revisión independiente.
- Duración reconstruida del cambio: ~5m40s (18:52:30–18:58:32 UTC),
  excluyendo unos 22s de tests, compilación y gates; estimada porque no había
  cronómetro por comando.

## 2026-09-25 — Materializar piezas usa solo el writer canónico

- Decisión: se retiraron los `mkdir` redundantes para root, categoría y pieza
  en `materialize_piece_store()`. Si falta un manifiesto, `json_write` delega
  en `write_json_atomic` y su owner registrado, que crea los directorios como
  parte de la escritura. Si el manifiesto existe, sus padres ya existen. No se
  cambió la identidad de pieza ni el contenido del manifiesto.
- Evidencia: prueba nueva confirma que el padre no existe antes del writer y
  que el manifiesto aparece después; Node Control split + translator: 29 passed
  en 9.94s con timeout de 60s. Compile, strict-classification y diff check
  PASS. Inventario: 2326 total / 82 runtime-unbound / 0 unclassified;
  strict-runtime FAIL/OPEN (antes 85).
- Duración reconstruida del cambio: ~4m35s (18:58:32–19:03:34 UTC),
  excluyendo unos 25s de pruebas, compilación y gates.

## 2026-09-25 — El plan de AgentOrchestrator persiste vía state.write

- Decisión: `_plan_store_path()` solo resuelve la ruta; elimina el `mkdir`
  anticipado. `save_orchestrator_plan()` sustituye `Path.open(..., "a")` por
  `bago_core.atomic_json.append_text_durable`, que delega la materialización y
  append en el writer server-owned `state.write`. Conserva el JSONL y la ruta
  canónica.
- Evidencia: `test_agent_kit.py`: 43 passed en 3.64s bajo timeout externo de
  60s; prueba nueva observa que el padre aún no existe al invocar al writer.
  Compile, strict-classification y `git diff --check` PASS. Inventario: 2324
  total / 80 runtime-unbound / 0 unclassified; strict-runtime FAIL/OPEN
  (antes 82).
- Duración de cambio estimada: ~1m35s (aprox. 19:06:07–19:08:05 UTC),
  excluyendo ~22s de pruebas, compilación y gates.

## 2026-09-25 — La proyección Android usa state.write

- Decisión: `_write_layers_state()` conserva su ruta `ANDROID_LAYERS_STATE` y
  payload, pero delega el reemplazo JSON al writer existente
  `bago_core.atomic_json.write_json_atomic` (`state.write`). Se eliminaron el
  `mkdir` y `write_text` directos; el informe sigue siendo una proyección
  derivada y no adquiere una autoridad propia.
- Evidencia: prueba focal 1 passed en 0.24s bajo timeout de 60s; verifica la
  delegación y contenido JSON. `py_compile`, strict-classification y
  `git diff --check` PASS. Inventario: 2322 total / 78 runtime-unbound / 0
  unclassified; strict-runtime FAIL/OPEN (antes 80). Un primer intento de test
  falló por importar una función como módulo; corregido y corrida final PASS.
- Duración reconstruida del cambio: ~2m47s (19:08:05–19:11:05 UTC),
  excluyendo unos 13s de prueba, compilación y gates.

## 2026-09-25 — ClaimLedger persiste por state.write sin adquirir autoridad

- Decisión: `ClaimLedger` deja de crear `evidence/` durante construcción y
  ambos logs append-only (`claims.jsonl` y `claim_receipts.jsonl`) escriben
  mediante `bago_core.atomic_json.append_text_durable` (`state.write`). Se
  preservan formato y verificación evidence-backed. `ClaimLedger` sigue siendo
  ledger de afirmaciones/evidencia; no reemplaza ni comparte autoridad con
  `ExecutionClaimStore`, `AuthorizationBoundary` o los Permits del Gateway.
- Evidencia: claim ledger + evidence authority: 16 passed en 13.34s con timeout
  externo de 60s; prueba nueva confirma constructor read-only y append vía
  state writer. Compile, strict-classification y diff check PASS. Inventario:
  2320 total / 75 runtime-unbound / 0 unclassified; strict-runtime FAIL/OPEN
  (antes 78).
- Duración de cambio estimada: ~2m10s (19:11:05–19:13:53 UTC), excluyendo
  unos 34s de tests, compilación y gates.

## 2026-09-25 — Raíces de estado requieren owner y el arranque no poda backups

- Decisión: `state.directory.ensure` usa el único `ServerStateEffectAdapter`
  server-policy; el adapter revalida el root y el conjunto exacto de rutas
  canónicas antes de materializar. Respeta los overrides explícitos del
  contrato (`BAGO_RUNTIME_ROOT` y `BAGO_STATE_ROOT`). `ensure_user_roots()` ya
  no borra backups implícitamente; la rotación expone únicamente
  `backup_prune_candidates()` read-only.
- Evidencia: 77 pruebas focales pasaron en 8.13s con timeout de 60s y basetemp
  dentro del checkout; `py_compile` y `git diff --check` PASS. Un test también
  prueba que un target ajeno se bloquea antes de crear carpeta. Inventario:
  2321 total / 73 runtime-unbound / 0 sin clasificar; strict-classification
  PASS, strict-runtime FAIL/OPEN. Un intento inicial de pytest encontró
  `PermissionError` enumerando el Temp global de Windows; se repitió con
  basetemp local. Duración neta estimada ~12m, excluyendo pruebas/gates.

## 2026-09-25 — AuditTrail persiste mediante state.write

- Decisión: `OperationalIntegrity.AuditTrail` sigue siendo ledger de evidencia,
  pero delega su append JSONL en `atomic_json.append_text_durable`
  (`state.write`). Se eliminaron la creación de directorio y la apertura directa.
- Evidencia: 21 pruebas de `test_operational_integrity.py` y
  `test_claim_ledger_split.py` pasaron en 16.05s; `py_compile`,
  strict-classification y `git diff --check` PASS. Inventario: 2319 total / 71
  runtime-unbound / 0 sin clasificar; strict-runtime FAIL/OPEN. La duración neta
  se estima en ~5m, excluyendo pruebas y gates.

## 2026-09-25 — La identidad del candidato inspecciona Git por Gateway

- Decisión: `candidate_identity` reutiliza `process.inspect` para sus consultas
  Git exactas de solo lectura. Se amplió el allowlist cerrado para status,
  remote, upstream, rama y diff; `safe.directory` solo admite rutas absolutas.
  La salida de diff se hashea dentro del adapter para preservar el fingerprint
  completo aunque exceda el límite de stdout de receipts.
- Evidencia: 63 pruebas de sesión Git, Gateway y recibos de candidato pasaron en
  25.98s bajo timeout de 90s; compile, strict-classification y diff-check PASS.
  Inventario: 2317 total / 69 runtime-unbound / 0 sin clasificar;
  strict-runtime FAIL/OPEN. Duración de cambio reconstruida ~7m, excluyendo
  pruebas y gates.
