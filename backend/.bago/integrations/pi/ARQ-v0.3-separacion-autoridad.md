# BagoPiBridge — ARQ v0.3 · Separación de autoridad BAGO↔PI

**Estado:** BORRADOR para revisión CRIT
**Fecha:** 2026-07-16
**Relacionado:** v0.1 (DRAFT/QUARANTINE), v0.2 (GO CONDICIONADO con HOLD OPERATIVO)
**Fase actual:** 0 (handshake sin modelo) — sidecar mock local

---

## 1. Premisa arquitectónica

```
BAGO ordena y valida → PI ejecuta una capacidad acotada → BAGO comprueba y certifica.
```

PI no es autoridad de sesión, workspace, permisos, herramientas, credenciales, estado de interfaz ni evidencia. PI es un **adaptador técnico subordinado**.

| Pieza PI            | Uso en BAGO                                       | Estado            |
| ------------------- | ------------------------------------------------- | ----------------- |
| `pi-ai`             | Catálogo modelos, streaming, uso y coste          | GO Fase 1         |
| `pi-agent-core`     | Bucle agéntico, hooks beforeToolCall/afterToolCall | GO condicionado   |
| `pi-coding-agent`   | Solo laboratorio RPC o pruebas de integración     | HOLD operativo    |
| `pi-tui`            | Ideas o componentes para la terminal BAGO         | Opcional          |
| `pi-orchestrator`   | Ninguno; PI lo declara experimental e inestable   | NO GO             |
| Skills/extensiones  | Importación tras normalización, firma y policy    | Bloqueado         |
| Sesiones `.pi`      | Ninguno                                           | Prohibido         |

PI confirma que su "Project Trust" solo controla la **carga inicial** de recursos: **no es sandbox** y no limita posteriormente lo que las herramientas pueden hacer. Sus herramientas y extensiones heredan los permisos completos del proceso. → **La frontera de seguridad es BAGO, no PI.**

---

## 2. Estado actual del repositorio (verificado 2026-07-16)

### 2.1 Lo que YA existe ✅

| Componente | Ubicación | Estado |
| --- | --- | --- |
| `BagoPiProviderAdapter` (virtual subclass del canónico) | `backend/.bago/integrations/pi/provider_adapter.py` | ✅ Cerrado v0.2 (B1) |
| `ProviderAttestation` con `requested_/effective_provider` y `requested_/effective_model` | `backend/.bago/integrations/pi/contracts.py:362` | ✅ 10 campos |
| `BridgeExecutionRequest` con `requested_provider/model` | `backend/.bago/integrations/pi/contracts.py:216` | ✅ |
| `WALStore` con fsync por evento | `backend/.bago/integrations/pi/wal.py` (A2 v0.2) | ✅ |
| Config cuarentena con 13 flags `allow_*` | `backend/.bago/integrations/pi/config.py` | ✅ |
| Sidecar mock local (5 archivos JS, 0 deps) | `backend/.bago/integrations/pi/sidecar/src/*.js` | ✅ |
| `FORBIDDEN_PATH_NAMES` (`.pi`, `.agents`, `skills`, `extensions`, `.pi-skills`) | `backend/.bago/integrations/pi/sidecar/src/runtime_guard.js:14` | ✅ |
| `FORBIDDEN_MODULE_PREFIXES` (`@earendil-works/`, `pi-coding-agent`, `@mariozechner/`) | `backend/.bago/integrations/pi/sidecar/src/runtime_guard.js:23` | ✅ |
| `ToolReceipt` promovido a canónico | `backend/.bago/core/tool_receipt.py` (Sprint 4) | ✅ |
| `ContextReceipt` reusado, no duplicado | `backend/.bago/core/context_envelope.py` | ✅ |
| `abortcontroller` 60s en `ControlPlane` y AbortController en fetch | `frontend/src/app/ControlPlane.tsx` | ✅ (FIX UI v0.2.1) |
| DevTools auto-open (configurable por `BAGO_DEVTOOLS=0`) | `electron-viewer/main.cjs` | ✅ (FIX UI) |

### 2.2 Lo que FALTA ⚠️ (brechas del ARQ)

| # | Brecha | Severidad | Acción propuesta |
| --- | --- | --- | --- |
| 1 | `BridgeExecutionRequest` no transporta `adapter` ni `runtime` | **BLOQUEANTE** | Añadir `requested_adapter`, `requested_runtime` al dataclass. |
| 2 | `ProviderAttestation` no expone `effective_adapter` ni `effective_runtime` | **BLOQUEANTE** | Añadir 2 campos. El cuádruplo `requested_/effective_` × `{provider, model, adapter, runtime}` debe quedar completo. |
| 3 | `bridge.py` real NO invoca `BagoPiProviderAdapter` | **BLOQUEANTE** | El smoke test Fase 1 debe atravesar `bridge.py` → router → adapter. Hoy solo hay `_run_tests()` con `MockAdapter`. |
| 4 | `ControlShadow` escribe en `base_path/.bago/{state,logs}` en lugar de `state_root` o `.gabo` | **MAYOR** | Redirigir a `state_root` del backend (CANON). |
| 5 | `backend/.bago/contracts/pi/` con 8 JSON Schemas **no existe** | **MAYOR** | Crear: `bridge_handshake`, `bridge_request`, `bridge_event`, `policy_manifest`, `provider_attestation`, `tool_request`, `tool_receipt_payload`, `context_receipt_payload`. |
| 6 | `ui-react/src/contracts/backend.ts` no contempla campo `bridge_state` ni `active_bridges` | **MENOR** | Añadir tipos TypeScript que reflejen el estado del bridge (disabled, provider_only, readonly_tools, agent_capture). |
| 7 | Sidecar no carga `@earendil-works/pi-ai@0.80.7` (es mock) | **INFO** | Esperado. La promoción a runtime real ocurrirá tras canary v0.2.1 con ARQ+CRIT+PLAN. |
| 8 | `Lockfile e integridad` aún no registrados | **MAYOR** | Cuando se fije `pi-ai@0.80.7`, generar `package-lock.json` con `npm ci --ignore-scripts`, calcular SHA-256 del lockfile y guardarlo en `expected_lockfile_hash` del policy. |
| 9 | UI no muestra "PI Manager" pero tampoco muestra el `bridge_state` en Sistema | **MENOR** | Añadir tarjeta "Bridge PI" en SystemSurface con `state`, `version`, `runtime`, `capabilities`. |
| 10 | Sin pruebas obligatorias de los 14 escenarios del ARQ §"Pruebas obligatorias" | **BLOQUEANTE** | Crear `test_v03_arq_separation.py` con 14 tests. |

---

## 3. Cambios arquitectónicos propuestos

### 3.1 Cuádruplo provider / adapter / runtime / model

Hoy `BridgeExecutionRequest` y `ProviderAttestation` solo manejan `(provider, model)`. El ARQ exige que sean **4 dimensiones independientes**:

```
provider  = anthropic | openai | openrouter | copilot | ollama-local | ...
adapter   = pi-ai    | bago-native | (futuro: litellm)
runtime   = node-sidecar | python-inproc | (futuro: wasm)
model     = claude-sonnet-4-5 | qwen2.5:1.5b | gpt-5 | ...
```

**Regla de invariante:** `provider` nunca puede ser igual a `"pi"`. PI es adaptador, no proveedor. `ContextReceipt.detect_drift()` debe comparar `requested_provider == effective_provider` y `requested_model == effective_model` antes de certificar.

#### Cambios concretos

**`backend/.bago/integrations/pi/contracts.py`:**

```python
# BridgeExecutionRequest
requested_provider: str    # anthropic
requested_adapter: str     # "pi-ai"
requested_runtime: str     # "node-sidecar"
requested_model: str       # claude-sonnet-4-5

# ProviderAttestation
requested_provider: str
effective_provider: str
requested_adapter: str
effective_adapter: str
requested_runtime: str
effective_runtime: str
requested_model: str
effective_model: str
```

### 3.2 `bridge.py` debe invocar `BagoPiProviderAdapter` en la ruta real

Hoy la única invocación al bridge es en `_run_tests()` con `MockAdapter`. La ruta real `POST /api/v1/chat` no consulta `integrations.pi.*`. Acción: el router de `/chat` debe:

1. Leer `config.integrations.pi.enabled` y `max_phase`.
2. Si `enabled=true` y `max_phase >= 1` y `requested_provider` está en la allowlist:
   - Resolver `BagoPiProviderAdapter` desde `integrations.pi.provider_adapter`.
   - Validar attestation (requested vs effective).
   - Emitir `ContextReceipt` con `adapter="pi-ai"`, `runtime="node-sidecar"`.
3. Si `enabled=false`: fallback al adapter nativo BAGO con `adapter="bago-native"`, `runtime="python-inproc"`.

### 3.3 Redirigir `ControlShadow` a `state_root`

`backend/.bago/api/control_shadow.py:32-33`:

```python
# Antes (incorrecto)
self.state_dir = self.base_path / ".bago" / "state"
self.logs_dir = self.base_path / ".bago" / "logs"

# Después (canónico)
self.state_dir = state_root / "ui_control_shadow"
self.logs_dir = state_root / "logs"
```

`state_root` se obtiene de `request_context` o de `backend/.bago/api/state_paths.py` (CANON). **Nunca** del `base_path` del proyecto del usuario.

### 3.4 Crear `backend/.bago/contracts/pi/` con 8 JSON Schemas

| Schema | Propósito |
| --- | --- |
| `bridge_handshake.schema.json` | Versión de PI, lockfile hash, sidecar hash, capacidades declaradas, mode (rpc/embedded/disabled). |
| `bridge_request.schema.json` | BridgeExecutionRequest serializado (cuádruplo provider/adapter/runtime/model). |
| `bridge_event.schema.json` | Eventos `agent_end`, `tool.request`, `provider.attestation`, `execution.done`. |
| `policy_manifest.schema.json` | 13 flags `allow_*` + `max_phase` + `network_mode` firmados. |
| `provider_attestation.schema.json` | Cuádruplo requested/effective + endpoint + version. |
| `tool_request.schema.json` | `tool.name`, `tool.args`, `tool.id`, `correlation_id`. |
| `tool_receipt_payload.schema.json` | `ToolReceipt` serializado con `outcome`, `duration_ms`, `output_digest`. |
| `context_receipt_payload.schema.json` | `ContextReceipt` con drift detection, scope validation, hash chain. |

Cada schema debe tener `version` propio y se versionan con semver.

### 3.5 UI: añadir tipos `bridge_state` y tarjeta "Bridge PI" en Sistema

`ui-react/src/contracts/backend.ts`:

```typescript
export type BridgeState = "disabled" | "provider_only" | "readonly_tools" | "agent_capture";
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

En `SystemSurface`, tarjeta "Bridge PI" muestra `state`, `version`, `runtime`, `capabilities`. **No botones para activar capacidades** — la UI solo consume estado.

---

## 4. Pruebas obligatorias (las 14)

Bloquean el paso de fase. `test_v03_arq_separation.py` con:

| # | Test | Verifica |
| --- | --- | --- |
| 1 | `test_read_outside_workspace_scope_root_blocked` | `read("/etc/passwd")` con `workspace_scope_root=/home/u/proj` → `ScopeViolation` |
| 2 | `test_write_in_phase_1_blocked` | Fase `max_phase=1`, intento `write()` → `ToolNotAllowed` |
| 3 | `test_bash_in_phase_1_3_blocked` | `bash` con `max_phase=3` → `ToolNotAllowed` |
| 4 | `test_dotpi_load_blocked` | Sidecar no monta `~/.pi/agent`; pathnames `.pi` en `FORBIDDEN_PATH_NAMES` |
| 5 | `test_skills_extensions_load_blocked` | `FORBIDDEN_MODULE_PREFIXES` contiene `@earendil-works/` y `pi-coding-agent` |
| 6 | `test_AGENTS_md_load_blocked` | Búsqueda de `AGENTS.md`/`CLAUDE.md` retorna vacío |
| 7 | `test_provider_drift_blocks_certification` | `requested=anthropic`, `effective=openai` → `ContextReceipt` con `verification_state=unverified` |
| 8 | `test_credential_outside_bago_rejected` | Inyección directa de `ANTHROPIC_API_KEY` por env → bridge rechaza |
| 9 | `test_tool_call_without_approval_rejected` | `beforeToolCall` sin approval → `ToolNotApproved` |
| 10 | `test_tool_result_without_receipt_rejected` | `execution.done` sin `ToolReceipt.id` → `BridgeError` |
| 11 | `test_agent_end_without_context_receipt_rejected` | Cierre de agente sin `ContextReceipt` → sesión no termina |
| 12 | `test_path_escape_blocked` | `read("../../etc/passwd")`, symlink a `/`, junction Windows, UNC `\\srv\share` → todos bloqueados |
| 13 | `test_sidecar_crash_keeps_session_intact` | Matar sidecar con SIGKILL → sesión BAGO no contaminada |
| 14 | `test_cross_session_contamination_zero` | 2 ejecuciones consecutivas con providers distintos → cero memoria cruzada |

Adicional: **secretos en logs** (test #15) — assert que ningún log contiene `sk-...`, `ghp_...`, `xoxb-...` ni patrones `Bearer `.

---

## 5. Versión y empaquetado (cuando se fije `pi-ai`)

```json
{
  "dependencies": {
    "@earendil-works/pi-ai": "0.80.7"
  }
}
```

- **Versión exacta**, no `^` ni `latest`.
- `npm ci --ignore-scripts` en CI.
- SHA-256 del `package-lock.json` calculado y guardado en `expected_lockfile_hash` del policy.
- SBOM y licencia MIT en `backend/.bago/integrations/pi/SBOM.json` y `LICENSE-PI.txt`.
- Upgrade de PI = migración contractual, no automática.

---

## 6. Primer objetivo operativo

**Ejecutar una llamada real mediante `pi-ai`, iniciada por una sesión BAGO, con `ContextEnvelope`, provider/modelo explícitos, cero herramientas, cero recursos PI, produciendo un `ContextReceipt` validado por BAGO.**

Hasta que ese smoke test atraviese `bridge.py` real y genere evidencia reproducible, el estado permanece:

| Fase | Estado |
| --- | --- |
| 0 — Handshake sin modelo | GO (mock local) |
| 1 — `pi-ai` provider-only | GO condicionado (Fase 1 requiere `bridge.py` real, breath #3) |
| 2 — Tools read-only | HOLD operativo |
| 3 — `pi-agent-core` efímero | HOLD operativo |
| 4 — Mutaciones | NO GO hasta OS sandbox + ChangeSet + rollback |
| `pi-coding-agent` operativo | NO GO |
| `pi-orchestrator` | NO GO |

---

## 7. Decisiones que requieren CRIT antes de implementación

| # | Decisión | Opciones |
| --- | --- | --- |
| D1 | ¿`BagoPiProviderAdapter` se inyecta en el router BAGO vía `ADAPTER_REGISTRY` (vía canónica) o se invoca directamente desde `bridge.py`? | (a) registry canónico / (b) invocación directa |
| D2 | ¿El cuádruplo `provider/adapter/runtime/model` se añade como 4 campos nuevos o se refactoriza a un struct `ProviderIdentity`? | (a) 4 campos / (b) struct anidado |
| D3 | ¿`state_root` de ControlShadow se lee de `request_context` o de un nuevo módulo `state_paths.py`? | (a) request_context / (b) state_paths.py |
| D4 | ¿Los 8 JSON Schemas viven en `backend/.bago/contracts/pi/` o en `backend/docs/contracts/pi/`? | (a) `.bago/contracts/` / (b) `docs/contracts/` |
| D5 | ¿Tarjeta "Bridge PI" en `SystemSurface` se renderiza siempre o solo cuando `state != "disabled"`? | (a) siempre / (b) condicional |

---

## 8. Riesgos abiertos

1. **Sidecar mock ≠ PI real**: las 14 pruebas pasan con el mock, pero al cargar `@earendil-works/pi-ai` real podrían aparecer diferencias. Plan: ejecutar las 14 pruebas **también** con PI real (canary v0.2.1+).
2. **`BagoCredentialStore`**: PI permite inyectar un `CredentialStore` propio, pero esto es opcional. Si el adapter BAGO no implementa la interfaz exacta de PI, la inyección falla y PI recurre a sus rutas por defecto. Acción: estudiar API exacta de `pi-ai` antes de implementar.
3. **Performance**: 4 `status()` por request BAGO (FIX UI v0.2.1) sigue costando 6s. La cache se invalidó mal. Acción: TTL explícito de 5s con invalidación en POST /project/sync.
4. **Memory card duplication**: el context bank del workspace `gestor-de-deudas-con` muestra 20 entradas con título idéntico ("BAGO v4 debe convertir...") y un clúster con título "directorio estable". Acción: deduplicar `seed.py` o normalizar títulos en backend.

---

## 9. Cierre ARQ

**Veredicto ARQ:** GO CONDICIONADO.

- Las 10 brechas identificadas son **accionables** y tienen plan de implementación.
- El sidecar mock cumple la cuarentena por construcción.
- El cuádruplo `provider/adapter/runtime/model` es un cambio **aditivo** sobre lo que ya existe.
- Las 14 pruebas obligatorias son la rampa de promoción de Fase 1 a Fase 2.
- El bridge NO se promueve a `enabled=true` hasta que el smoke test atraviese `bridge.py` real y las 14 pruebas pasen con PI real (no solo mock).

**Pendiente para CRIT:** aprobar D1-D5 antes de PLAN v0.3.
