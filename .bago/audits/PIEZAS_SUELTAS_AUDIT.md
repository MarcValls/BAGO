# Auditoría de piezas sueltas y enrutamiento — BAGO

Fecha: generado por agente `.bago` sobre `/Volumes/bago_core`.
Objetivo: identificar qué piezas conservar, pulir, fusionar o eliminar, y corregir su enrutamiento real frente al manifiesto.

---

## 1. Scripts `_*` en la raíz (parches de un solo uso a `bago.ps1`)

| Archivo | Tipo | Refs core | Veredicto |
|---|---|---|---|
| `_add_findgh.py` | parche Python que muta `bago.ps1` (inserta `Find-Gh`) | 0 | **ELIMINAR** |
| `_add_pipeline.py` | parche que inserta `Invoke-BagoPipeline` | 0 | **ELIMINAR** |
| `_final_pipeline.py` | reescritura final del pipeline | 0 | **ELIMINAR** |
| `_fix_timeout.py` | hot-patch de `WaitForExit` | 0 | **ELIMINAR** |
| `_rebuild_pipeline.py` | reconstrucción del bloque pipeline | 0 | **ELIMINAR** |
| `_rebuild_pipeline2.py` | segunda reconstrucción | 0 | **ELIMINAR** |
| `_test_job.ps1` | smoke test ad-hoc de `gh copilot` | 0 | **ELIMINAR** |

**Evidencia**: ninguno de los 7 está referenciado en `bago`, `bago.cmd`, `bago.ps1`, `Makefile`, ni `pyproject.toml`. Solo aparecen en `.bago/state/boot/boot_state.json` (estado histórico, no contrato). Su contenido ya está aplicado en `bago.ps1`.

**Acción**: mover a `archive/scratch_2024_pipeline_patches/` o borrar. Recomiendo **borrar** (git conserva historia).

---

## 2. Documentación `.bago/*.md` huérfana

| Archivo | Refs externas | Veredicto |
|---|---|---|
| `BAGO_TABLET_COMMAND.md` | 0 | **ELIMINAR** o mover a `archive/docs/` |
| `STRUCTURE_VERIFICATION.md` | 0 | **ELIMINAR** o mover a `archive/docs/` |
| `CLI_INDEX.md` | 1–2 | **ENRUTAR**: enlazarlo desde `.bago/README.md` o regenerarlo desde el dispatcher |
| `START_AGENT.md` | 1–2 | **ENRUTAR**: linkear desde `AGENT_START.md` (que tiene 23 refs) o fusionar |
| `README.md` | 62 | **CONSERVAR** (canónico) |
| `AGENT_START.md` | 23 | **CONSERVAR** (canónico) |
| `QUICKSTART.md` | 21 | **CONSERVAR** (canónico) |

---

## 3. Duplicidad real de herramientas (`.bago/tools/`)

Manifest reporta **170 tools**. Hay solapamiento serio en tres familias:

### Familia HEALTH

| Tool | Refs | Rol real |
|---|---|---|
| `health_score.py` | **35** | **Canónico** — métrica ponderada |
| `health_check.py` | 11 | Chequeo binario por dominio |
| `health_report.py` | 8 | Renderiza informe a partir de los anteriores |
| `bago_health_check.py` | 2 | Wrapper legacy |
| `bago_health_router.py` | ~ | Router delgado a `health.main` (~250 b) |

**Plan**:
- Mantener `health_score.py` (cálculo), `health_check.py` (chequeos), `health_report.py` (presentación) como **trio canónico**.
- Eliminar `bago_health_check.py` (2 refs, wrapper).
- Conservar `bago_health_router.py` solo si es el punto único que invoca `bago health`. Si no, eliminar.

### Familia DOCTOR / CONSISTENCY

| Tool | Refs | Rol |
|---|---|---|
| `doctor.py` | **28** | **Canónico** — el dispatcher `bago` lo invoca |
| `bago_doctor.py` | 4 | Wrapper |
| `bago_consistency_check.py` | 5 | Chequeo de consistencia (función propia) |

**Plan**:
- Conservar `doctor.py` y `bago_consistency_check.py` (cumplen funciones distintas).
- **Eliminar** `bago_doctor.py` y actualizar manifest.

### Familia ORCHESTRATOR

| Tool | Refs | Rol |
|---|---|---|
| `orchestrator.py` | **27** | Canónico general |
| `bago_orchestrator.py` | 5 | Variante usada por `bago.ps1` |
| `cabinet_orchestrator.py` | usado por `bago cabinet` | Especializado |
| `research_orchestrator.py` | usado por workflow research | Especializado |
| `code_quality_orchestrator.py` | usado por workflow QA | Especializado |

**Plan**:
- Conservar los 3 especializados (`cabinet`, `research`, `code_quality`) — son W-específicos.
- Decidir entre `orchestrator.py` vs `bago_orchestrator.py`: el primero gana en refs (27 vs 5). Hacer que `bago.ps1` apunte también a `orchestrator.py` y **eliminar** `bago_orchestrator.py`.

### Familia AUDIT

Existen al menos `audit_v2.py` (canónico, invocado por `bago audit`), `bago_audit_router.py`, `audit_state_pointers.py` (3 refs, función específica: validar punteros de estado), `bago_learning_audit.py` (nuevo, project-traceability).

**Plan**:
- `audit_v2.py` ✅ canónico.
- `audit_state_pointers.py` ✅ conservar (rol propio).
- `bago_learning_audit.py` ✅ conservar (nuevo, registrar en manifest).
- `bago_audit_router.py` ✅ conservar si es el único enrutador.
- `spanish_audit.py`, `security_audit.py`: revisar individualmente (no eran candidatos a duplicidad directa).

### Familia RECIENTES

- `recientes_aggregator.py` (3 refs) y `recientes_cli.py` (2 refs) son complementarios (agregador + CLI). **Conservar ambos**.
- `recent_projects.py`: validar si solapa con aggregator. Si solapa, fusionar.

---

## 4. Routers delgados (~250 b)

`bago_health_router.py`, `bago_audit_router.py`, `bago_session_router.py` son wrappers de `import; main()`. **Conservarlos solo si el dispatcher `bago` los invoca como punto único**. Caso contrario son indirección innecesaria.

**Acción**: verificar en `bago` (shell) cada `case`/`elif cmd ==`: si invoca directamente al tool real, los routers son muertos → eliminar y limpiar manifest.

---

## 5. Enrutamiento real del dispatcher `bago`

Mapeos confirmados:

| Comando | Tool invocada |
|---|---|
| `bago health` | `health_score.py` |
| `bago audit` | `audit_v2.py` |
| `bago cabinet` | `cabinet_orchestrator.py` |
| `bago doctor` | `doctor.py` |
| `bago project init` | `project_init.py` |

**Brecha detectada**: `bago.ps1` apunta a `bago_orchestrator.py` mientras el dispatcher Unix usa `orchestrator.py`. Esto rompe paridad cross-platform.

**Fix**: unificar ambos dispatchers para apuntar a `orchestrator.py` y borrar la variante.

---

## 6. `bago_core/cli.py` — entrypoint Python

Usa `importlib.machinery.SourceFileLoader` para cargar el launcher `bago` (sin extensión). Correcto y necesario porque `bago` no es módulo Python regular. **Conservar tal cual**.

---

## 7. Plan de ejecución (en orden)

1. **Borrar** los 7 scripts `_*` de la raíz.
2. **Borrar** o archivar `BAGO_TABLET_COMMAND.md` y `STRUCTURE_VERIFICATION.md`.
3. **Borrar** `bago_health_check.py` y `bago_doctor.py` (wrappers obsoletos).
4. **Unificar orchestrator**: cambiar `bago.ps1` para invocar `orchestrator.py`; eliminar `bago_orchestrator.py`.
5. **Auditar routers delgados**: si `bago` invoca al tool real directamente, eliminar el router correspondiente.
6. **Regenerar manifest** (`.bago/tools.manifest.json`) tras los borrados — descontar entries muertos, añadir `bago_learning_audit.py`.
7. **Linkear** `CLI_INDEX.md` y `START_AGENT.md` desde `README.md` / `AGENT_START.md` o fusionar.
8. **Commit** en español con trailer `Co-authored-by: Copilot`, mensaje:
   `chore(piezas): elimina parches one-shot, fusiona orchestrator y limpia wrappers`.

---

## 8. Lo que NO se toca

- `health_score.py`, `health_check.py`, `health_report.py`, `doctor.py`, `audit_v2.py`, `orchestrator.py` (canónicos).
- `project_init.py`, `project_summary.py`, `project_memory.py` (núcleo de project-scoping).
- `recientes_aggregator.py`, `recientes_cli.py`, `audit_state_pointers.py`, `bago_consistency_check.py`, `bago_learning_audit.py` (función propia).
- `README.md`, `AGENT_START.md`, `QUICKSTART.md`, `BOOTSTRAP.md`.
- `bago_core/cli.py` (entrypoint válido).

---

## 9. Riesgo y reversibilidad

Todos los borrados son recuperables vía git. No se toca `.bago/state/*.json` a mano. El paso 4 (unificar orchestrator) requiere prueba: ejecutar `bago auto --dry-run` (o equivalente PS) tras el cambio.

**Confirmación requerida del usuario** antes de ejecutar pasos 1–7 (operaciones irreversibles fuera de git).
