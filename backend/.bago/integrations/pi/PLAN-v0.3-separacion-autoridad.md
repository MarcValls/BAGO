# BagoPiBridge — PLAN v0.3 · Implementación de la separación de autoridad

**Estado:** PLAN para ejecución
**Fecha:** 2026-07-16
**Documentos previos:**
- ARQ v0.3 — `backend/.bago/integrations/pi/ARQ-v0.3-separacion-autoridad.md`
- CRIT v0.3 — `backend/.bago/integrations/pi/CRIT-v0.3-separacion-autoridad.md`
**Versión del bridge:** v0.1 cerrado, v0.2 cerrado, v0.3 ejecución
**Fase objetivo al cierre:** 1 (pi-ai provider-only) con `enabled=true` solo tras smoke test real

---

## 1. Resumen ejecutivo

Este plan implementa los cambios arquitectónicos aprobados en CRIT v0.3, en 5 oleadas (W1-W5) con 17 tareas, 14 pruebas obligatorias y 4 JSON Schemas críticos. La duración estimada es **3-4 semanas** de trabajo secuencial. El cierre se alcanza con un smoke test real que atraviesa `bridge.py` → dispatch table → `BagoPiProviderAdapter` → sidecar → `ContextReceipt` con cuádruplo `provider/adapter/runtime/model`.

**Las 3 condiciones del CRIT son los gates de este plan:**

1. **D1** (dispatch table) implementado antes de la tarea #6 (invocación en `bridge.py`).
2. **Auditoría de las 14 pruebas** completada antes de la tarea #16 (creación de `test_v03_arq_separation.py`).
3. **D3** (fix `ControlShadow`) ejecutado en W1 (no bloquea el resto).

---

## 2. Decisiones heredadas del CRIT

| D | Decisión | Implicación para implementación |
| --- | --- | --- |
| **D1** | Dispatch table `(provider, adapter) → class` | Crear `backend/.bago/core/adapter_dispatch.py` con `ADAPTER_DISPATCH`; router BAGO lo consulta después de `ADAPTER_REGISTRY[provider]`. |
| **D2** | 4 campos separados en dataclass | Añadir strings a `BridgeExecutionRequest` y `ProviderAttestation`; no refactor. |
| **D3** | Usar `resolve_state_root()` de `api_state.py` | Modificar `control_shadow.py:32-33` para usar la función canónica. NO crear `state_paths.py`. |
| **D4** | Schemas en `backend/docs/contracts/pi/` | Crear 4 schemas críticos + 4 deseables en `docs/contracts/pi/`. |
| **D5** | Tarjeta "Bridge PI" siempre visible | Renderizar siempre; variante atenuada cuando `state == "disabled"`. |

---

## 3. Backlog de tareas (17 tareas, 5 oleadas)

### Leyenda

- **P0** = BLOQUEANTE (debe estar antes de Fase 1 GO)
- **P1** = MAYOR (antes de Fase 2 GO)
- **P2** = MENOR (antes de Fase 3 GO)
- **INFO** = sin acción

### W1 — Quick wins y cimientos (3 días)

#### Tarea #1 — Fix `ControlShadow` para usar `state_root` canónico [P1] — D3 del CRIT
**Condición CRIT #3**: ejecutada en paralelo, no bloquea el resto.

**Archivos:**
- `backend/.bago/api/control_shadow.py:30-37` (constructor y rutas)

**Cambio:**
```python
# Antes
def __init__(self, base_path: str | None = None):
    self.base_path = Path(base_path or os.getcwd())
    self.state_dir = self.base_path / ".bago" / "state"
    self.logs_dir = self.base_path / ".bago" / "logs"

# Después
def __init__(self, base_path: str | None = None, state_root: str | Path | None = None):
    from .api_state import resolve_state_root  # si está en el mismo paquete
    if state_root is None:
        # Fallback: base_path (legacy), pero warning explícito
        self.base_path = Path(base_path or os.getcwd())
        self.state_dir = self.base_path / ".bago" / "state"
        self.logs_dir = self.base_path / ".bago" / "logs"
    else:
        self.base_path = None
        self.state_dir = Path(state_root) / "ui_control_shadow"
        self.logs_dir = Path(state_root) / "logs"
```

**Verificación:**
- Test de regresión: las rutas no se computan si no se invoca el handler.
- Test de humo: invocar `ControlShadow()` con `state_root=/tmp/foo` → archivos en `/tmp/foo/ui_control_shadow/` y `/tmp/foo/logs/`.

**Cierre:** archivo modificado + 1 test de humo `test_control_shadow_uses_state_root`.

---

#### Tarea #2 — Audit de las 14 pruebas obligatorias [P0] — Condición CRIT #2

**Objetivo:** mapear cada una de las 14 pruebas a tests existentes o gaps.

**Mapa de auditoría** (estado actual verificado 2026-07-16):

| # | Test ARQ | Test existente | Ubicación | Acción |
| --- | --- | --- | --- | --- |
| 1 | `test_read_outside_workspace_scope_root_blocked` | `test_resolve_path_outside` | `test_scope_validator.py:32` | ✅ Referenciar |
| 2 | `test_write_in_phase_1_blocked` | `test_no_persistent_state_after_chat` + tests de policy | `test_phase1_adversarial.py:279` + `test_policy_gate.py` | ✅ Referenciar |
| 3 | `test_bash_in_phase_1_3_blocked` | `test_filter_env_blocks_pi_prefix` | `test_process_boundary.py:27` | ✅ Referenciar (process_bash) |
| 4 | `test_dotpi_load_blocked` | `test_deny_implicit_pi_sources` | `test_scope_validator.py:98` | ✅ Referenciar |
| 5 | `test_skills_extensions_load_blocked` | `test_filter_env_strips_unallowed` | `test_process_boundary.py:42` | ✅ Referenciar |
| 6 | `test_AGENTS_md_load_blocked` | `test_deny_implicit_pi_sources` (cubre `.agents`) + `test_negatives.py:474` | `test_scope_validator.py:98` + `test_negatives.py` | ✅ Referenciar (ampliar con AGENTS.md literal) |
| 7 | `test_provider_drift_blocks_certification` | `test_provider_drift_raises` | `test_phase1_adversarial.py:191` | ✅ Referenciar |
| 8 | `test_credential_outside_bago_rejected` | `test_credential_drift_detected` | `test_phase1_adversarial.py:112` | ✅ Referenciar |
| 9 | `test_tool_call_without_approval_rejected` | `test_kill_switch_phase_lock_blocks_below_max` (Fase 0) | `test_phase1_adversarial.py:85` | ⚠️ Falta test específico Fase 2 con `beforeToolCall` real |
| 10 | `test_tool_result_without_receipt_rejected` | `test_no_persistent_state_after_chat` (parcial) | `test_phase1_adversarial.py:279` | ⚠️ Falta test específico con `ToolReceipt.id` ausente |
| 11 | `test_agent_end_without_context_receipt_rejected` | (implícito en `test_no_persistent_state_after_chat`) | `test_phase1_adversarial.py:279` | ⚠️ Falta test específico |
| 12 | `test_path_escape_blocked` | `test_symlink_escape_denied` + NEG-011 + NEG-012 | `test_scope_validator.py:63` + `test_negatives.py:315,334` | ✅ Referenciar (3 casos: symlink, junction, UNC) |
| 13 | `test_sidecar_crash_keeps_session_intact` | `test_runner_cancel_kills_sidecar_process` (parcial — usa `cancel`, no `SIGKILL`) | `test_phase3_adversarial.py:392` | ⚠️ Falta con `SIGKILL` real |
| 14 | `test_cross_session_contamination_zero` | (no existe) | — | ❌ **GAPS: 4 tests nuevos** |

**Tests #15 (bonus) — secretos en logs:**
- `test_secret_does_not_appear_in_receipt` ✅ ya existe en `test_phase1_adversarial.py:143`.

**Gaps identificados (4 tests nuevos necesarios):**
- T9: `beforeToolCall` real sin approval → `ToolNotApproved`
- T10: `execution.done` sin `ToolReceipt.id` → `BridgeError`
- T11: `agent_end` sin `ContextReceipt` → sesión no cierra
- T13: SIGKILL del sidecar → sesión BAGO intacta
- T14: 2 ejecuciones consecutivas con providers distintos → cero contaminación

**Cierre:** tabla de auditoría como `backend/tests/integrations/pi/AUDIT-14-tests.md` + lista de gaps.

---

#### Tarea #3 — Crear 4 JSON Schemas críticos en `docs/contracts/pi/` [P1] — D4 del CRIT

**Archivos a crear:**
- `backend/docs/contracts/pi/bridge_handshake.schema.json`
- `backend/docs/contracts/pi/bridge_request.schema.json`
- `backend/docs/contracts/pi/provider_attestation.schema.json`
- `backend/docs/contracts/pi/policy_manifest.schema.json`

**Estructura de cada schema (basada en `bago_v4_runtime_contract.json`):**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://bago.local/contracts/pi/bridge_handshake.schema.json",
  "title": "BagoPiBridge Handshake",
  "version": "0.3.0",
  "type": "object",
  "required": ["protocol_version", "pi_version", "lockfile_hash", "sidecar_hash", "mode", "capabilities"],
  "properties": {
    "protocol_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "pi_version": { "type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$" },
    "lockfile_hash": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
    "sidecar_hash": { "type": "string", "pattern": "^[a-f0-9]{64}$" },
    "mode": { "enum": ["rpc", "embedded", "disabled"] },
    "capabilities": { ... }
  }
}
```

**Cierre:** 4 archivos JSON Schema válidos, validables con `jsonschema` CLI.

---

### W2 — Cuádruplo provider/adapter/runtime/model (4 días)

#### Tarea #4 — Extender `BridgeExecutionRequest` con `requested_adapter` y `requested_runtime` [P0] — Brecha #1

**Archivo:** `backend/.bago/integrations/pi/contracts.py:208-228`

**Cambio:**
```python
@dataclass(frozen=True)
class BridgeExecutionRequest:
    # ... campos existentes ...
    requested_provider: str
    requested_model: str
    # NUEVO
    requested_adapter: str   # "pi-ai" | "bago-native"
    requested_runtime: str   # "node-sidecar" | "python-inproc"
```

**Validación (en `__post_init__` o helper):**
- `requested_provider != "pi"` (invariante).
- `requested_adapter in {"pi-ai", "bago-native", "litellm"}`.
- `requested_runtime in {"node-sidecar", "python-inproc", "wasm"}`.

**Cierre:** dataclass extendido + 1 test `test_bridge_request_invariant_provider_not_pi`.

---

#### Tarea #5 — Extender `ProviderAttestation` con `effective_adapter` y `effective_runtime` [P0] — Brecha #2

**Archivo:** `backend/.bago/integrations/pi/contracts.py:362-373`

**Cambio:**
```python
@dataclass(frozen=True)
class ProviderAttestation:
    requested_provider: str
    effective_provider: str
    requested_adapter: str   # NUEVO
    effective_adapter: str   # NUEVO
    requested_runtime: str   # NUEVO
    effective_runtime: str   # NUEVO
    requested_model: str
    effective_model: str
    endpoint_normalized: str
    adapter: str             # (legacy — se mantiene para backward compat)
    bridge_version: str
    pi_package_version: str
    pi_lockfile_hash: str
    sidecar_artifact_hash: str
```

**Cierre:** dataclass extendido + 1 test `test_attestation_drift_detection_quadruplet`.

---

#### Tarea #6 — Crear `adapter_dispatch.py` con el dispatch table de D1 [P0] — Brecha #3 + Condición CRIT #1

**Archivo nuevo:** `backend/.bago/core/adapter_dispatch.py`

**Contenido:**
```python
"""adapter_dispatch.py — dispatch table (provider, adapter) → adapter_class.

El ADAPTER_REGISTRY canónico indexa por provider (anthropic → AnthropicAdapter).
Este módulo añade una segunda dimensión: adapter (pi-ai, bago-native, litellm).
La regla de invariante: provider NUNCA es "pi"; pi-ai es siempre un adapter.
"""

from __future__ import annotations

from typing import Any, Type
from .provider_adapter import ProviderAdapter


# (provider, adapter_name) → adapter_class
ADAPTER_DISPATCH: dict[tuple[str, str], Type[ProviderAdapter]] = {
    # Adapter nativo BAGO (sin bridge)
    ("ollama-local", "bago-native"): <OllamaLocalAdapter>,
    ("anthropic", "bago-native"): <AnthropicAdapter>,
    # Bridge PI (subordinado, requiere integrations.pi.enabled=true)
    # Se inyecta dinámicamente en runtime (no import estático para evitar
    # que el sidecar se cargue en arranque).
}


def resolve_adapter(provider: str, adapter_name: str) -> Type[ProviderAdapter] | None:
    """Resuelve (provider, adapter) → adapter_class.

    Returns None si no hay dispatch configurado.
    Raises BridgeError si el adapter es pi-ai y la integración está deshabilitada.
    """
    key = (provider, adapter_name)
    if key in ADAPTER_DISPATCH:
        return ADAPTER_DISPATCH[key]

    # Si el adapter es pi-ai, intentar carga dinámica del bridge
    if adapter_name == "pi-ai":
        from .bago.integrations.pi.config import load_pi_bridge_config
        from .bago.integrations.pi.provider_adapter import BagoPiProviderAdapter
        config = load_pi_bridge_config()
        if config.enabled and config.max_phase >= 1:
            return BagoPiProviderAdapter
        raise BridgeError("pi-ai adapter requires integrations.pi.enabled=true and max_phase>=1")

    return None
```

**Cierre:** módulo creado + 1 test `test_dispatch_resolves_pi_ai_when_enabled`.

---

#### Tarea #7 — Modificar `bridge.py` para invocar el dispatch table en `/api/v1/chat` [P0] — Brecha #3

**Archivo:** `backend/.bago/api/bridge.py` (router HTTP)

**Cambio en el handler de chat:**

```python
# Antes (pseudocódigo del router actual)
adapter_class = ADAPTER_REGISTRY.get(provider)
adapter = adapter_class(config)

# Después
from adapter_dispatch import resolve_adapter
adapter_class = ADAPTER_REGISTRY.get(provider)
if adapter_class is None:
    return 400, "unknown provider"
adapter = adapter_class(config)

# Si el provider tiene un adapter pi-ai configurado, intentar dispatch
pi_adapter = resolve_adapter(provider, "pi-ai")
if pi_adapter is not None:
    # El adapter del bridge se inyecta como wrapper alrededor del nativo
    # El bridge controla la llamada, no el nativo.
    pi_instance = pi_adapter(...)
    return pi_instance.chat(messages, model, **kwargs)
```

**Cierre:** router modificado + 1 test de integración `test_chat_routes_to_pi_ai_when_enabled`.

---

#### Tarea #8 — Test de humo del smoke test en `bridge.py` real [P0] — Gate de promoción a Fase 1

**Objetivo:** ejecutar la llamada real a `BagoPiProviderAdapter` desde `bridge.py` con el sidecar mock, y producir un `ContextReceipt` con cuádruplo `provider/adapter/runtime/model`.

**Procedimiento:**
1. Activar `integrations.pi.enabled=true` y `max_phase=1` en `backend/.bago/config.json` temporalmente.
2. Arrancar backend en puerto 8080.
3. `POST /api/v1/chat` con `provider=anthropic, model=claude-sonnet-4-5, adapter=pi-ai`.
4. Verificar respuesta 200 con `ContextReceipt` que contenga:
   - `requested_provider="anthropic"`, `effective_provider="anthropic"`
   - `requested_adapter="pi-ai"`, `effective_adapter="pi-ai"`
   - `requested_runtime="node-sidecar"`, `effective_runtime="node-sidecar"`
   - `verification_state="executed_unverified"` (nunca `verified`)

**Cierre:** log del smoke test con traceback completo del flujo BAGO → dispatch → BagoPiProviderAdapter → sidecar → ContextReceipt.

---

### W3 — 4 JSON Schemas deseables + UI bridge_state (3 días)

#### Tarea #9 — Crear 4 JSON Schemas deseables en `docs/contracts/pi/` [P2] — Brecha #5 (deseables)

**Archivos a crear:**
- `backend/docs/contracts/pi/bridge_event.schema.json`
- `backend/docs/contracts/pi/tool_request.schema.json`
- `backend/docs/contracts/pi/tool_receipt_payload.schema.json`
- `backend/docs/contracts/pi/context_receipt_payload.schema.json`

**Diferencia con los críticos:** estos describen eventos de runtime, no del handshake inicial. Son útiles para validación en logs y para clientes que consuman el stream JSONL.

**Cierre:** 4 archivos JSON Schema válidos.

---

#### Tarea #10 — Añadir tipos `BridgeState` y `ActiveBridges` en `ui-react/src/contracts/backend.ts` [P2] — Brecha #6

**Archivo:** `frontend/src/contracts/backend.ts`

**Cambio:**
```typescript
export type BridgeState =
  | "disabled"
  | "provider_only"
  | "readonly_tools"
  | "agent_capture";

export type ActiveBridges = {
  pi: {
    state: BridgeState;
    version: string | null;
    runtime: string | null;
    capabilities: {
      tools: number;
      skills: number;
      extensions: number;
    };
    last_health: string | null;  // ISO8601
  };
};
```

**Backend complementario:** añadir `/api/v1/bridges` que devuelva `ActiveBridges` con el estado actual del bridge.

**Cierre:** tipos TypeScript + endpoint backend.

---

#### Tarea #11 — Tarjeta "Bridge PI" en `SystemSurface` (siempre visible) [P2] — Brecha #9 + D5

**Archivo:** `frontend/src/features/context-tree/` (nuevo componente o extensión de SystemSurface)

**Diseño:**
- Si `state === "disabled"`: variante atenuada con texto "Integración PI: deshabilitada por configuración (cuarentena)".
- Si `state !== "disabled"`: tarjeta con `version`, `runtime`, `capabilities`, `last_health` y badge de color según estado.
- **Sin botones** — la UI solo consume estado.

**Cierre:** componente creado + screenshot de revisión visual.

---

### W4 — Lockfile + 14 pruebas obligatorias (5 días)

#### Tarea #12 — Lockfile + hash cuando se decida promover a PI real [P1] — Brecha #8

**Trigger:** esta tarea se activa solo cuando se decida promover el canary con `pi-ai@0.80.7` real. Mientras el sidecar sea mock, no aplica.

**Acciones:**
1. Fijar `@earendil-works/pi-ai@0.80.7` exacto en `sidecar/package.json`.
2. `npm ci --ignore-scripts` → genera `package-lock.json`.
3. Calcular SHA-256 del lockfile: `sha256sum package-lock.json`.
4. Guardar en `backend/.bago/integrations/pi/expected_lockfile.sha256`.
5. `pi_lockfile_hash` en policy se compara con este archivo.
6. Generar `backend/.bago/integrations/pi/SBOM.json` con `npm sbom`.
7. Adjuntar `LICENSE-PI.txt` (MIT).

**Cierre:** lockfile generado + hash registrado + SBOM + LICENSE.

---

#### Tarea #13 — Crear los 4 tests nuevos identificados en la auditoría (#2) [P0] — Brecha #10

**Archivo nuevo:** `backend/tests/integrations/pi/test_v03_arq_separation.py`

**Tests nuevos a crear (gaps del audit):**

```python
def test_beforeToolCall_without_approval_rejected():
    """Fase 2+: tool call sin approval flag → ToolNotApproved"""

def test_execution_done_without_tool_receipt_rejected():
    """Fase 2+: agent_end con tool_call sin ToolReceipt.id → BridgeError"""

def test_agent_end_without_context_receipt_rejected():
    """Fase 3+: cierre de agente sin ContextReceipt → sesión no termina"""

def test_sidecar_SIGKILL_keeps_session_intact():
    """Fase 3+: matar sidecar con SIGKILL → sesión BAGO no contaminada"""
    # NOTA: test_runner_cancel_kills_sidecar_process usa cancel, no SIGKILL

def test_cross_session_contamination_zero():
    """Fase 3+: 2 ejecuciones consecutivas con providers distintos → cero memoria"""
```

**Tests consolidados (referencias):**
```python
# Cabecera del archivo con tabla de auditoría
"""test_v03_arq_separation.py — Consolidación de las 14 pruebas obligatorias del ARQ v0.3.

| # | Test                              | Fuente                                  | Estado   |
| -- | --------------------------------- | --------------------------------------- | -------- |
|  1 | test_read_outside_scope_blocked   | test_scope_validator.py::test_resolve_path_outside | REFERENCED |
|  2 | test_write_in_phase_1_blocked     | test_phase1_adversarial.py::test_no_persistent_state_after_chat | REFERENCED |
| ... | ...                             | ...                                     | ...      |
"""
```

**Cierre:** archivo creado + 14 entradas en tabla + 4 tests nuevos pasando.

---

#### Tarea #14 — Test del dispatch table (D1) [P0] — Condición CRIT #1

**Archivo:** `backend/tests/core/test_adapter_dispatch.py` (nuevo)

**Tests:**
```python
def test_dispatch_returns_none_for_unknown():
def test_dispatch_returns_native_for_bago_native():
def test_dispatch_returns_pi_ai_when_enabled():
def test_dispatch_raises_when_pi_ai_disabled():
def test_dispatch_invariant_provider_never_pi():
```

**Cierre:** archivo creado + 5 tests pasando.

---

#### Tarea #15 — Test del cuádruplo en dataclasses [P0] — Brechas #1 y #2

**Archivo:** `backend/tests/integrations/pi/test_contracts_v03.py` (nuevo)

**Tests:**
```python
def test_bridge_request_invariant_provider_not_pi():
def test_bridge_request_has_adapter_and_runtime():
def test_attestation_has_effective_adapter_and_runtime():
def test_attestation_drift_detection_quadruplet():
def test_attestation_serialization_roundtrip():
```

**Cierre:** archivo creado + 5 tests pasando.

---

### W5 — Cierre y gate de promoción (3 días)

#### Tarea #16 — Suite final + verificación de 228 tests sin regresión [P0]

**Comando:** `python -m pytest backend/tests/integrations/pi/ -v`

**Verificación:**
- 228 tests existentes siguen verdes.
- 1 skipped sigue skipped.
- Tests nuevos (4 + 5 + 5 = 14) están verdes.
- **Total esperado:** 242 tests verdes + 1 skipped.

**Cierre:** log de pytest con `242 passed, 1 skipped in X.XXs`.

---

#### Tarea #17 — Documentación de cierre en CHANGELOG.md [P0]

**Archivo:** `backend/.bago/integrations/pi/CHANGELOG.md`

**Añadir:**
```markdown
## v0.3 — Cierre 2026-07-XX

### Cambios arquitectónicos
- D1: dispatch table `(provider, adapter) → class` en `backend/.bago/core/adapter_dispatch.py`
- D2: 4 campos planos (no struct anidado) en `BridgeExecutionRequest` y `ProviderAttestation`
- D3: `ControlShadow` redirigido a `state_root` canónico
- D4: 8 JSON Schemas en `backend/docs/contracts/pi/`
- D5: tarjeta "Bridge PI" siempre visible en `SystemSurface`

### Brechas cerradas
1. `BridgeExecutionRequest` con `requested_adapter` y `requested_runtime`
2. `ProviderAttestation` con `effective_adapter` y `effective_runtime`
3. `bridge.py` invoca `BagoPiProviderAdapter` vía dispatch table
4. `ControlShadow` en `state_root` (no en proyecto del usuario)
5. 8 JSON Schemas contractuales
6-9. UI bridge_state + tarjeta
10. 14 pruebas obligatorias (8 referenciadas + 4 nuevas + 2 mejoradas)

### Estado
- Smoke test real `bridge.py` → dispatch → BagoPiProviderAdapter → sidecar → ContextReceipt: ✅
- Cuádruplo provider/adapter/runtime/model en ContextReceipt: ✅
- `enabled=true` permitido solo en workspace de prueba, NO en producción.
- HOLD OPERATIVO preservado.
- 242 tests verdes + 1 skipped (228 + 14 nuevos).

### Veredicto CRIT
GO CONDICIONADO con smoke test obligatorio antes de promoción a `enabled=true` en producción.
```

**Cierre:** changelog actualizado.

---

## 4. Cronograma

| Semana | Días | Tareas | Entregable | Tests añadidos |
| --- | --- | --- | --- | --- |
| **W1** | 3 | #1, #2, #3 | `control_shadow` corregido, audit table, 4 schemas críticos | 1 (smoke) |
| **W2** | 4 | #4, #5, #6, #7, #8 | Cuádruplo en dataclasses, dispatch table, smoke test real | 5 (contracts) + 5 (dispatch) |
| **W3** | 3 | #9, #10, #11 | 4 schemas deseables, tipos UI, tarjeta | 0 (schemas ya validados) |
| **W4** | 5 | #12, #13, #14, #15 | Lockfile, 14 pruebas, tests dispatch y contracts | 4 (gaps) |
| **W5** | 3 | #16, #17 | Suite final, changelog | — |
| **Total** | **18 días** | **17 tareas** | **v0.3 cerrado** | **14 tests nuevos** |

**Buffer recomendado:** 4-5 días para imprevistos (regresiones, fixes de W1-W2, etc.). Total realista: **3-4 semanas**.

---

## 5. Riesgos del plan

| # | Riesgo | Probabilidad | Impacto | Mitigación |
| --- | --- | --- | --- | --- |
| R1 | El dispatch table rompe el router canónico BAGO | Media | Alto | Tests de regresión en W2 (#7); rollback inmediato si 228 tests fallan. |
| R2 | `BagoPiProviderAdapter` no se invoca correctamente desde el dispatch | Baja | Alto | W2 incluye smoke test real (#8) ANTES de promover. |
| R3 | Auditoría de 14 tests revela más gaps de los 4 estimados | Media | Medio | Tarea #2 es exploratoria; ajustar #13 si hay más gaps. |
| R4 | Lockfile con PI real genera incompatibilidades (Node 22.19 vs 20.0) | Alta | Bajo | Engines.node está en `>=20.0.0`; puede romperse con `pi-ai@0.80.7` que requiere `>=22.19`. Subir engines en sidecar. |
| R5 | El smoke test real revela drift entre mock y PI real | Alta | Alto | El plan es que Fase 1 GO se alcance con mock; Fase 1 GO REAL con `pi-ai` real es trabajo de v0.4 (canary). |
| R6 | Cambios en D1 rompen backward compat de tests | Baja | Medio | Mantener `ADAPTER_REGISTRY` intacto; añadir `ADAPTER_DISPATCH` como segunda capa. |

---

## 6. Gate de promoción a Fase 1 GO

El plan termina con W5, pero **`enabled=true` en producción NO se activa** hasta que se cumplan las 3 condiciones del CRIT simultáneamente:

1. ✅ D1 (dispatch table) implementado y testeado.
2. ✅ Auditoría de las 14 pruebas completada.
3. ✅ D3 (`ControlShadow` corregido) implementado y testeado.

**MÁS:**
- 242 tests verdes + 1 skipped.
- Smoke test real atravesó `bridge.py` con `BagoPiProviderAdapter` invocado.
- `ContextReceipt` con cuádruplo `provider/adapter/runtime/model` completo.
- Veredicto CRIT v0.3 cerrado con GO CONDICIONADO.

**Después del cierre del plan, el siguiente paso sería v0.4 — Canary con `pi-ai@0.80.7` real** (este plan NO incluye el canary real; solo prepara la infraestructura).

---

## 7. Cierre PLAN

**PLAN v0.3 veredicto:** **EJECUTABLE** con 17 tareas, 5 semanas (con buffer: 3-4 semanas), 14 tests nuevos.

**Gates del plan:**
- T1-T3 (W1) → cimientos + auditorías.
- T4-T8 (W2) → cuádruplo + dispatch + smoke test.
- T9-T11 (W3) → schemas + UI.
- T12-T15 (W4) → lockfile + 14 pruebas.
- T16-T17 (W5) → suite + changelog.

**HOLD OPERATIVO preservado.**

**Próximo paso:** ejecutar las tareas en orden. Empezar por T1 (fix `ControlShadow`) en paralelo con T2 (auditoría de pruebas).
