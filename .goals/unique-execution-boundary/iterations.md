# UNIQUE_EXECUTION_BOUNDARY iteration log

Durations are wall time reported by the commands in this worktree. The full
backend suite result below predates the current session-mirror tranche and is
not final-candidate evidence.

## 2026-09-25 — plan process integration and frontend authorization flow

| Block | Duration | Result |
| --- | ---: | --- |
| Pipeline/gateway/inventory focal tests | 21.78s | `68 passed` |
| Full backend suite | 267.93s | `1365 passed, 3 skipped, 198 subtests`; predates the session-mirror edits |
| Frontend API client test | 13.28s command (`1.08s` Vitest) | `21 passed` |
| Frontend typecheck | 10.51s | PASS |
| Frontend production build | 2.59s | PASS, `123 modules` |
| Strict runtime inventory | about 10s | FAIL, exit `2`, `437` runtime-unbound |

## 2026-09-25 — session workspace mirror gateway tranche

| Block | Duration | Result |
| --- | ---: | --- |
| Initial mirror/gateway/workspace focal suite | 2.91s | `55 passed` |
| Mistyped test target | under 1s | pytest error: nonexistent test file; `0` tests ran; corrected immediately |
| Focal suite after routing changes | 5.08s | `60 passed` |
| Related session/workspace regression before symlink-path recheck | 90.29s | `259 passed, 1 skipped, 8 subtests` |
| Regression after symlink-path recheck | 86.42s | `258 passed, 2 failed, 1 skipped, 8 subtests`; Windows `Path.resolve()` changed the long profile path to its `AMTEC_~1` alias, causing valid mirror destinations to fail closed |
| Isolated two affected workspace tests | 1.46s | `2 failed`, reproducing the alias mismatch |
| Corrected path validation target | 2.77s | `11 passed`; adapter now checks lexical components for symlinks without collapsing the long path alias |
| Final related session/workspace regression | 89.87s | `260 passed, 1 skipped, 8 subtests` |
| Strict classification and diff checks | about 18s inventory plus local checks | PASS, `0` unclassified; `git diff --check` PASS |
| Strict runtime inventory | about 18s with classification | FAIL, exit `2`, `433` runtime-unbound |

### Net result and remaining work

- `SessionWorkspaceMirrorEffectAdapter` owns mirror `rmtree/copytree/mkdir`;
  the inventory moved from `437` to `433` runtime-unbound. The effect
  inventory total is `2108` because adapter findings remain visible.
- The effect registry is now version `1.1.0` with policy-only
  `workspace.mirror.prepare`.
- `SessionManager.state_dir.mkdir`, `attach_context`, `sync_workspace_mirror`,
  installer/Electron effects, full backend suite on this code, committed
  candidate evidence and independent review remain open.

## 2026-09-25 — workspace mirror sync authorization tranche

| Measure | Duration / result |
| --- | ---: |
| Implementation window (first edit to final source edit; file timestamps, not active typing time) | about 14m29s, 03:22:58–03:37:27 Madrid |
| Final backend focal suite | 37.64s; `68 passed` |
| Frontend API client suite | 0.447s Vitest; `22 passed` |
| Frontend typecheck | PASS; duration not separately timed |
| `--strict-classification` | PASS; `0` unclassified scope/binding |
| `--strict-runtime` | FAIL/OPEN, exit `2`; `430` runtime-unbound |

`workspace.mirror.sync` is now an explicit canonical effect owned by
`WorkspaceMirrorSyncEffectAdapter`. `/project/sync` performs challenge →
approve → one-time Permit → gateway execution; the adapter binds the active
session, source mirror, target project, workspace identity and digest, then
revalidates under a per-session lock before copying. It reuses the existing
SessionManager mirror-exclusion policy and skips symlinks. The legacy command
and direct SessionManager method fail closed. The UI now asks for visible
confirmation before the implicit workspace-activation sync path.

Negative gateway coverage proves a changed destination blocks before copying;
the HTTP lifecycle test proves no materialization before approval and copies
only after Permit consumption. Inventory moved from `433` to `430` runtime-
unbound; sink totals rose from `2108` to `2114` because adapter and test sinks remain
visible. This is `EXECUTED / SCOPED`; full backend suite, strict runtime,
committed candidate and independent final review remain open. The 14m29 figure
is an implementation timestamp window, not net hands-on time; some checks ran
while this tranche was being refined.

## 2026-09-25 — context attachment authorization tranche

| Measure | Duration / result |
| --- | ---: |
| Source-change window (file timestamps; includes debug/verification loop) | 7m08s, 03:43:08–03:50:16 Madrid |
| Context adapter + HTTP pre-effect gate | 5 passed in 0.66s |
| API route metadata | 22 passed, 143 subtests in 0.82s |
| Frontend API + context regressions | 30 passed in 0.444s; typecheck PASS |
| Compile, registry JSON, diff check | PASS |
| Strict classification | PASS; 0 unclassified scope/binding |
| Strict runtime | FAIL/OPEN, exit 2; 425 runtime-unbound |

workspace.context.attach is now a registered explicit effect. The
ContextAttachEffectAdapter binds the session, source root, context destination,
resolved selection and content digest; requires the exact consumed Permit;
rechecks the source before and after copying; excludes symlinks; stages into a
temporary bundle and publishes it with os.replace. /context/attach owns
challenge → approve → execute. The React command surface asks for visible
confirmation and sends the selected path as data, preserving spaces. The
generic command and direct SessionManager.attach_context() paths fail closed.

The first two gateway/API attempts failed: the adapter compared a 4-field
identity with a 3-field recheck tuple, and operation-fingerprint mismatch was
mapped to HTTP 403. Both were corrected; final route, adapter and frontend
checks pass. Inventory moved from 430 to 425 runtime-unbound (2120 total);
adapter/test findings remain in the inventory. Full backend suite, committed
candidate, strict-runtime closure and independent review remain open. The
7m08s figure is the source-change window, not pure active editing time.

## 2026-09-25 — detached release-update helper authorization tranche

| Measure | Duration / result |
| --- | ---: |
| Source-change window (first-edit clock marker to last implementation-file timestamp; includes debugging, excludes test wall time as a separate metric) | 12m23s, 04:05:46–04:18:09 Madrid |
| Helper/application focused tests | 6 passed in 12.05s |
| Update manager + inventory regression | 30 passed in 32.47s |
| Python compile | PASS |
| Strict classification | PASS; 0 unclassified scope/binding |
| Strict runtime | FAIL/OPEN; 408 runtime-unbound |

`system.update.apply` now emits a one-use helper ticket only after a strong
direct-user Permit is consumed and the prepared target is revalidated. Permit
consumption persists the exact executed request descriptor in the canonical
AuthorizationBoundary ledger. `apply_release_update.ps1` validates that
consumed ledger entry, the direct-interaction proof/decision, the exact bundle,
installation, state path, version, helper path/hash and restart arguments; it
then claims the ticket before any other effect. Tests cover ticket dispatch
from a real challenge/approve/consume flow, successful component replacement,
forged/missing authorization denied before materialization, and changed target
denied before materialization. Its effect sinks stay visible and count as the
registered adapter's delegated implementation. Inventory moved from 425 to
408 runtime-unbound; totals are 2131 with zero unclassified. This is scoped
progress only; global closure, committed candidate, full backend suite and
independent final review remain open.

## 2026-09-25 — debt-guard fixture separation

| Measure | Duration / result |
| --- | ---: |
| Source-change window (clock marker to last implementation-file timestamp) | 43s, 04:25:51–04:26:34 Madrid |
| Dedicated debt-guard pytest module | 3 passed in 0.24s |
| Python compile and `git diff --check` | PASS |
| Strict classification | PASS; 0 unclassified scope/binding |
| Strict runtime | FAIL/OPEN; 403 runtime-unbound |

The five temporary fixture write sinks were moved from
`backend/.bago/tools/debt_guard.py` into `backend/tests/test_debt_guard.py`.
The old `--test` flag now points to pytest and performs no mutation. These
five effects remain visible under test scope; total inventory stays `2131`
while runtime-unbound moves from `408` to `403`. The seven real config, Git
inspection and pre-commit hook sinks remain unbound. This does not close the
debt-guard runtime path, the global gate, the full backend suite, candidate
commit or independent review.

## 2026-09-25 — Electron release signature and bundle staging gateway tranche

| Measure | Duration / result |
| --- | ---: |
| Source/change window (includes design/debug; test wall time reported separately) | about 15m50s, 04:35:42–04:51:32 Madrid |
| Focused gateway, adapter, registry and route suite | 37 passed, 145 subtests in 1.63s |
| Electron release-job regression | PASS (`cancel_resume`, checksum, install, rollback and delete) |
| JavaScript syntax, Python compile and `git diff --check` | PASS |
| Strict classification | PASS; 0 unclassified scope/binding |
| Strict runtime | FAIL/OPEN, exit 1; 400 runtime-unbound |

`release-job-manager.cjs` now delegates GPG verification and ZIP expansion to
the backend API, whose fixed handlers dispatch `release.signature.verify` and
`release.bundle.stage` through `ExecutionGateway`. The ZIP adapter preflights
paths, symlinks, file/directory collisions, entry count and expanded size
before creating staging data, then publishes the extracted tree from a
temporary directory. Its old GPG and `Expand-Archive` process calls are gone.
The manager still owns job/cache/log state, download, installer execution,
backup/rollback and taskkill; 21 sinks in this file remain runtime-unbound.
Final inventory is 2,155 sinks / 400 runtime-unbound, with 0 unclassified.
This is
`EXECUTED / SCOPED`, not global closure. Full backend suite, commit, strict
runtime zero and independent review remain open.

## 2026-09-25 — Electron release-job state and log gateway tranche

| Measure | Duration / result |
| --- | ---: |
| Source/change window (includes design/debug; test wall time separate) | about 11m50s, 04:56:04–05:07:54 Madrid |
| Focused gateway/API/registry/security tests | 57 passed, 147 subtests in 6.21s |
| Electron release manager regression | PASS: cancel/resume, checksum, install, rollback, archive/delete |
| Crash-boundary recovery regression | PASS: persisted restart and 3 destructive boundaries |
| JS syntax, Python compile and `git diff --check` | PASS |
| Strict classification | PASS; 0 unclassified scope/binding |
| Strict runtime | FAIL/OPEN, exit 1; 396 runtime-unbound |

The manager's state and log calls now cross the existing local API bridge;
only fixed backend handlers can build these requests, and the adapters derive
paths from `job_id`. Persistence is awaited before changed events or dependent
job stages. Four direct manager sinks (initial state-directory creation,
atomic state write/replace, and log append) moved under the gateway. The
remaining 18 unbound sinks in this file are archive/delete, release-cache and
download writes, backup/rollback moves, installer spawn and taskkill. Total
inventory is 2,168 / 396 runtime-unbound / 0 unclassified. This is
`EXECUTED / SCOPED`; full backend suite, commit and independent final review
remain open.

## 2026-09-25 — Explicit Electron release-job archive gateway tranche

| Measure | Duration / result |
| --- | ---: |
| Source-change window (first clock marker to last implementation-file timestamp; checks reported separately) | 11m14s, 05:11:14–05:22:28 Madrid |
| Focused gateway/API/registry/route tests | 38 passed, 148 subtests in 1.83s |
| Electron manager + persisted-restart + IPC confirmation regressions | PASS; grouped syntax/test/diff command 9.35s |
| Strict classification | PASS; 0 unclassified scope/binding |
| Strict runtime | FAIL/OPEN, exit 1; 389 runtime-unbound |

The persisted terminal-job archive now has canonical effect `release.job.archive`
and a registered adapter. The Electron main process presents a native
confirmation bound to the job ID; after approval, the existing Authorization
Boundary issues a one-time Permit and the API handler dispatches through the
ExecutionGateway. The operation fingerprint binds the persisted-state digest
and archive timestamp. The adapter validates the consumed direct-user proof,
exact state identity, terminal status and safe paths before creating/moving
anything; if a move fails it restores inputs, and if rollback also fails it
preserves the partial archive and reports its recovery path. The renderer's
duplicate confirmation was removed. Eight Electron runtime sinks moved out
of `release-job-manager.cjs`; its remaining 10 are release cache/download,
backup/rollback, installer spawn and taskkill. Global inventory is 2,180 /
389 runtime-unbound / 0 unclassified. This tranche is `EXECUTED / SCOPED`;
full backend suite, strict runtime zero, candidate commit and independent
review remain open.

## 2026-09-25 — PowerShell persistent-setting sink detection

| Measure | Duration / result |
| --- | ---: |
| Source-change window (first clock marker to last implementation-file timestamp; checks reported separately) | 1m21s, 05:30:33–05:31:54 Madrid |
| Inventory/registry focused tests | 24 passed in 24.56s |
| Strict classification | PASS; 0 unclassified scope/binding |
| Strict runtime | FAIL/OPEN, exit 1; 395 runtime-unbound |

The PowerShell scanner previously missed persistent PATH/registry writes made
through `New-ItemProperty`, `Set-Item`, and
`Environment.SetEnvironmentVariable`, plus direct .NET `File.WriteAllText` /
related methods. It now recognizes these call forms and binds their findings to
canonical effect IDs. This exposed six runtime sinks in `install-v4.ps1` and
other runtime paths; its inventory rises from 41 to 47, including five
`system.configuration.write` operations. Total inventory is 2,198 / 395
runtime-unbound / 0 unclassified. This closes only the scanner-coverage
sub-block; it does not migrate those sinks or close the runtime gate.

## 2026-09-25 — Correct installer authorization sequencing

| Measure | Duration / result |
| --- | ---: |
| Source/documentation change window | 2m04s, 05:44:49–05:46:53 Madrid |
| Installer focused tests | NOT_RUN; documentation/design correction only |
| `git diff --check` | PASS (existing line-ending warnings only) |
| Installer sink migration | NOT_RUN; 47 remain open |

Source review found an ordering hole in the prepared installer design:
`install-v4.ps1` self-elevates through `Start-Process -Verb RunAs` before the
main install sequence, and guided provider/configuration choices are collected
interactively. The helper must reject missing/invalid authorization before the
elevation process launch and independently revalidate the consumed Permit,
helper identity and complete operation in the elevated child. All material
choices must be bound before challenge/approval or collected in a non-material
preparation phase. Remote download/extraction remain separately owned; the
staged bundle identity must be bound to the install request. This supersedes
the weaker child-only validation order in the prior proposal. The correction
changes implementation sequencing, not goal status or gate counts.

## 2026-09-25 — Install operation identity foundation

| Measure | Duration / result |
| --- | ---: |
| Source-change window | 1m52s, 05:53:21–05:55:13 Madrid |
| Focused plan tests | 8 passed in 0.32s |
| Python compile | PASS |
| Scoped sink inventory (`install_plan.py`) | 0 findings |
| Runtime paths routed | 0; AuthorizationBoundary/Gateway/helper wiring remains open |

Added a pure install-plan descriptor that binds source tree and helper hashes,
destination, action, selected mode, allowlisted flags, package identity, and a
secret-free digest for provider/configuration choices. Tests prove changes to
source, helper, target, mode, or config invalidate the operation digest and
that unselected modes, unknown options, external helpers and source symlinks
are rejected. This prepares the operation fingerprint for the upcoming
authorization owner; it does not itself route or close any installer sink.

## 2026-09-25 — Enrutar releases del Manager heredado por release-job

| Medida | Duración / resultado |
| --- | ---: |
| Bloque de cambio (trazado, implementación y cierre; pruebas aparte) | 9m23s, 05:46:49–05:56:12 UTC |
| Tests de contrato y seguridad | 15 passed en 3.74s |
| Sintaxis Node (`legacy-manager.js`, `preload.cjs`) | PASS |
| Strict classification | PASS; 2252 sinks y cero sin clasificar |
| Strict runtime | FAIL/OPEN; 328 runtime-unbound |
| `git diff --check` | PASS; advertencias preexistentes de CRLF |

Los botones de instalación/actualización de release del Manager Electron ya no
construyen un comando PowerShell que lanza `install-remote.ps1`. Ahora crean un
release-job, esperan su preparación/verificación y solicitan instalación por
`system.install.apply`, que conserva la confirmación nativa. Se quitó el bridge
`buildInstallCommand` del preload y se añadió limpieza del listener IPC tras
terminar la espera del job. El bootstrap remoto sigue siendo una superficie
material viva para instalación sin backend; no se reclasificó ni ocultó y sus
10 sinks siguen abiertos. `rollback-bago.ps1` también continúa abierto con 9
sinks aunque la búsqueda actual no encontró caller productivo. Este bloque no
reduce el inventario; elimina la ruta directa desde la UI activa y prepara el
trabajo separado de autoridad de bootstrap.

## 2026-09-25 — Enrutar las operaciones locales de instalación Electron

| Medida | Duración / resultado |
| --- | ---: |
| Bloque de cambio (trazado, implementación y cierre; pruebas aparte) | 17m20s, 05:56:12–06:13:32 UTC |
| Tests focales Python | 26 passed en 3.88s |
| Cliente Electron `system-install-client.cjs` | PASS; challenge, confirmación, execute, cancelación y action repair |
| Sintaxis Node (5 módulos Electron) | PASS |
| Parser PowerShell 7 (`install-v4.ps1`) | PASS |
| Strict classification | PASS; 2252 sinks, 0 scope/binding sin clasificar |
| Strict runtime | FAIL/OPEN, exit 2; 327 runtime-unbound |
| `git diff --check` | PASS; advertencias de CRLF preexistentes |

Las acciones de instalación inicial, reparación, reinstalación, copia nueva y
actualización desde fuente ya no llaman `dependency-service.runInstallScript`.
Todas preparan una operación `system.install.apply`, muestran confirmación
nativa ligada a source/helper/configuration hashes y ejecutan el helper con el
ticket consumido. Se eliminó el spawn duplicado de instalación de
`dependency-service.cjs`. En reparación, `install-v4.ps1` preserva los dos
archivos de configuración existentes; el store externo no se sobrescribe con
un payload vacío. La nueva instalación mantiene configuración neutral.

El scanner baja de 328 a 327 runtime-unbound; añadió un sink del propio test de
contrato y el total permanece 2252. Siguen directos el `git pull` previo a la
autorización de `source-update`, la desinstalación Electron, el bootstrap
`install-remote.ps1` (10) y `rollback-bago.ps1` (9). La suite backend completa,
candidato comiteado y review independiente siguen abiertos.

## 2026-09-25 — Mover el autotest de infraestructura a pytest

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (12:37:23–12:39:26 UTC; pruebas aparte) | 2m03s |
| Pytest focal | 3 passed en 3.24s |
| Python compile / strict classification / `git diff --check` | PASS |
| Strict runtime | FAIL/OPEN; 193 runtime-unbound |

Eliminé `--test` y sus fixtures de servidor/workspace de `bago_infra_scan.py`;
los casos de detección HTTP, extracción de modelos, reporte y persistencia ahora
están en `backend/tests/test_bago_infra_scan.py`. El inventario bajó de 196 a
193 runtime-unbound y conserva cero hallazgos sin clasificar. Quedan en el
módulo los sinks productivos de `netstat` y escritura del informe, aún abiertos.
Duración excluye 3.24s de pytest.

## 2026-09-25 — Retirar el autotest peligroso de `agent_router`

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (12:39:26–12:43:11 UTC; pruebas aparte) | 3m42s |
| Suite focal `test_agent_router_cabinet.py` | 26 passed en 2.54s |
| Python compile / strict classification / `git diff --check` | PASS |
| Strict runtime | FAIL/OPEN; 187 runtime-unbound |

Eliminé `agent_router --test`, cuyo propio flujo de prueba escribía el manifiesto
y archivos `roles/` de `BAGO_ROOT` real. Sus expectativas CLI/JSON y el rechazo
del switch viven ahora en pytest temporal. También quité el `state.mkdir` de
`configure_paths`: resolver rutas ya no materializa estado durante una lectura;
`save_json` crea el padre cuando hay una escritura funcional. El inventario bajó
de 193 a 187 runtime-unbound; clasificación global sigue sin hallazgos abiertos.
Duración excluye 2.54s de pytest.

## 2026-09-25 — GitHub usa el dueño común de procesos

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (12:19:59–12:33:25 UTC; pruebas aparte) | 12m23s |
| Suite focal Python | 44 passed en 32.03s; tres expectativas antiguas corregidas tras el primer intento |
| Cliente Electron proceso | PASS; challenge, confirmación nativa, Permit consumido y token oculto en el diálogo |
| TypeScript | `npm run typecheck` PASS |
| Python compile / sintaxis Node / `git diff --check` | PASS |
| Strict classification | PASS; 2269 sinks, cero sin clasificar |
| Strict runtime | FAIL/OPEN; 196 runtime-unbound |

Las lecturas autenticadas `gh auth status` y `gh api` ahora se despachan por
`process.inspect` con allowlist exacta, sesión y cwd activos. Auth login/logout
y `gh repo create` usan el cliente Electron `process.execute`, con argv
limitado y aprobación desktop; el token de login se oculta en el diálogo. Se
retiró la creación duplicada del tool MCP y las rutas HTTP mutadoras antiguas
responden 410. El inventario bajó de 200 a 196 runtime-unbound.

La suite total, strict runtime, commit y revisión independiente siguen abiertos.
Duración excluye 62.98s de pytest (dos corridas focales); un comando inicial
intentó pasar un archivo CJS a pytest y se repitió con Node correctamente.

## 2026-09-25 — Sacar autotests destructivos de tres herramientas de orquestación

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (12:45:22–12:49:19 UTC; pruebas aparte) | 3m56s |
| Suite focal | 8 passed en 0.67s |
| Python compile / `git diff --check` | PASS |
| Strict classification | PASS; 2248 sinks, cero sin clasificar |
| Strict runtime | FAIL/OPEN; 175 runtime-unbound |

Se retiraron `--test` y los scratch trees con borrado recursivo de `toolsmith`,
`skill_engine` y `spiral_agent`; también se eliminó el autotest trivial que
generaba la plantilla de herramientas. `backend/tests/test_orchestration_tools.py`
cubre asignación de toolboxes, persistencia de skill y ciclo del agente con
`tmp_path`, además de verificar que resolver rutas no materializa estado y que
el CLI rechaza el antiguo switch. `save_json` conserva la creación de carpetas
cuando ocurre una escritura funcional.

El inventario baja de 187 a 175 runtime-unbound. La suite total, strict runtime,
commit y revisión independiente siguen abiertos. Duración excluye 0.67s de
pytest.

## 2026-09-25 — Unificar el writer JSON compartido detrás de `state.write`

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (12:51:55–12:54:55 UTC; pruebas aparte) | 2m48s |
| Suite focal | 13 passed en 11.59s |
| Python compile | PASS |
| Strict classification | PASS; 2244 sinks, cero sin clasificar |
| Strict runtime | FAIL/OPEN; 171 runtime-unbound |

`bago_utils.save_json` ahora despacha por `ExecutionGateway`/`state.write`,
acota el destino al `.bago` del proyecto y falla cerrado para archivos fuera
de ese límite. `get_state_dir` sólo resuelve la ruta; se retiró el `mkdir`
directo de la API no usada `ensure_subdir` y el `--test` sin valor funcional.
Los consumidores existentes mantienen el API común sin duplicar el writer.

El inventario baja de 175 a 171 runtime-unbound. En la primera corrida un test
de inventario esperaba sinks ya eliminados y fue corregido. También se lanzó
por error la suite completa de `test_execution_gateway_v2.py`: falló en dos
tests de allowlist de argv de procesos. La entrada siguiente documenta su
corrección de expectativas y la suite completa verde. Duración excluye 11.59s
de pytest.

## 2026-09-25 — Alinear las pruebas de procesos con la allowlist exacta

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (12:55:00–12:56:22 UTC; pruebas aparte) | 1m19s |
| Gateway v2 completo | 51 passed en 2.49s |
| Python compile / `git diff --check` | PASS |

Las dos expectativas que permitían `python -c` arbitrario se sustituyeron por
un `gh auth status` permitido y simulado; la prueba de cwd fuera del workspace
usa ahora una petición que sí supera la allowlist y confirma el bloqueo antes
del spawn. No se amplió la autoridad ejecutable. Duración excluye 2.95s de
pytest (corrida filtrada más suite Gateway v2 completa).

## 2026-09-25 — El CLI `bago` delega su estado al writer compartido

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (13:01:25–13:03:22 UTC; pruebas aparte) | 1m56s |
| Pruebas runtime del CLI | 53 passed en 1.41s |
| Python compile / `git diff --check` | PASS |
| Strict classification | PASS; 2240 sinks, cero sin clasificar |
| Strict runtime | FAIL/OPEN; 167 runtime-unbound |

Quité la creación eager de cuatro directorios en cada arranque. El handoff
Markdown usa `write_text_atomic`; el estado y los recibos JSON de `verify`
usan el writer compartido `save_json`, ambos bajo `ExecutionGateway`. Añadí
pruebas de persistencia en `.bago` temporal y moví las pruebas de `verify` a
raíces temporales. Quedan dos `subprocess.run` en este CLI para identidad Git
y ejecución de la verificación solicitada. Duración excluye 1.41s de pytest.

## 2026-09-25 — El CLI de continuidad gobierna procesos de verificación

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (13:06:11–13:11:19 UTC; pruebas aparte) | 5m03s |
| Suite Gateway/CLI | 110 passed en 4.69s |
| Python compile / `git diff --check` | PASS |
| Strict classification | PASS; 2238 sinks, cero sin clasificar |
| Strict runtime | FAIL/OPEN; 165 runtime-unbound |

`git rev-parse HEAD` usa `process.inspect` y allowlist exacta de sólo lectura.
`bago verify` sólo acepta `pytest` o `python -m pytest`, normaliza al Python
activo y usa `process.execute` con Permit directo TTY ligado a cwd/argv antes
del spawn. Inline Python y comandos arbitrarios fallan antes del efecto. Los
dos subprocesses del CLI quedan retirados. Duración excluye 4.69s de pytest.

## 2026-09-25 — Retirada del adaptador GitHub duplicado

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (13:16:07–13:16:49 UTC; pruebas aparte) | 42s |
| Contrato GitHub | 5 passed en 0.32s |
| Strict classification | PASS; 2237 sinks, cero sin clasificar |
| Strict runtime | OPEN; 164 runtime-unbound |

`handlers_github` ya despacha las lecturas permitidas por `process.inspect`.
El adaptador aislado `github_cli.py` no tenía imports de producción y mantenía
un `subprocess.run` paralelo al owner canónico; lo retiré junto con sus pruebas
aisladas. El contrato de handlers GitHub sigue cubierto. Duración excluye
0.32s de pytest.

## 2026-09-25 — Selftest de preflight trasladado a pytest

| Medida | Resultado |
| --- | ---: |
| Bloque de cambios (13:19:05–13:20:09 UTC; pruebas aparte) | 1m04s |
| Pruebas de preflight | 3 passed en 0.17s |
| Python compile / búsqueda de referencias / `git diff --check` | PASS |
| Strict classification | PASS; 2233 sinks, cero sin clasificar |
| Strict runtime | OPEN; 160 runtime-unbound |

Retiré `--test`, el scratch destructivo fijo y sus cuatro sinks del runtime.
Las comprobaciones de archivo, entorno, comando, warning y forma JSON ahora
usan `tmp_path`; también se confirma que la opción retirada se rechaza.
Duración excluye 0.17s de pytest.

## 2026-09-25 — Estado de arranque LLM delegado al writer común

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:20:55–13:21:50 UTC, menos pytest) | 47s |
| Pruebas de arranque Ollama/LLM | 7 passed en 8.01s |
| Python compile / strict classification / `git diff --check` | PASS |
| Strict runtime | OPEN; 157 runtime-unbound |

`llm_start.json` usa `server_effects.write_text_atomic` acotado a su raíz de
estado. Quité la creación anticipada del directorio de estado y de la ruta
headless; la prueba comprueba que resolverla no escribe. Duración excluye
8.01s de pytest.

## 2026-09-25 — Autoprueba del security audit trasladada a pytest

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:22:48–13:23:47 UTC, menos pytest) | 59s |
| Pruebas del security audit | 3 passed en 0.21s |
| Python compile / referencias / `git diff --check` | PASS |
| Strict classification | PASS; 2227 sinks, cero sin clasificar |
| Strict runtime | OPEN; 154 runtime-unbound |

Retiré `--test`, su árbol de fixtures dentro del paquete y el borrado
recursivo. La detección/exclusión de tokens, permisos e ignore de `.env`, score
y remediation ahora se prueban en pytest, usando `tmp_path` para archivos.
Duración excluye 0.21s de pytest.

## 2026-09-25 — Blocklist de modelos delegada a `state.write`

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:25:37–13:26:32 UTC, menos pytest) | 54s |
| Gateway writer + legacy user state | 9 passed en 1.26s |
| Python compile / strict classification / `git diff --check` | PASS |
| Strict runtime | OPEN; 151 runtime-unbound |

`model_blacklist.json` se serializa por `server_effects.write_text_atomic`
con trusted root en su directorio. Eliminé el mkdir, temporal, replace y
cleanup duplicados del módulo. Duración excluye 1.26s de pytest.

## 2026-09-25 — Recompensas RL anexadas por el gateway

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:27:31–13:29:39 UTC, menos pytest) | 1m43s |
| Pruebas RL | 2 passed en 0.35s |
| Python compile / strict classification / `git diff --check` | PASS |
| Strict runtime | OPEN; 148 runtime-unbound |

`RewardStore.append` usa `append_text_durable` acotado al directorio RL y ya no
crea el directorio directamente. Quité el `--test` inline, que truncaba el
archivo de recompensas para comprobar una caché fría; pytest ahora cubre append,
recarga desde disco, selección y feedback con estado temporal aislado. Duración
excluye 0.35s de pytest.

## 2026-09-25 — Selftests de auto-heal y métricas retirados del runtime

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:34:53–13:36:38 UTC, menos dos corridas pytest) | 1m44s |
| Pruebas finales | 4 passed en 0.19s |
| Python compile / referencias / `git diff --check` | PASS |
| Strict classification | PASS; 2218 sinks, cero sin clasificar |
| Strict runtime | OPEN; 143 runtime-unbound |

Eliminé los scratch fijos y borrados recursivos de ambos selftests. Su
cobertura de scan, reparación JSON, tamaños, métricas, extensiones y exclusión
de dependencias ahora usa `tmp_path`. La primera aserción omitió la reparación
del JSON vacío; se corrigió y la corrida final pasó. Duración excluye las dos
corridas (0.56s total).

## 2026-09-25 — Orchestrator v4 resuelve rutas sin materializar estado

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:38:31–13:39:56 UTC, menos pytest) | 1m24s |
| Pruebas de orchestrator/orchestration tools | 11 passed en 1.04s |
| Python compile / referencias / strict classification / `git diff --check` | PASS |
| Strict runtime | OPEN; 141 runtime-unbound |

`configure_paths` ya no crea `state/orchestrator`; el writer común existente
materializa el estado al guardar un brief. Retiré el selftest con `mkdtemp` y
borrado recursivo; pytest cubre el ciclo y la CLI en `tmp_path`. Duración
excluye 1.04s de pytest.

## 2026-09-25 — Informe de infraestructura por el writer de estado

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:41:43–13:42:25 UTC, menos pytest) | 39s |
| Pruebas de infra scan | 3 passed en 3.33s |
| Python compile / strict classification / `git diff --check` | PASS |
| Strict runtime | OPEN; 139 runtime-unbound |

El informe fijo `infra_status.json` ahora usa `write_text_atomic` con raíz
limitada a su directorio. Quité el mkdir y la escritura directa. Las pruebas
confirman contenido y ruta dentro de estado aislado. Duración excluye 3.33s de
pytest.

## 2026-09-25 — Definiciones dinámicas de agente bajo su efecto canónico

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:45:26–13:51:23 UTC, menos pytest) | 5m54s |
| Pruebas de agent definition | 2 passed en 0.23s final |
| Python compile / strict classification / `git diff --check` | PASS |
| Strict runtime | OPEN; 136 runtime-unbound |

Las escrituras de código y manifest usan `agent.definition.write`; su adapter
admite sólo replace en `agents/<nombre>.py` y `agents/manifest.json` dentro de
la raíz enlazada al request. Quité mkdir y chmod directos. Corregí también el
manifest vacío: `agents` debe ser mapa, no lista. La prueba confirma bloqueo
antes de escribir fuera de ese namespace. Las primeras pruebas no podían
sustituir la raíz por una importación duplicada del adapter; la prueba final
usa el owner real y pasó. Duración excluye ~2.7s de corridas pytest.

## 2026-09-25 — Diagnósticos del Electron Viewer bajo el owner de logging

| Medida | Resultado |
| --- | ---: |
| Cambio neto (13:58:35–14:01:44 UTC; pruebas excluidas) | 3m09s |
| Pruebas API/logger | 28 passed, 158 subtests en 1.48s |
| Viewer client HTTP smoke / Node syntax / Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2208 total / 133 runtime-unbound / 0 unclassified |

El viewer envía sus diagnósticos de arranque y requests al `StructuredLogger`
existente por `/desktop/viewer-log`, que limita cliente a loopback, source,
categorías y tamaño. Se quitaron las escrituras locales de `boot.log` y
`electron-requests.log`; la creación de `.run` queda en `scripts/dev.ps1`.
Los cuatro sinks directos de proceso/bootstrap del viewer continúan abiertos;
strict runtime sigue OPEN. Duración excluye las pruebas.

## 2026-09-25 — Receipts de PI bajo el owner `state.write`

| Medida | Resultado |
| --- | ---: |
| Cambio neto (14:06:38–14:10:43 UTC; pruebas excluidas) | 4m05s |
| Suite de integraciones PI | 229 passed, 1 skipped en 13.90s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2205 total / 130 runtime-unbound / 0 unclassified |

Los events, tool receipts y context receipt del PI runner pasan a
`server_effects.write_text_atomic` bajo `workspace/.gabo/integrations/pi/receipts`.
El helper liga el target a esa raíz y al execution id, y bloquea escape o
componentes simbólicos antes del dispatch. El spawn del sidecar en
`AgentRunner` sigue abierto: el proceso genérico no admite stdin ni cancelación
del stream requerido por este protocolo. Strict runtime continúa OPEN.
La verificación final por separado pasó; una combinación anterior había
terminado con error por una ruta inexistente de compilación añadida por
equivocación después de compilar e inventariar.

## 2026-09-25 — WAL de PI bajo append durable de `state.write`

| Medida | Resultado |
| --- | ---: |
| Cambio neto (14:19:53–14:21:47 UTC; pruebas excluidas) | 1m54s |
| Suite de integraciones PI | 238 passed, 1 skipped en 14.93s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2203 total / 128 runtime-unbound / 0 unclassified |

`WALStore` ya no crea directorios ni mantiene handles o escribe/fsynca. Cada
línea se despacha por `append_text_durable` al owner `state.write`, que conserva
el append + fsync por evento. `identity_paths.artifact_component` centraliza
los nombres PI sin colisiones por sanitización y mantiene iguales los IDs que
ya son componentes seguros. Strict runtime permanece OPEN.

## 2026-09-25 — Spawn del sidecar PI bajo el owner único de proceso

| Medida | Resultado |
| --- | ---: |
| Cambio neto (14:23:50–14:37:48 UTC, excluyendo pytest) | 13m15s |
| Suite PI | 238 passed, 1 skipped en 21.42s |
| Registro de efectos | 5 passed en 0.25s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2202 total / 126 runtime-unbound / 0 unclassified |

`AgentRunner` ya no crea ni controla procesos directamente. El sidecar fijo
`main.js` se despacha como `process.sidecar.execute` por el existente
`ProcessExecutionEffectAdapter`, bajo policy server-owned antes de cualquier
spawn. El request liga ruta y SHA-256 del sidecar, Node, cwd, timeout,
execution/session identity y entorno filtrado; el owner conserva HOME efímero,
stream JSONL, cancelación y timeout. La espera usa un único worker de
`communicate` para enviar stdin una vez y drenar ambos pipes. Los shims
arbitrarios de protocolo se ejecutan sólo en un helper explícito del arnés de
pytest; producción los rechaza. Strict runtime sigue OPEN con 126 sinks.

## 2026-09-25 — El sidecar PI tiene un owner registrado propio

| Medida | Resultado |
| --- | ---: |
| Cambio neto (14:42:10–14:46:21 UTC, excluyendo pytest paralelo) | 3m41s |
| Suite PI | 239 passed, 1 skipped en 24.67s |
| Gateway + registro | 59 passed en 4.11s |
| Inventario | 27 passed en 30.30s; strict classification PASS |
| Python compile / `git diff --check` | PASS |
| Runtime sinks restantes | 125 |

El inventario había revelado que el `Popen` estaba en una función helper fuera
del span de un adapter registrado: el call llegaba al Gateway, pero el scanner
lo mantenía `runtime_unbound`. Convertí ese módulo en
`PiSidecarProcessEffectAdapter` y lo registré para el único efecto
`process.sidecar.execute`; el adapter genérico ya no lo reclama. El sink queda
en el span concreto de su único owner. Strict runtime continúa OPEN.

## 2026-09-25 — El handler de provider buffer deja de crear una ruta vacía

| Medida | Resultado |
| --- | ---: |
| Cambio neto (14:49:48–14:51:42 UTC, excluyendo pytest) | 1m54s |
| Prueba de import aislado | 1 passed en 0.17s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2201 total / 124 runtime-unbound / 0 unclassified |

Quité la creación de `BAGO_BUFFER_DIR` al importar `handlers_provider_buffer`.
El buffer se conserva en `_BUFFER_STATE` en memoria y no existe ningún lector
ni escritor de aquella ruta; la variable sólo provocaba un mkdir lateral. El
test confirma que la importación con un directorio configurado no lo crea.
Strict runtime continúa OPEN.

## 2026-09-25 — Modelos activos de provider bajo el writer de estado

| Medida | Resultado |
| --- | ---: |
| Cambio neto (14:54:06–14:57:35 UTC, excluyendo pytest) | 3m28s |
| Prueba focal + estado legacy | 12 passed en 1.42s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2200 total / 123 runtime-unbound / 0 unclassified |

El getter `_active_models_path` deja de crear el directorio: la escritura ya
usa `atomic_json`, que delega en el owner `state.write` y crea el padre. Quité
la sanitización con pérdida de identidad; lectura y escritura aceptan sólo un
ID exacto de `PROVIDER_CATALOG`, sin colisiones entre aliases inventados. El
handler rechaza IDs externos antes de materializar. Strict runtime continúa
OPEN.

## 2026-09-25 — Selección del modelo REPL bajo el writer de estado

| Medida | Resultado |
| --- | ---: |
| Cambio neto (14:59:02–15:02:10 UTC, excluyendo pytest) | 3m08s |
| Prueba focal + estado de providers | 11 passed en 0.61s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2197 total / 120 runtime-unbound / 0 unclassified |

`repl_model_router.save_selection` conserva el schema JSON pero deja de
materializar el temporal y reemplazo: delega en `atomic_json -> state.write`,
que también crea el directorio padre. Se retiraron los tres sinks directos
del router. Strict runtime continúa OPEN.

## 2026-09-25 — El historial del REPL persiste bajo `state.write`

| Medida | Resultado |
| --- | ---: |
| Cambio neto (15:02:10–15:08:03 UTC, excluyendo pytest) | ~5m51s |
| Pruebas de history + selección/modelos | 10 passed en 0.79s; primer fixture falló por CRLF de Windows y se corrigió |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2196 total / 118 runtime-unbound / 0 unclassified |

Se extrajeron los adapters de persistencia a `repl_history.py`. `readline`
carga su archivo existente y registra un callback de salida que obtiene sus
entradas en memoria y las reemplaza mediante `state.write`. Prompt Toolkit
conserva el formato legible por `FileHistory`, pero las nuevas entradas se
añaden mediante `state.write`; ambos binds usan el root del estado y la sesión
REPL. Quité los `mkdir` de startup; el owner crea los padres. Las pruebas
verifican delegación, identidad de root/sesión y lectura de formato previo.
Strict runtime sigue OPEN con 118 sinks.

## 2026-09-25 — Neural Bus de `AgentGateway` usa el writer de estado

| Medida | Resultado |
| --- | ---: |
| Cambio neto (15:08:03–15:13:50 UTC, excluyendo pytest) | ~5m46s |
| Prueba focal | 1 passed en 0.15s; dos intentos iniciales fallaron al cargar el homónimo equivocado y registrar el módulo dinámico, corregidos |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2195 total / 117 runtime-unbound / 0 unclassified |

El `_emit_event` de `backend/.bago/agents/agent_gateway.py` mantiene su
proyección en memoria y el mismo JSONL append-only, pero materializa el evento
Neural Bus con `append_text_durable -> state.write` bajo el root local de
estado y una identidad de sesión estable del gateway. La prueba carga el
archivo de runtime por ruta absoluta para no resolver el homónimo
`backend/.bago/core/agent_gateway.py`; comprueba root, sesión, formato y
delegación. Los dos subprocess de ese módulo quedan abiertos y fuera de este
bloque. Strict runtime sigue OPEN con 117 sinks.

## 2026-09-25 — ToolLogger delega su JSONL a `state.write`

| Medida | Resultado |
| --- | ---: |
| Cambio neto (15:13:50–15:15:52 UTC, excluyendo pytest) | ~2m00s |
| `test_f4_guardrails.py` | 29 passed en 1.67s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2193 total / 115 runtime-unbound / 0 unclassified |

`SessionManager` da a `ToolLogger` su `state_dir` como root de confianza. El
logger ya no crea la ruta al construirse ni hace `open/append`; cada entrada
JSONL usa `append_text_durable -> state.write`, ligado a la sesión que la
produjo. Se conserva el append best-effort del logger y su estado in-memory.
Strict runtime sigue OPEN con 115 sinks.

## 2026-09-25 — ContextStore no materializa sesiones durante la carga

| Medida | Resultado |
| --- | ---: |
| Cambio neto (15:15:52–15:19:51 UTC, excluyendo pytest) | ~3m54s |
| Conversaciones + persistencia atómica | 8 passed en 2.12s; una primera regresión llamó `get_history`, que escribe metadatos legítimamente, y se acotó a carga pura |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2192 total / 114 runtime-unbound / 0 unclassified |

`ContextStore.__init__` deja de crear `sessions/<sid>` eagerly. Los métodos
de guardado ya usan `atomic_json`/`state.write`, que materializan sólo cuando
hay estado que persistir. Cargar un SID ausente permanece en memoria y no
genera una carpeta vacía; pedir estado conversacional puede persistir su
proyección por el writer ya existente. Strict runtime sigue OPEN con 114.

## 2026-09-25 — Los artifacts de RL usan `state.write`

| Medida | Resultado |
| --- | ---: |
| Cambio neto (~15:19:51–15:24:41 UTC, excluyendo pytest) | ~4m46s |
| Contrato RL + persistencia RL | 8 passed en 1.07s final; dos ensayos anteriores se ajustaron por un fixture que `classify_message` mapeaba a chat |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2190 total / 111 runtime-unbound / 0 unclassified |

`BCPolicy.save` reemplaza el archivo bajo el root canónico `state_root` con
`write_text_atomic -> state.write`; la ingesta desde historial añade el JSONL
con `append_text_durable -> state.write`. Quité mkdir, `Path.write_text` y
append directos. El test nuevo materializa un SQLite de fixture aislado y
verifica que el historial convertido aparece en `.bago/state` junto con el
policy guardado. Strict runtime sigue OPEN con 111 sinks.

## 2026-09-25 — La persistencia de capas usa el writer de estado

| Medida | Resultado |
| --- | ---: |
| Cambio neto estimado (15:24:41–15:27:33 UTC; bloque interrumpido) | ~2m52s |
| Pruebas focales (repetidas tras reanudar) | 2 passed en 0.21s |
| Python compile / strict classification | PASS |
| Inventario | 2188 total / 109 runtime-unbound / 0 unclassified |

`LayerStore` ya no crea su carpeta en el constructor ni abre/escribe el JSONL
directamente. Conserva el formato y delega el reemplazo en
`write_text_atomic -> state.write`. `SessionAdaptersMixin` enlaza el root al
workspace activo (`base_path`, incluido el mirror de sesión) y mantiene el
`session_id`; un ID de ruta se rechaza antes de llegar al writer. La ventana
de código quedó interrumpida por una consulta de contexto; duración excluye
la verificación focal posterior. Strict runtime sigue OPEN con 109 sinks.

## 2026-09-25 — La configuración UI del REPL usa `config.write`

| Medida | Resultado |
| --- | ---: |
| Cambio neto estimado (15:37:34–15:38:43 UTC; excluye verificación) | ~1m |
| Prueba focal | 1 passed en 0.39s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2186 total / 107 runtime-unbound / 0 unclassified |

`/ui` conserva su ruta de configuración y el mismo JSON, pero `_ui_save_config`
ya no crea el directorio ni escribe directamente. Delega en
`write_config_text_atomic -> config.write`, con root derivado de la ubicación
del paquete, superficie `chat.repl.ui-config` e identidad de sesión activa.
El inventario estricto de runtime se ejecutó y sigue OPEN con 107 sinks.

## 2026-09-25 — Bootstrap del estado runtime bajo un owner propio

| Medida | Resultado |
| --- | ---: |
| Cambio neto estimado (15:42:00–15:47:30 UTC; excluye las pruebas) | ~4m50s |
| Bootstrap + registro + ExecutionGateway | 62 passed en 3.20s |
| Python compile / JSON del registro / strict classification / `git diff --check` | PASS |
| Inventario | 2187 total / 104 runtime-unbound / 0 unclassified |

Añadí el efecto policy `state.bootstrap` y su adapter separado. `ensure_state_dir`
crea sólo `sessions`, `changes` y `evidences` mediante el gateway; la siembra
desde `.bago/state.example` conserva la condición de no sobrescribir el estado
ya inicializado. El owner comprueba el root canónico, su identidad y los paths
antes de materializar. Strict runtime sigue OPEN con 104 sinks.

## 2026-09-25 — `ConfigManager` difiere crear el root de configuración

| Medida | Resultado |
| --- | ---: |
| Cambio neto estimado (15:48:35–15:50:49 UTC; excluye pruebas y gates) | ~1m40s |
| Prueba focal | 1 passed en 0.23s; el fixture inicial usaba root explícito y se ajustó para cubrir lectura legacy |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2187 total / 103 runtime-unbound / 0 unclassified |

El constructor deja de crear un directorio de estado vacío al cargar una
configuración legacy. Cuando se persiste un cambio, `_save` conserva el writer
atómico existente (`state.write`), que crea el directorio bajo su owner. Strict
runtime sigue OPEN con 103 sinks.

## 2026-09-25 — Corrección de `Path.open` y auditoría reflexiva bajo `state.write`

| Medida | Resultado |
| --- | ---: |
| Duración activa de edición | No quedó cronometrada de forma fiable; se omite para no inventar un tiempo |
| Inventario corregido | 2220 total / 106 runtime-unbound / 0 unclassified |
| Scanner | 28 passed; strict classification PASS, strict runtime OPEN (exit 2) |
| Ledger reflexivo | 2 pruebas focales passed; Python compile PASS |

El scanner ahora interpreta correctamente el argumento de modo en
`Path.open(mode)` ligado, además de las formas `open(path, mode)` y
`Path.open(path, mode)` no ligadas. El inventario previo subcontaba escrituras.
`ReflexiveAuditLedger` elimina el `mkdir` eager y enruta el append JSONL por
`append_text_durable -> state.write`, ligado al root y a la sesión. El gate
global permanece abierto con 106 sinks; el conteo no incluye sinks ya movidos
a owner.

## 2026-09-25 — El probe de Codex ya no lanza un proceso

| Medida | Resultado |
| --- | ---: |
| Tiempo de cambio | 12s (16:03:57–16:04:09 UTC); pruebas y gates excluidos |
| Prueba focal | 2 passed en 0.17s |
| Python compile / strict classification / `git diff --check` | PASS |
| Inventario | 2219 total / 105 runtime-unbound / 0 unclassified |

`CodexAdapter.health()` solo necesita determinar si existe el ejecutable, por
lo que ahora usa `shutil.which("codex")` y no ejecuta `codex --version`. El
probe dejó de ser un sink de proceso. El despacho general de comandos locales
`_run_bago` conserva una responsabilidad de ejecución más amplia y queda como
tramo separado. Strict runtime sigue OPEN con 105 sinks.
## 2026-09-25 — El inventario SQLite separa PRAGMA local de conexión

| Medida | Resultado |
| --- | ---: |
| Edición del detector | 10s (16:30:24–16:30:34 UTC); ajustar expectativa del test sin cronómetro fiable |
| Suite focal del inventario | 30 passed en 25.74s |
| Python compile / strict classification | PASS |
| Inventario actual | 2342 total / 134 runtime-unbound / 0 unclassified |
| Candidatos database.write | 122; SQL dinámico de confianza baja sigue en revisión |
| Strict runtime | OPEN con 134 sinks |

El scanner deja de llamar `database.write` a `PRAGMA busy_timeout` y
`PRAGMA synchronous`, que solo configuran la conexión. Conserva `journal_mode`
y las mutaciones SQL como candidatos persistentes. La revisión confirmó que
KnowledgeBase, EmbeddingStore y SessionDB aún tienen escrituras directas, y
que `/memory/embeddings/upsert` permite que el body suministre `source_session`;
ese dato aún no queda ligado al SessionManager. No se añadió ni se reclama un
owner SQLite: queda pendiente resolver autoridad y conservar identidad de
sesión/workspace antes de migrar.

## 2026-09-25 — El upsert de embeddings liga origen a la sesión activa

| Medida | Resultado |
| --- | ---: |
| Edición fuente | 17s (16:34:26–16:34:43 UTC); la edición adicional de test no quedó cronometrada |
| Pruebas de contrato memory/embeddings | 9 passed en 0.60s |
| Compile / `git diff --check` | PASS |
| Runtime sinks eliminados | 0; la autorización database.write sigue pendiente |

`POST /memory/embeddings/upsert` ya no acepta `source_session` del body: lo
resuelve desde el `SessionManager` activo. Si no existe sesión, responde 409
antes de abrir o materializar las bases SQLite. La prueba cubre el intento de
atribución falsificada y el rechazo sin sesión/pre-efecto. El cambio corrige la
identidad de esa ruta; no cierra la autoridad de persistencia ni las otras
entradas que escriben KnowledgeBase, EmbeddingStore o SessionDB.

## 2026-09-25 — Subconjunto runtime de sinks SQLite identificado

El inventario `--json` separa 122 candidatos `database.write` globales de 31
runtime-authority/unbound: `knowledge_base.py` 12, `embedding_store.py` 10,
`session_db.py` 8 y `rl_policies.py` 1. Hay llamadas `sqlite3.connect` que
requieren decidir por callsite si son materialización o apertura de una DB ya
existente; no se presumen escrituras confirmadas. El siguiente corte debe
resolver first la autoridad de KnowledgeBase/embeddings y clasificar
SessionDB como índice derivado o persistencia canónica con un owner propio.
Strict runtime global continúa OPEN con 134 sinks.

## 2026-09-25 — La lectura del historial SQLite queda explícitamente read-only

| Medida | Resultado |
| --- | ---: |
| Pruebas focales inventario + RL | 37 passed en 25.65s |
| Inventario | 2342 total / 133 runtime-unbound / 0 unclassified |
| Candidatos `database.write` | 121 globales; 30 runtime-unbound |
| Strict classification / strict runtime | PASS / OPEN |
| Tiempo de edición | No se midió de forma fiable; no se atribuye duración de pruebas al cambio |

La auditoría por callsite confirmó que `rl_policies` solo lee la base existente
de historial Copilot. La conexión ahora usa URI SQLite `mode=ro`, que impide
crear o mutar ese archivo y elimina esa finding de escritura runtime. El
scanner reconoce explícitamente este modo read-only y sigue separando las
aperturas de las mutaciones persistentes. El sink global sigue abierto con 133
hallazgos runtime, incluidas KnowledgeBase, EmbeddingStore y SessionDB; el
owner `database.write` y Node Control aún no están cerrados.
