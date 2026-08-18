# BagoPiBridge — CHANGELOG

## v0.1 (DRAFT/QUARANTINE) — Cierre 2026-07-15

### Alcance
Fases 0-3 cerradas: contención, provider adapter, tool proxy read-only, agent runner. Fase 4 (mutaciones) bloqueada por canon.

### Tests
- 218 tests verdes + 1 skipped.
- 24 NEG del PLAN §8 cubiertas.
- 0 regresiones en suite BAGO pre-existente.

### Decisiones arquitectónicas
- `ToolReceipt` promovido a canónico en `backend/.bago/core/tool_receipt.py` durante Sprint 4 (decisión ARQ-IMPLEMENTATION, sin consulta explícita a CRIT).
- `ContextReceipt` reusado, no duplicado.
- Sidecar Node/TS mock local autocontenido (5 archivos JS, 0 deps runtime).
- Persistencia atómica con `fsync` por evento.

### Estado
- `enabled: false, max_phase: 0` por defecto.
- HOLD OPERATIVO: NO se promueve a `enabled=true` en producción hasta resolver B1.

### Dictamen CRIT
GO CONDICIONADO con HOLD OPERATIVO. B1 (herencia formal) y A1-A4 marcadas como acciones de v0.2.

---

## v0.2 — Cierre 2026-07-15

### Acciones tomadas

#### B1 (BLOQUEANTE PRE-PRODUCCIÓN) ✅ RESUELTO
**Problema:** `BagoPiProviderAdapter` no era reconocido por `isinstance(adapter, ProviderAdapter)` en el router BAGO, porque no heredaba formalmente del canónico.

**Solución:** la clase se registra como **subclase virtual** del canónico `ProviderAdapter` mediante `ProviderAdapter.register(BagoPiProviderAdapter)`. Esto:
- No requiere herencia formal (que exigiría adaptar las firmas de `chat` para coincidir exactamente con el canónico).
- Permite que el router BAGO use `isinstance(adapter, ProviderAdapter)` para discovery.
- Preserva la API dict-returning del bridge (Fase 1+).

**Implementación:** el módulo canónico se carga bajo el nombre `provider_adapter` en `sys.modules`, lo que permite que `from provider_adapter import ProviderAdapter` retorne la misma clase que el bridge registra.

**Tests:**
- `test_B1_adapter_is_instance_of_canonical_provider_adapter`: verifica que `isinstance(adapter, canonical)` es `True`.
- `test_B1_provider_adapter_module_registered_in_sys_modules`: verifica el registro en `sys.modules`.
- `test_B1_adapter_method_signatures_compatible`: verifica que los 6 métodos del contrato están presentes.

**Consecuencia:** el router BAGO ya puede descubrir el adapter. El HOLD OPERATIVO se levanta pendiente de ARQ-IMPLEMENTATION v0.2.1 (ver §"Estado post-v0.2").

#### A1 (anotación sobre `verification_state`) ✅ APLICADO
**Problema:** el campo `verification_state` del `ContextReceipt` podría confundirse con una certificación final; la promoción a `done`/`verified`/`certified` es exclusiva del validador BAGO.

**Solución:** anotación explícita en `backend/.bago/integrations/pi/receipt_factory.py` que documenta:
- `verification_state` es **propuesta del bridge, no certificación final**.
- El bridge nunca escribe `done`/`verified`/`certified`.
- La promoción a esos estados es **exclusiva del validador BAGO**.
- El campo viaja como metadato informativo; el validador puede sobrescribirlo o ignorarlo.

**Test:** `test_A1_receipt_factory_documents_verification_state_authority` verifica la presencia de la anotación.

#### A2 (write-ahead log) ✅ APLICADO
**Problema:** si el bridge crashea tras validar un evento pero antes de persistirlo, el evento está en memoria pero no en disco. La invariante "si el bridge afirma EXECUTED_UNVERIFIED, los eventos están en disco" no se cumplía estrictamente para eventos intermedios.

**Solución:** nuevo módulo `backend/.bago/integrations/pi/wal.py` que implementa un WAL append-only con `fsync` por escritura. El `AgentRunner` ahora:
- Inicializa el WAL al entrar a estado `Capturing`.
- Hace `wal.append(execution_id, event.to_dict())` **antes** de `log.append(event)`. Si el WAL falla, la ejecución pasa a `REJECTED` con `BRIDGE_PERSISTENCE_FAILED`.
- Cierra el WAL al final del run (éxito o rechazo).

**Path:** `project_root/.gabo/integrations/pi/wal/<execution_id>.jsonl`.

**Tests:**
- `test_A2_wal_persists_events_for_successful_run`: verifica que el WAL contiene todos los eventos del run exitoso.
- `test_A2_wal_is_closed_after_run`: verifica que `runner._wal is None` tras el run.
- `test_A2_wal_module_basic_operations`: smoke test del módulo WAL.
- `test_A2_wal_rejects_unknown_execution_id_safely`: el WAL no falla con execution_id desconocido.

**Trade-off:** costo de `fsync` por evento (mismo que v0.1). En producción con miles de eventos, considerar agrupar fsync en v0.3+.

#### A3 (rango `engines` del sidecar) ✅ APLICADO
**Problema:** el `package.json` del sidecar declaraba `"node": ">=20.0.0 <23.0.0"` pero el runner tiene Node 24. El sidecar funciona porque no usa APIs nuevas, pero el contrato `engines` no se cumple estrictamente.

**Solución:** el rango se relajó a `"node": ">=20.0.0"`. El sidecar sigue funcionando en cualquier Node 20+; las APIs mínimas que usa (fs, path, crypto, child_process via subprocess) están disponibles en todas las versiones LTS.

**Test:** `test_A3_sidecar_engines_declare_node_20_or_higher` verifica el rango.

#### A4 (changelog) ✅ ESTE DOCUMENTO

### Tests
- 228 tests verdes + 1 skipped.
- 10 nuevos tests en `test_v02_changes.py`.
- 0 regresiones en suite BAGO pre-existente.

### Estado post-v0.2

#### HOLD OPERATIVO LEVANTADO PARCIALMENTE
- ✅ B1 resuelto: el router BAGO ya puede descubrir el adapter.
- ✅ A1-A4 aplicados.
- 🟡 El bridge sigue con `enabled: false, max_phase: 0` por defecto. La promoción a `enabled=true` en producción requiere:
  - Smoke test en staging con el adapter registrado en el router real.
  - Canary con workspaces explícitos.
  - Aprobación explícita de ARQ-IMPLEMENTATION v0.2.1.

#### Pendiente para v0.2.1 (canary)
1. Smoke test con `BagoPiProviderAdapter` registrado en `bridge.py` real.
2. Canary con un workspace de prueba (`BAGO_PI_BRIDGE_ENABLED=true` + `BAGO_PI_MAX_PHASE=3` + `integrations.pi.enabled: true`).
3. Monitoreo de receipts y WAL durante 1 semana.
4. Promoción o rollback.

#### Pendiente para Fase 4
- Independiente. Requiere ciclo ARQ+CRIT+PLAN siguiendo el canon del PLAN v0.1 §13.
- Los 8 riesgos abiertos del PLAN §15 siguen abiertos.
- El sandbox por OS, MutationReceipt canónico, protocolo de approvals, modelo formal de mutaciones: trabajo nuevo, no parte de v0.2.

### Compatibilidad
- ✅ Sidecar Node 24: ahora dentro del rango `engines`.
- ✅ Node 20-22: sigue soportado.
- ✅ Bridge sigue sin instanciar el SDK real de PI.
- ✅ Cuarentena preservada: `enabled: false, max_phase: 0` por defecto en `backend/.bago/config.json`.

---

## v0.2.1 — 2026-07-15

### Alcance
Optimizaciones derivadas de la sesión de debugging de la UI de BAGO 4.8 (workspace seed que colgaba). NO se introducen cambios funcionales en el bridge BagoPiBridge.

### Acciones

#### R1.1 — Caché de `status()` en `handlers_project.py` ✅
**Problema:** el handler de `/project/seed`, `/project/link`, `/project/sync` llamaba a `ctx.session_mgr.status()` **4 veces por request**. `status()` es caro (6+ segundos en proyectos grandes) porque invoca `measure_context()`.

**Solución:** dict-local `state_cache` en el handler que cachea el primer `status()`. Las siguientes 3 llamadas son O(1).

**Impacto medido:** `POST /project/seed` pasa de ~20s a ~7.8s en el workspace `gestor-de-deudas-con` (con 523 MB de `node_modules`).

**Limitación:** el primer `status()` sigue tardando 6s. Para reducirlo más habría que cachear `measure_context()` en el `SessionManager` con TTL, lo cual es invasivo contra el canon.

#### R2 — Timeout en fetch redirigido ✅
**Problema:** el `runCommand` del frontend tiene un redirigido para `/auto-config *` y `/blacklist` que hace `fetch` directo sin timeout. Si el backend cuelga, la UI se queda esperando.

**Solución:** `AbortController` con timeout 60s en `ControlPlane.tsx::runCommand`. Si el fetch excede 60s, se aborta y se reporta error.

**Limitación:** solo aplica al redirigido. Los demás `fetch` directos del frontend siguen sin timeout explícito; se recomienda estandarizar a un wrapper en una iteración futura.

#### R3 — Changelog ✅
Este documento.

### Comportamiento documentado

**Timeouts típicos del backend** (workspace `gestor-de-deudas-con`, ~50 MB sin `node_modules`):

| Endpoint | Tiempo | Por qué |
| --- | --- | --- |
| `GET /health` | < 0.1s | Solo lee state interno |
| `GET /menu` | < 0.1s | Idem |
| `GET /files/read/...` | 0.1-0.5s | Lee del mirror, excluye `node_modules` |
| `POST /project/link` | ~6-7s | `status()` (6s) + rebind si cambia |
| `POST /project/seed` | ~7-8s | `status()` (6s) + `seed_project` (2s) |
| `POST /project/sync` | ~6-7s | `status()` (6s) + `sync_workspace_mirror` |

**Si la UI aborta con `net::ERR_ABORTED`:** significa que la UI tiene un timeout menor a 30s (probable con `fetch` directos). El comando probablemente SÍ se ejecutó en el backend, pero la UI no recibió la respuesta. Verificar con el `BagoClient.runCommand` que usa 150s (suficiente) vs los `fetch` directos.

### Archivos modificados en v0.2.1

| Path | Cambio |
| --- | --- |
| `backend/.bago/api/handlers_project.py` | R1.1: dict `state_cache` para evitar 4 llamadas a `status()` |
| `frontend/src/app/ControlPlane.tsx` | R2: `AbortController` con timeout 60s en fetch redirigido |
| `backend/.bago/integrations/pi/CHANGELOG.md` | R3: este documento |

### Estado del bridge BagoPiBridge

- 228 tests verdes + 1 skipped (sin cambios).
- Aislado de los fixes de BAGO 4.8.
- HOLD OPERATIVO preservado.

### Recomendaciones para v0.3

1. **Estandarizar timeouts en todos los `fetch` directos del frontend** (R2 ampliado). Crear un wrapper `fetchWithTimeout(url, options, ms)` en `api/client.ts` y migrar todos los call sites.
2. **Cachear `measure_context()` en el `SessionManager`** con TTL de 1-2s. Permitiría que `status()` sea O(1) para llamadas repetidas en poco tiempo.
3. **Limitar `seed_project` a directorios con `.bago/` o `.gabo/` pre-existentes** (proyectos nuevos) o a profundidad explícita del usuario. Evita que `seed` indexe accidentalmente proyectos gigantes.
4. **Revisar `rebind_project_root`** para confirmar que el `should_rebind` evita el rebind cuando el root no cambia. Ya está implementado, pero requiere tests de cobertura explícitos.

