# Decisions

Record architectural or product decisions that affect canon here.

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
- Alcance: `filesystem_effects.py` y clases concretas `*EffectAdapter` del
  gateway; el ledger de autorización continúa siendo `authority_internal`.
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
