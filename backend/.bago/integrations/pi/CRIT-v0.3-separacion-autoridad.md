# BagoPiBridge — CRIT v0.3 · Revisión del ARQ v0.3

**Estado:** CRIT — Veredicto
**Fecha:** 2026-07-16
**Documento revisado:** `ARQ-v0.3-separacion-autoridad.md`
**Versión del bridge:** v0.1 cerrado, v0.2 cerrado, v0.3 propuesto
**Fase actual:** 0 (handshake sin modelo) — sidecar mock local

---

## 1. Metodología de revisión

Cada decisión **D1-D5** se evalúa en 4 ejes:

1. **Coherencia con canon BAGO** — ¿rompe alguna invariante existente?
2. **Complejidad de implementación** — ¿cuánto cuesta el cambio?
3. **Riesgo de regresión** — ¿puede romper 228 tests verdes + 1 skipped?
4. **Alineación con la separación de autoridad BAGO↔PI** — ¿reafirma que BAGO es la frontera?

Las 10 brechas se evalúan con criterios: ¿es BLOQUEANTE para Fase 1 GO, MAYOR para Fase 2 GO, MENOR para Fase 3 GO, o INFO?

---

## 2. Revisión de las 10 brechas

### Brecha #1 — Falta `requested_adapter` y `requested_runtime` en `BridgeExecutionRequest`

**Severidad ARQ:** BLOQUEANTE → **CRIT confirma BLOQUEANTE**

- **Canon:** El dataclass es el contrato inter-proceso. Si no transporta el cuádruplo, el `ContextReceipt` no puede atestiguar drift en `adapter` ni `runtime`. Esto es exactamente el modo en que la sección 2.1.2 del ARQ dice que "BAGO puede detectar si se pidió Anthropic y finalmente se ejecutó OpenAI". Mismo argumento aplica a adapter/runtime.
- **Complejidad:** 2 campos string, frozen dataclass, sin migración de `to_dict` (regenera con `asdict`).
- **Riesgo regresión:** NINGUNO — el dataclass tiene `to_dict()` que serializa todos los campos; añadir 2 no rompe consumidores. Verificado leyendo `contracts.py:215-228`.
- **Alineación autoridad:** REFUERZA. BAGO recibe los 4 vectores y puede atestiguar drift en cada uno.

**CRIT veredicto:** APROBADO. Acción pasa a PLAN v0.3 sin cambios.

### Brecha #2 — Falta `effective_adapter` y `effective_runtime` en `ProviderAttestation`

**Severidad ARQ:** BLOQUEANTE → **CRIT confirma BLOQUEANTE**

- **Canon:** Mismo argumento que #1, pero del lado "effective" (lo que el sidecar realmente ejecutó).
- **Complejidad:** 2 campos string adicionales al dataclass de 10 campos.
- **Riesgo regresión:** BAJO. El campo `adapter` ya existe; añadir `effective_adapter` no rompe. `runtime` es nuevo pero aditivo.
- **Alineación autoridad:** REFUERZA. La attestation es la prueba que BAGO usa para detectar drift.

**CRIT veredicto:** APROBADO. Acción pasa a PLAN v0.3.

### Brecha #3 — `bridge.py` real NO invoca `BagoPiProviderAdapter`

**Severidad ARQ:** BLOQUEANTE → **CRIT confirma BLOQUEANTE con matiz**

- **Canon:** El bridge es la única ruta de chat en producción. Si no se invoca el adapter del bridge, la integración **NO EXISTE operacionalmente** — es código que se testea pero nunca se ejecuta en producción.
- **Complejidad:** MEDIA-ALTA. Requiere modificar el router de `/api/v1/chat` (o equivalente) para:
  1. Leer `config.integrations.pi.*`.
  2. Decidir dispatch por `(provider, adapter)` no solo por `provider`.
  3. Inyectar `BagoPiProviderAdapter` cuando aplique.
- **Riesgo regresión:** ALTO si se hace mal. El router canónico usa `ADAPTER_REGISTRY` indexado por `provider` (verificado en `session_utils.py:24`). Si se mete `BagoPiProviderAdapter` ahí, colisiona con `provider="anthropic"`. **D1 es la decisión que resuelve esto** — ver §3.
- **Alineación autoridad:** REFUERZA. La integración debe pasar por el router canónico, no por una ruta secreta.

**CRIT veredicto:** APROBADO el objetivo, pero **D1 es prerequisito** (ver §3). Acción pasa a PLAN v0.3 con la nota: "no implementar hasta que D1 esté aprobada y la inyección del bridge en el router sea coherente con el patrón actual".

### Brecha #4 — `ControlShadow` escribe en `base_path/.bago/{state,logs}`

**Severidad ARQ:** MAYOR → **CRIT confirma MAYOR**

- **Canon:** Verificado. `control_shadow.py:32-33`:
  ```python
  self.state_dir = self.base_path / ".bago" / "state"  # ❌ en el proyecto del usuario
  self.logs_dir = self.base_path / ".bago" / "logs"    # ❌ en el proyecto del usuario
  ```
  Esto **contamina el workspace del usuario** con estado interno de BAGO. La UI no debe dejar huella en el proyecto del usuario.
- **Complejidad:** BAJA. Cambiar 2 líneas para usar `resolve_state_root()`. La función ya existe en `backend/.bago/api/api_state.py:18`.
- **Riesgo regresión:** BAJO. `ControlShadow` no tiene tests que asuman la ruta actual (verificado: `grep "control_shadow" backend/tests/` no retorna nada).
- **Alineación autoridad:** REFUERZA. El estado de UI vive en `state_root` canónico, no en el proyecto.

**CRIT veredicto:** APROBADO. Acción pasa a PLAN v0.3 con **D3 ya resuelta** (§3).

### Brecha #5 — No existe `backend/.bago/contracts/pi/` con 8 JSON Schemas

**Severidad ARQ:** MAYOR → **CRIT MAYOR con matiz de ubicación (D4)**

- **Canon:** El bridge tiene dataclasses Python (`BridgeExecutionRequest`, `ProviderAttestation`, etc.) que son **el contrato real**. Los JSON Schemas son **documentación + validación opcional**.
- **Complejidad:** MEDIA. 8 schemas × 1-2 días = 1-2 semanas de trabajo.
- **Riesgo regresión:** NINGUNO — son archivos nuevos.
- **Alineación autoridad:** NEUTRAL. Los schemas no cambian quién controla qué; solo formalizan.

**CRIT veredicto:** APROBADO con priorización. **Críticos** (deben existir antes de Fase 1 GO):
- `bridge_handshake.schema.json`
- `bridge_request.schema.json`
- `provider_attestation.schema.json`
- `policy_manifest.schema.json`

**Deseables** (pueden existir en paralelo sin bloquear):
- `bridge_event.schema.json`
- `tool_request.schema.json`
- `tool_receipt_payload.schema.json`
- `context_receipt_payload.schema.json`

Acción pasa a PLAN v0.3 con la nota: "4 críticos antes de Fase 1 GO; 4 deseables en v0.4".

### Brecha #6 — UI no contempla `bridge_state` ni `active_bridges`

**Severidad ARQ:** MENOR → **CRIT confirma MENOR**

- **Canon:** La UI no debe activar capacidades por sí misma. Solo consume estado del backend.
- **Complejidad:** BAJA. Añadir tipos en `backend/.../contracts/backend.ts` y 1 tarjeta en `SystemSurface`.
- **Riesgo regresión:** NINGUNO — la UI actual no depende de estos tipos.
- **Alineación autoridad:** REFUERZA. La UI refleja el estado declarado por el backend.

**CRIT veredicto:** APROBADO. Acción pasa a PLAN v0.3 con **D5 como sub-decisión** (§3).

### Brecha #7 — Sidecar no carga `@earendil-works/pi-ai` (es mock)

**Severidad ARQ:** INFO → **CRIT confirma INFO**

- **Canon:** El sidecar debe ser subordinado a BAGO. Mientras sea mock local, BAGO es el único que decide qué corre. La promoción a PI real es un paso contractual con su propio ARQ+CRIT+PLAN.
- **Complejidad:** La promoción a PI real es trabajo de v0.4+ (canary con `npm ci --ignore-scripts`, lockfile pinned, SBOM).
- **Riesgo regresión:** NINGUNO en el estado actual.
- **Alineación autoridad:** CONSISTENTE. El mock es un placeholder explícito.

**CRIT veredicto:** CONFIRMADO. Sin acción en v0.3.

### Brecha #8 — Lockfile e integridad aún no registrados

**Severidad ARQ:** MAYOR → **CRIT MAYOR (acoplado a brecha #7)**

- **Canon:** Sin lockfile, no hay reproducibilidad. Sin hash, no hay verificación de "lo que está corriendo es lo que esperamos".
- **Complejidad:** BAJA cuando se decida fijar la versión (`npm ci --ignore-scripts`, `sha256sum`).
- **Riesgo regresión:** NINGUNO.
- **Alineación autoridad:** REFUERZA. La attestation incluye `pi_lockfile_hash` que ya está en el dataclass.

**CRIT veredicto:** APROBADO. Acoplado a #7: cuando se fije `pi-ai@0.80.7`, generar lockfile y registrar SHA-256. Acción pasa a PLAN v0.3 en la sub-tarea "lockfile + hash".

### Brecha #9 — UI no muestra "Bridge PI" en SystemSurface

**Severidad ARQ:** MENOR → **CRIT confirma MENOR (acoplado a #6)**

- **Canon:** Operador debe poder ver el estado del bridge sin tener que abrir DevTools o leer logs.
- **Complejidad:** BAJA.
- **Riesgo regresión:** NINGUNO.
- **Alineación autoridad:** NEUTRAL. Solo refleja.

**CRIT veredicto:** APROBADO. Acoplado a #6 y D5.

### Brecha #10 — Sin `test_v03_arq_separation.py` con las 14 pruebas obligatorias

**Severidad ARQ:** BLOQUEANTE → **CRIT BLOQUEANTE con cobertura parcial**

- **Canon:** Las pruebas obligatorias son la **puerta de promoción** entre fases. Sin ellas, no hay manera de saber si la separación de autoridad es real o solo declarada.
- **Complejidad:** MEDIA-ALTA. 14 tests, pero varios ya existen dispersos en `test_phase1_adversarial.py`, `test_negatives.py`, `test_phase2_negatives.py`, etc.
- **Riesgo regresión:** NINGUNO — son tests nuevos.
- **Alineación autoridad:** REFUERZA. Cada test es un test de "BAGO sigue siendo la frontera".

**Cobertura ya existente (verificado):**
- ✅ `test_provider_drift_raises` — `test_phase1_adversarial.py:191`
- ✅ `test_secret_does_not_appear_in_receipt` — `test_phase1_adversarial.py:143`
- ✅ `test_fallback_flag_rejected` — `test_phase1_adversarial.py:221`
- ✅ `test_kill_switch_global_disables_adapter` — `test_phase1_adversarial.py:57`
- ✅ `test_kill_switch_phase_lock_blocks_below_max` — `test_phase1_adversarial.py:85`
- ✅ `test_no_persistent_state_after_chat` — `test_phase1_adversarial.py:279`
- ✅ `test_credential_drift_detected` — `test_phase1_adversarial.py:112`
- ✅ `test_unknown_event_from_sidecar_rejected` — `test_phase1_adversarial.py:251`

**Faltantes o a verificar:**
- ⚠️ `test_read_outside_workspace_scope_root_blocked` — verificar en `test_scope_validator.py`
- ⚠️ `test_path_escape_blocked` (symlink, junction, UNC) — verificar en `test_scope_validator.py`
- ⚠️ `test_dotpi_load_blocked` — verificar en `test_process_boundary.py` y `test_sidecar_integration.py`
- ⚠️ `test_AGENTS_md_load_blocked` — verificar que existe
- ⚠️ `test_sidecar_crash_keeps_session_intact` — verificar
- ⚠️ `test_cross_session_contamination_zero` — verificar
- ⚠️ `test_skills_extensions_load_blocked` — verificar en `test_process_boundary.py`

**CRIT veredicto:** APROBADO. Acción pasa a PLAN v0.3 con la instrucción: "auditar primero qué pruebas ya existen; consolidar las 14 en `test_v03_arq_separation.py` o referenciarlas desde ahí si ya están. Las pruebas nuevas solo si la auditoría revela gaps."

---

## 3. Revisión de las decisiones D1-D5

### D1 — ¿Cómo invocar `BagoPiProviderAdapter` en el router BAGO?

**Opciones:**
- (a) Vía `ADAPTER_REGISTRY` (registrar `pi-ai` como provider)
- (b) Vía dispatch table separado `(provider, adapter) → adapter_class`
- (c) Vía invocación directa desde `bridge.py` (ruta especial)

**Análisis técnico (verificado en código):**

`backend/.bago/core/session_utils.py:24`:
```python
ADAPTER_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "ollama-local": OllamaLocalAdapter,
    "anthropic": AnthropicAdapter,
    ...
}
```

**El registry indexa por `provider`, no por `adapter`**. Esto es semánticamente correcto: si pido `provider=anthropic`, BAGO debe invocar `AnthropicAdapter` (nativo BAGO) — no `BagoPiProviderAdapter` (que es un adapter técnico alternativo que también habla Anthropic).

**Conclusión técnica:**

- **Opción (a) es incorrecta semánticamente.** Registrar `pi-ai` en `ADAPTER_REGISTRY` significaría que `provider=pi-ai`, que es exactamente lo que el ARQ v0.3 prohíbe ("provider nunca puede ser igual a `pi`").
- **Opción (c) es un workaround.** Funciona pero crea una ruta secreta que el router canónico no ve, lo que rompe la autoridad BAGO.
- **Opción (b) es la correcta.** Crear un **dispatch table secundario** `ADAPTER_DISPATCH: dict[(provider, adapter_name), adapter_class]` o una lista de `(provider, adapter_name, adapter_class)` que el router consulta **después** de resolver `ADAPTER_REGISTRY[provider]`. Esto mantiene la semántica: `provider` identifica el upstream; `adapter` identifica la pila técnica.

**Decisión CRIT:** **D1 = opción (b) — dispatch table secundario `(provider, adapter) → adapter_class`**. Razón: respeta la separación `provider ≠ adapter` y no introduce una ruta secreta.

**Implicación:** crear un nuevo módulo (o reutilizar el dataclass existente) con la tabla de dispatch. El bridge se inyecta cuando `ADAPTER_DISPATCH[(provider, "pi-ai")]` está presente **Y** `integrations.pi.enabled=true` **Y** `max_phase >= 1`.

### D2 — ¿Cuádruplo `provider/adapter/runtime/model` como 4 campos o struct anidado?

**Opciones:**
- (a) 4 campos separados en el dataclass
- (b) Struct anidado `ProviderIdentity` con 4 campos

**Análisis técnico:**

- **Serialización JSON:** `dataclasses.asdict()` desempaca structs anidados automáticamente, pero los tests existentes asumen acceso por atributo (`attestation.requested_provider`).
- **Backward compat:** Los 228 tests actuales referencian `.requested_provider`, `.effective_provider` directamente. Cambiar a `.identity.requested_provider` rompería todos.
- **Claridad:** 4 campos planos son más fáciles de leer en logs y receipts.

**Decisión CRIT:** **D2 = opción (a) — 4 campos separados**. Razón: backward compat con 228 tests, claridad operativa, no introduce indirección.

**Implicación:** añadir `requested_adapter`, `requested_runtime`, `effective_adapter`, `effective_runtime` como 4 nuevos strings en los 2 dataclasses (`BridgeExecutionRequest` y `ProviderAttestation`).

### D3 — ¿`state_root` desde `request_context` o `state_paths.py`?

**Opciones:**
- (a) `request_context`
- (b) Nuevo módulo `state_paths.py`

**Análisis técnico (verificado):**

`backend/.bago/api/api_state.py:18` ya tiene `resolve_state_root(handler)` con orden canónico:
1. `session_mgr.state_root`
2. `session_context.current_state_root()` (REPL fallback)
3. `~/.bago/state` (last resort)

**`request_context.py` no tiene `state_root`** (verificado: `grep "state_root" backend/.bago/api/request_context.py` retorna vacío).

**Conclusión técnica:**

- **Opción (a) es incorrecta** — `request_context` no expone `state_root`.
- **Opción (b) es redundante** — ya existe `api_state.py::resolve_state_root()`.
- **La opción correcta (no listada en el ARQ):** usar `resolve_state_root(self)` desde `api_state.py`. Es el módulo canónico que YA centraliza la lógica.

**Decisión CRIT:** **D3 = opción (a) reinterpretada — usar `resolve_state_root()` de `backend/.bago/api/api_state.py`**. Razón: ya existe, tiene orden canónico, otros handlers (`handlers_memory`, `handlers_schedule`, `handlers_router`, `bridge.py`) ya lo usan. Mantener la opción original habría duplicado la lógica.

**Implicación:** `control_shadow.py` debe importar `from api_state import resolve_state_root` y usar `state_root = resolve_state_root(self)` o pasarlo al constructor. **Esto NO requiere un módulo nuevo.**

### D4 — ¿Schemas en `backend/.bago/contracts/pi/` o `backend/docs/contracts/pi/`?

**Opciones:**
- (a) `backend/.bago/contracts/pi/`
- (b) `backend/docs/contracts/pi/`

**Análisis técnico (verificado):**

Convención BAGO existente — `backend/docs/contracts/` contiene 8 contratos canónicos:
- `bago_v4_engineering_contract.md`
- `bago_v4_evidence_contract.md`
- `bago_v4_governance_contract.md`
- `bago_v4_knowledge_contract.md`
- `bago_v4_repl_contract.md`
- `bago_v4_runtime_contract.json`
- `resolver_contract.json`

**No existe** `backend/.bago/contracts/` (verificado). El ARQ proponía crear un directorio nuevo siguiendo el patrón de `backend/.bago/integrations/pi/`, pero **rompe la convención canónica**.

**Decisión CRIT:** **D4 = opción (b) — `backend/docs/contracts/pi/`**. Razón: coherencia con la convención existente; los 8 contratos canónicos ya viven ahí; los nuevos schemas son documentación contractual del bridge, igual que `bago_v4_runtime_contract.json` es documentación contractual del runtime BAGO.

**Implicación:** crear `backend/docs/contracts/pi/` con 8 sub-schemas. El subdirectorio `pi/` es la unidad de organización que agrupa los contratos del bridge, paralelo a cómo `workspace_seed_contract/` agrupa los suyos.

### D5 — ¿Tarjeta "Bridge PI" siempre o condicional?

**Opciones:**
- (a) Siempre visible
- (b) Solo cuando `state != "disabled"`

**Análisis técnico:**

- **Operatividad:** Un operador debe poder confirmar que el bridge está desactivado. Si la tarjeta está oculta cuando `disabled`, debe abrir DevTools o leer logs para verificar.
- **Consistencia:** Las demás tarjetas de `SystemSurface` (Runtime, Memory, etc.) se muestran siempre, independientemente de su estado.
- **Costo:** 1 componente siempre visible = ~3 KB CSS + ~0.5 KB JS. Despreciable.

**Decisión CRIT:** **D5 = opción (a) — siempre visible**. Razón: consistencia con el resto de `SystemSurface`; permite confirmar el estado `disabled` sin herramientas externas; el costo de UI es trivial.

**Implicación:** la tarjeta siempre se renderiza. Cuando `state == "disabled"`, muestra una variante atenuada con copy "Integración PI: deshabilitada por configuración (cuarentena)".

---

## 4. Veredicto CRIT

### 4.1 Por brecha

| # | Brecha | Severidad CRIT | Estado |
| --- | --- | --- | --- |
| 1 | Falta `requested_adapter/runtime` en `BridgeExecutionRequest` | BLOQUEANTE | APROBADO |
| 2 | Falta `effective_adapter/runtime` en `ProviderAttestation` | BLOQUEANTE | APROBADO |
| 3 | `bridge.py` real NO invoca `BagoPiProviderAdapter` | BLOQUEANTE (con D1) | APROBADO pendiente D1 |
| 4 | `ControlShadow` en `base_path/.bago` | MAYOR | APROBADO (D3 reinterpretada) |
| 5 | No existe `contracts/pi/` con 8 JSON Schemas | MAYOR (4 críticos, 4 deseables) | APROBADO con priorización |
| 6 | UI no contempla `bridge_state` | MENOR | APROBADO |
| 7 | Sidecar mock (sin `pi-ai` real) | INFO | CONFIRMADO sin acción |
| 8 | Lockfile e integridad no registrados | MAYOR (acoplado a #7) | APROBADO |
| 9 | UI no muestra "Bridge PI" en SystemSurface | MENOR (acoplado a #6) | APROBADO |
| 10 | Sin `test_v03_arq_separation.py` con 14 pruebas | BLOQUEANTE (con cobertura parcial) | APROBADO con auditoría previa |

### 4.2 Por decisión

| D | Pregunta | Decisión CRIT | Razón |
| --- | --- | --- | --- |
| D1 | ¿Cómo invocar el adapter? | (b) Dispatch table `(provider, adapter) → class` | `ADAPTER_REGISTRY` indexa por provider; meter `pi-ai` ahí rompería la semántica "provider ≠ pi". |
| D2 | ¿Cuádruplo: 4 campos o struct? | (a) 4 campos separados | Backward compat con 228 tests; claridad operativa. |
| D3 | ¿state_root: request_context o state_paths? | (a) reinterpretada — `resolve_state_root()` de `api_state.py` | Ya existe el módulo canónico; duplicar sería regresión. |
| D4 | ¿Schemas: `.bago/contracts` o `docs/contracts`? | (b) `backend/docs/contracts/pi/` | Coherencia con la convención canónica de 8 contratos. |
| D5 | ¿Tarjeta UI: siempre o condicional? | (a) Siempre visible | Consistencia con el resto de `SystemSurface`; permite confirmar `disabled`. |

### 4.3 Veredicto global

**CRIT veredicto:** **GO CONDICIONADO** con 3 condiciones explícitas.

**Las 3 condiciones son:**

1. **D1 resuelta antes de implementar la brecha #3.** El dispatch table `(provider, adapter) → class` debe existir antes de que `bridge.py` pueda invocar `BagoPiProviderAdapter` en la ruta real. Sin D1, la invocación sería un hack.

2. **Auditoría de las 14 pruebas obligatorias antes de crear `test_v03_arq_separation.py`.** Varios tests ya existen dispersos. El nuevo archivo debe **consolidar referencias** a tests existentes, no duplicarlos. Solo crear tests nuevos para los gaps reales.

3. **D3 ejecutada como fix prioritario de la brecha #4.** Es la única acción que corrige una desviación de canon (escribir estado interno en el proyecto del usuario). Esta puede implementarse en paralelo al resto.

**Cierre CRIT:**

- ✅ Las 10 brechas son **accionables** y **alineadas con la separación de autoridad**.
- ✅ Las 5 decisiones tienen **razón técnica verificable** en el código actual.
- ⚠️ La promoción a `enabled=true` sigue **bloqueada** hasta que el smoke test atraviese `bridge.py` real con `BagoPiProviderAdapter` invocado vía el dispatch table de D1.
- ⚠️ El sidecar mock **no es suficiente** como evidencia de Fase 1 GO. El canary con `pi-ai@0.80.7` real debe ejecutarse antes de promover.

**Pendiente para PLAN v0.3:**

- Implementar las 10 brechas en el orden de las 3 condiciones.
- 4 JSON Schemas críticos antes de Fase 1 GO (`bridge_handshake`, `bridge_request`, `provider_attestation`, `policy_manifest`).
- 4 JSON Schemas deseables en v0.4 (event, tool, receipt, context_receipt).
- Tarjeta "Bridge PI" en `SystemSurface` (D5 = siempre visible).
- 14 pruebas: consolidar existentes + cubrir gaps.

**HOLD OPERATIVO preservado** — el bridge NO se promueve a `enabled=true` en producción.

**Próximo paso:** PLAN v0.3 con cronograma de implementación, basado en este CRIT.
