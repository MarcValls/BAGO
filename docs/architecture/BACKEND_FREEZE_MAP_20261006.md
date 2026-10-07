# Mapa inicial para congelar el backend — 2026-10-06

## Propósito y estado

Este documento inicia el mapa del backend que debe permanecer estable mientras
se diseña y construye una UI nueva. No congela código ni eleva el estado global
del repositorio. Distingue contratos que la UI puede consumir de áreas cuyo
estado todavía requiere evidencia candidata.

- Estado del mapa: `PREPARED`.
- Estado global observado: `EXECUTED`.
- Candidato observado al crear el mapa: rama
  `publish/worktree-groups-20261003-7f5d47a6`, HEAD
  `aec40891271310281a165214ed0fb5da4733c029`, worktree sucio.
- El inventario reproducido quedó añadido al índice Git en
  `docs/architecture/evidence/backend-effect-sink-inventory-20261006.json`;
  SHA-256 `5d57d90184efb9a04d0b1e5452c02834596cb0f013fcce6f6665248339eecf2b`.
- El manifiesto de entradas
  `docs/architecture/evidence/backend-effect-sink-input-manifest-20261006.json`
  registra los 2.945 ficheros que el iterador del scanner entrega al análisis,
  incluidos los inputs untracked/ignored; digest ordenado
  `366f6e24709dd78e7f1db23f5368b62ece5eb42b5e1ee5b29a1391b040a8b965`.
- Los recibos focales del 5 de octubre UTC están ligados al mismo candidato
  sucio; el fingerprint final se conserva en los recibos citados abajo y debe
  regenerarse si cambia el contenido versionado.
- La batería completa del backend no se ejecutó en este paso; el gate histórico
  del 2 de octubre que terminó con 47 fallos pertenece a otro candidato.
- Ninguna fila queda declarada `VALIDATED` por este mapa.

## Criterio para considerar una superficie congelable

Una superficie podrá proponerse como `FROZEN_FOR_UI` sólo cuando tenga:

1. contrato y owner identificados;
2. rutas/operaciones y esquemas de entrada/salida trazados hasta su handler;
3. pruebas de contrato y de límites que correspondan al uso de la UI;
4. recibos `VERIFIED` enlazados al mismo candidato o una prueba explícita de
   aplicabilidad de la evidencia al código actual;
5. errores, permisos, identidad de sesión y mutaciones documentados;
6. una regla de compatibilidad para cambios futuros.

`FROZEN_FOR_UI` significa que la UI consume el contrato sin cambiar su
semántica. No equivale a inmutabilidad global, seguridad completa ni
`VALIDATED` del producto.

## Mapa por superficie

| Dominio backend | Owner/contrato localizado | Uso previsto desde UI nueva | Evidencia observada | Estado para congelar |
|---|---|---|---|---|
| API local y dispatch | `backend/.bago/api/bridge.py`, `backend/.bago/api/api_dispatch.py`, contratos de rutas | Transporte y catálogo de operaciones | La batería focal actual incluye route meta, response contract, handler support, Origin y security | `PARTIAL / CURRENT_CANDIDATE` |
| Sesión y conversación | `SessionManager`, `session_persistence_mixin.py`, handlers de chat | Crear/seleccionar sesión, historial, enviar turno, consultar estado | Recibo focal actual: binding de turnos, idempotencia, persistencia atómica y recovery; pruebas incluidas en 292 PASS | `PARTIAL / CURRENT_CANDIDATE` |
| Autorización | `AuthorizationBoundary`, contratos de procedencia de autorización | Desafíos, decisiones, permisos y errores de autorización | Recibo focal actual cubre Gateway, security, Origin mutante y route contracts; no es revisión independiente | `PARTIAL / CURRENT_CANDIDATE` |
| Ejecución de efectos | `ExecutionGateway v2`, `EffectAdapterRegistry`, adapters | Ejecutar operaciones mutables con permisos y resultados tipados | Inventario/clasificación actual pasa; 538 runtime-unbound mantienen `strict-runtime` abierto | `OPEN / CURRENT_CANDIDATE` |
| Estado de mundo y precondiciones | `world_state_snapshot.py`, inventario de snapshots | Presentar estado, detectar datos obsoletos antes de operar | Pruebas del snapshot incluidas en recibo focal actual; no equivale a gate global | `PARTIAL / CURRENT_CANDIDATE` |
| Proveedores y modelos | `provider_catalog.py`, `provider_adapter.py`, `model_equivalence.py` | Configurar y seleccionar provider/modelo, health y capacidades | Endpoint, registro, contratos cloud, Ollama y descargas incluidas en recibo focal actual | `PARTIAL / CURRENT_CANDIDATE` |
| Planes y pipeline gobernado | `plan_engine.py`, `governed_work_pipeline.py` | Revisar planes, pasos, progreso, revalidación y recibos | Incluye verificación de recibos y snapshot, pero 04-FIX2 mantiene review abierta y falta verificación independiente | `PARTIAL / OPEN_REVIEW` |
| Evidencia y claims | `claim_evidence.py`, `evidence_model.py`, contrato v4 de evidencia | Mostrar procedencia, ejecución, checks y limitaciones | Contratos presentes; inventariar productores/consumidores y fijar qué recibos puede representar la UI | `OPEN` |
| Workspace y archivos | `workspace_binding.py`, adapters filesystem/workspace, handlers | Mostrar contexto del proyecto y proponer/aplicar cambios | Hay controles en Gateway; falta una matriz de operaciones de UI y evidencia actual para cada ruta | `OPEN` |
| Procesos, instalación y lifecycle | adapters de proceso/instalación/lifecycle | Acciones administrativas con confirmación explícita | Handoff mantiene P0 bootstrap abierto; fuera de la primera capa de UI congelada | `EXCLUDED_FROM_INITIAL_FREEZE` |
| Persistencia cognitiva, aprendizaje y memoria | `context_store.py`, `knowledge_base.py`, `learning_writer.py`, `rl_engine.py` | Consultar/gestionar memoria y aprendizaje | Autoridad, retención y mutaciones requieren auditoría propia; no exponer como CRUD genérico | `OPEN / HIGH_SENSITIVITY` |

## Evidencia disponible y límites

- El recibo actual `.bago/evidence/remediation-gates/backend-boundary-map-focal-20261006.json`
  registra **292 passed y 158 subtests**, exit 0, y candidate stable `true`.
  El recibo de clasificación
  `backend-boundary-map-classification-20261006.json` también pasa con
  candidate stable `true`; ambos declaran el mismo HEAD, branch y fingerprint.
- El gate actual `backend-boundary-map-runtime-20261006.json` termina con
  exit 2: confirma que `strict-runtime` no cierra mientras existan runtime
  sinks sin binding. Conteo observado: 538 runtime-unbound.
- Antes de regenerar el reporte AST, la batería focal falló sólo en
  `test_migration_inventory_is_current_and_machine_checkable` (291 passed).
  El generador canónico refrescó la proyección a 78 archivos/121 mutaciones;
  `--check` pasó y la batería final pasó.
- `.goals/backend-audit-remediation-b10178bf/status.json` registra una review
  independiente focal: 234 pruebas y 158 subtests pasaron para cinco criterios
  (endpoint/credenciales, binding de conversación, Origin mutante, timeout con
  retry por ID y protección de corrupción JSONL). La evidencia está ligada al
  candidato `b10178bf…`, no al HEAD observado hoy.
- El gate backend completo registrado en ese mismo candidato terminó con 47
  fallos, 1773 pases, 3 skips y 214 subtests; el informe explica que esos 47
  IDs también fallaban en la baseline limpia. Esto permite conservar la
  conclusión focal, pero no afirmar backend completo `VERIFIED` o `VALIDATED`.
- `.bago/state/PROJECT_STATE.json` identifica el recibo protegido previo como
  superado y establece que no hay recibo activo asociado al candidato actual.
- `.bago/runtime/ACTIVE_HANDOFF.md` declara explícitamente que el cierre global
  y el bootstrap P0 siguen abiertos; sus verificaciones de componentes están
  ligadas a candidatos sucios anteriores.
- El worktree global sigue sucio y contiene otros artefactos no rastreados. La
  evidencia actual es candidate-bound al fingerprint citado. Las entradas
  efectivas del scanner quedan además ligadas por el manifiesto de paths y
  hashes, de modo que untracked/ignored analizados no dependen de que el hash
  Git los incluya. Cualquier cambio de entrada invalida el manifiesto.
- `strict-classification` no mide cobertura total del scanner y no significa
  que todos los sinks estén gobernados. `strict-runtime` está abierto. No se
  afirma cierre completo ni `VALIDATED` del backend.

## Primera frontera sugerida para la UI nueva

La primera rebanada debería limitarse a consultas de solo lectura de sesión,
estado de conversación, catálogo de capacidades/proveedores y estado de
workspace, siempre consumiendo rutas y contratos existentes. Acciones mutables
deben permanecer detrás de `AuthorizationBoundary` y `ExecutionGateway`; la UI
no debe emitir permisos ni tratar un resultado de modelo como autorización.

Antes de congelar esa rebanada, producir un catálogo máquina-legible de rutas
con método, esquema, owner, efecto, modo de autorización, errores, identidad
requerida, pruebas y recibo candidato. Después ejecutar y registrar los gates
focales sobre un candidato fijado, resolver fallos aplicables, y obtener review
independiente. Hasta entonces, este mapa sólo sirve para planificar el límite
de integración de la nueva UI.
