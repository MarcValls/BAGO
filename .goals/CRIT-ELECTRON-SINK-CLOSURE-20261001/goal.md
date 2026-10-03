# P1 — Plan BAGO: cierre de sinks Electron

## [1] Objetivo
**Contenido:** Resolver mediante el owner correcto los dos sinks directos de `backend/electron/runtime-service.cjs` (spawn inicial del webchat y kill del fallback), generar un commit aislado sin perder los cambios ajenos actuales, ejecutar toda la suite backend y obtener revisión independiente final.
**Aceptacion:** El inventario fresco cubre ambos sinks y no deja ninguno runtime-unbound sin una clasificación probada; el commit candidato queda limpio; la suite backend completa se ejecuta sobre el candidato y no introduce fallos respecto a su baseline comparable; `/skill:bago-final-verifier` pasa para el cambio Electron. Los 47 fallos baseline conocidos mantienen bloqueado cualquier claim de suite global verde/cierre global.
**Siguiente accion:** Abrir un candidate workspace limpio en el HEAD fijado abajo y ejecutar primero el inventario read-only.

## [2] Origen
**Contenido:** Tarea derivada de la auditoría `code-map` y del handoff BAGO sobre los dos sinks de ciclo de vida Electron. Referencia de diseño por capas: `LAYERED_ARTIFACT_ENGINE_IMPLEMENTATION_v0.1.zip`, SHA-256 `f7d27f52d7c274ccd2dc0e87a5ddd679865aebe52f1cd8c707b03fe4279cfc31`; se verificaron 29/29 entradas de su `SHA256SUMS`. Su contrato congelado LAE v0.9-FIX8 tiene SHA-256 `d15ecd534f6f6ee34daff78107886c6d695b84d4790c04fbb4a0c35c2bf6c65e`.
**Aceptacion:** La referencia queda identificada y verificada; el ZIP y su directorio `frozen/` permanecen externos e inmutables. LAE v0.1 es una implementación de referencia in-memory, no un adapter runtime BAGO; el trabajo aplicará el protocolo de capas en soft mode conforme a `.agents/skills/bago-core/references/LAYER_PROTOCOL.md`.
**Siguiente accion:** Usar la referencia solo para parent exacto, delta inmutable, stale-parent rejection, verificación de delta y vista efectiva; no importar ni declarar integrada la librería LAE.

## [3] Entradas
**Contenido:**
- Código: `backend/electron/runtime-service.cjs`; inventario oficial y configuración del scanner; `backend/.bago/core/execution_gateway.py`, `execution_adapters/process.py` y `execution_adapters/pi_sidecar.py`; tests Electron/Gateway relevantes.
- Autoridad: `backend/.bago/contracts/bago.effect-registry.v1.json`, `AGENTS.md`, `.bago/state/PROJECT_STATE.json` y `.bago/runtime/ACTIVE_HANDOFF.md`.
- Parent de referencia observado: branch `fix/spbe-runtime-fix1-20260927`, HEAD `b10178bf8a13d0035079e989e46c36760dbd2a46`; worktree actual dirty, fingerprint `09568030cc7f863b10b960b16f3ca0bf07352fd14a5c1fb5e8c375c064a70fb9` (14.749 entradas porcelain al capturarlo). Este fingerprint es del checkout de planificación, no de un candidato verificado.
- Cambios locales ajenos: modificaciones de bootstrap/MSIX, API/backend y tests; artefactos y goals no trackeados. Deben preservarse, no borrarse ni incorporarse por accidente.
- Evidencia preexistente, solo como contexto: `.goals/backend-audit-remediation-b10178bf/status.json` registra P3 focal independiente PASS (234 tests, 158 subtests), y suite completa terminada con 1773 passed, 47 failed, 3 skipped y 214 subtests; los 47 IDs finales reproducen en baseline unchanged-HEAD. Su review P3 cubre cinco criterios backend, no verifica cambios futuros de Electron.
**Aceptacion:** Antes de escanear se vuelve a fijar HEAD, estado porcelain, rutas cambiadas, fingerprint, identidad/configuración del scanner y versión del effect registry en el workspace candidato exacto.
**Siguiente accion:** Crear el workspace candidato limpio desde el commit fijado y confirmar su parent antes de ejecutar el scanner.

## [4] Dependencias
**Contenido:** `git worktree`, Git, Python/pytest, scanner oficial de sinks, `read`/`bash`/`edit` de Pi y el skill `/skill:bago-final-verifier`. Las mutaciones y permisos se limitan al workspace candidato nuevo; el checkout sucio original queda preservado. No se requiere modificar el paquete LAE ni instalarlo.
**Aceptacion:** Workspace candidato aislado, scanner identificable, tests disponibles y autorización local de commit; si falla una dependencia, buscar una vía alternativa sin saltar evidencia.
**Siguiente accion:** Crear el workspace desde el HEAD fijado y registrar la identidad efectiva resultante; si el commit base o su alcance difiere, replanificar antes de editar.

## [5] Ejecucion
**Contenido:** Candidate layers secuenciales, soft mode LAE. El contrato congelado externo no se edita y las capas no se activan antes de sus gates.

### CL-01 — Inventario y partición read-only
- **parent_effective:** commit `b10178bf8a13d0035079e989e46c36760dbd2a46` en workspace limpio; identidad/fingerprint reproducidos al crear el worktree. No reutilizar el fingerprint del checkout sucio para este candidato.
- **scope:** solo lectura.
- **paths/targets:** `backend/electron/runtime-service.cjs`, scanner oficial/configuración, registry v`1.24.0` o la versión leída del checkout limpio.
- **pasos:** congelar branch/HEAD/status/changed paths/fingerprint y scanner+config+registry; ejecutar inventario y gates oficiales sobre ese snapshot; trazar cada sink desde caller a spawn/kill y recurso afectado; comprobar scanner coverage de ambas formas.
- **gate:** cobertura reproducible; findings exactos; sin P0, scanner gap ni inconsistencia. Si aparece alguno, parar y documentar sin reparar.

### CL-02 — Clasificación y owner propuesto
- **parent_effective:** resultado de CL-01 sin cambios al snapshot.
- **scope:** análisis read-only y decisión candidata.
- **paths/targets:** dos callsites concretos de `runtime-service.cjs`, adapters/handlers existentes y contratos necesarios.
- **pasos:** asignar exactamente una clase primaria por sink (`REUSE`, `EXTEND`, `NEW_OWNER`, `DELETE`, `RECLASSIFY` o `BLOCKED`), siguiendo el orden REUSE→EXTEND→NEW_OWNER. Probar reachability antes de DELETE y ownership exclusivo antes de RECLASSIFY. No aceptar `authority_internal` por documentación solamente: el sink debe seguir visible al scanner como `gateway_owned` si existe un efecto material gobernado. Para cada sink registrar owner, llamada material, identidad/sesión/recurso, fingerprint/TOCTOU, retry/replay/delegación/nested execution y gate de prueba.
- **gate:** cada sink pertenece a una clase y un cluster; owner y corrección están justificados; si no se puede probar owner correcto, BLOCKED y detener.

### CL-03 — Implementación en candidate layer
- **parent_effective:** snapshot limpio de CL-01 más el delta aceptado de CL-02; recalcular y registrar fingerprint antes de materializar. Si el parent cambia, rechazar/rebasar como nueva capa.
- **scope:** cambios mínimos a `backend/electron/runtime-service.cjs`, cliente/adapter de proceso y tests; contract/registry solo si CL-02 demuestra que es necesario.
- **pasos:** reusar primero owners existentes; si el backend no puede gobernar bootstrap pre-listener, diseñar un owner bootstrap separado únicamente tras justificar `NEW_OWNER`; no convertir un bypass material en `authority_internal`. Añadir tests que cubran spawn, fallo de arranque, cancelación, ownership PID y no terminación de procesos ajenos.
- **gate:** delta inspeccionado; tests focales pasan; inventario mantiene ambos sinks visibles y bound al owner correcto; `git diff --check` pasa.

### CL-04 — Vista resuelta, limpieza de candidato y commit
- **parent_effective:** candidato CL-03 con digest/fingerprint capturado; no usar parent histórico.
- **scope:** verificación, commit aislado y limpieza únicamente dentro del candidate workspace.
- **paths/targets:** rutas de CL-03 y todos los paths del worktree candidato.
- **pasos:** verificar delta y vista efectiva resuelta; confirmar que no hay artefactos ajenos; conservar el checkout sucio original intacto; ejecutar gates antes del commit; hacer commit solo de paths aprobados; confirmar HEAD y worktree limpio después del commit.
- **gate:** commit SHA y fingerprint registrados, sin staged/untracked/residual dirtiness en candidate workspace; ningún cambio del checkout original se perdió o incluyó.

### CL-05 — Suite backend y revisión independiente
- **parent_effective:** commit SHA de CL-04.
- **scope:** solo lectura, tests y revisión.
- **paths/targets:** commit entero; backend/tests y diff de CL-03.
- **pasos:** ejecutar `python -m pytest -q backend/tests` con basetemp local; ejecutar inventario/gates sobre el mismo SHA; invocar `/skill:bago-final-verifier`; vincular receipts/salidas al SHA exacto.
- **gate:** suite backend completa ejecutada sin timeout sobre el mismo candidato; comparar IDs exactos contra un baseline de parent equivalente. Aceptar solo cero fallos nuevos; registrar explícitamente los 47 baseline conocidos si siguen presentes (1773/47/3/214 es evidencia anterior, no resultado de este candidato). No describir la suite como PASS/global-green mientras persistan. Strict-classification PASS; sinks objetivo cerrados o decisión BLOCKED explícita; `git diff --check` PASS; verifier independiente PASS sobre el cambio Electron. Strict-runtime global puede seguir abierto y no se presenta como cerrado.

**Aceptacion:** Todas las capas preservan parent/delta/historial, ningún parent stale se activa, y la verificación cubre tanto el delta como la vista resuelta.
**Siguiente accion:** Ejecutar CL-01 en el candidate workspace recién fijado.

## [6] Programacion
**Contenido:** Ejecución manual, secuencial CL-01→CL-05. No recurrente ni programada. Las capas son soft-mode procedurales: la implementación LAE del ZIP no está integrada con persistencia/autorización BAGO. Interrupción o cambio del parent exige rehidratar y registrar una nueva identidad, no reutilizar receipts.
**Aceptacion:** Cada transición se registra; ninguna capa se activa antes de pasar su gate.
**Siguiente accion:** Crear el workspace candidato aislado; no alterar el checkout sucio existente.

## [7] Revision
**Contenido:** Verificador independiente `/skill:bago-final-verifier` revisa diff, ownership, pruebas, inventario y claims sobre el mismo SHA. El autor no se certifica a sí mismo. La revisión P3 ya archivada en `.goals/backend-audit-remediation-b10178bf/p3-scoped-review.md` cubre cinco criterios backend y no sustituye la revisión del cambio Electron. La decisión de clasificación demuestra caller→owner→material effect; la evidencia LAE solo respalda el método de capas, no integración runtime BAGO.
**Aceptacion:** Reviewer PASS candidate-bound; suite completa e inventario ligados al mismo commit; no hay afirmación de integración LAE, cierre global de strict-runtime, ni estado VERIFIED/VALIDATED sin evidencia vigente.
**Siguiente accion:** Solicitar la revisión independiente tras finalizar CL-05 y registrar su resultado en el goal.

## Quality Gates
- Parent efectivo exacto capturado para cada capa; rechazo/rebase al detectar drift.
- Scanner coverage e inventario reproducible en el snapshot fijado; strict-classification PASS.
- Los dos sinks quedan vinculados al owner correcto; no se ocultan con exclusiones ni etiquetas sin prueba.
- Tests focales y suite backend completa ejecutados sobre el candidato; cero regresiones nuevas respecto al baseline comparable. Los 47 fallos reproducidos siguen registrados y bloquean cierre global; no declarar suite completa PASS. `git diff --check` PASS.
- Workspace candidato committed y limpio; `/skill:bago-final-verifier` PASS sobre el mismo SHA.

## Riesgos
- El ZIP LAE es referencia in-memory, no integración productiva de BAGO → usar únicamente el protocolo soft de `.agents/skills/bago-core/references/LAYER_PROTOCOL.md`; no declarar LAE activado.
- El spawn ocurre antes de que exista el backend que ofrecería el Gateway → analizar primero REUSE/EXTEND y justificar NEW_OWNER antes de codificar; no reclasificar sin prueba de exclusividad.
- El checkout original tiene numerosos cambios/artefactos ajenos → usar worktree aislado y no borrar ni stagear el checkout original.
- El gate global strict-runtime contiene findings fuera de scope → reportar solo el cierre de `runtime-service.cjs`; mantener el gate global OPEN.
