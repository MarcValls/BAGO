# Tools Reference — BAGO v2.5-stable

> **Total tools:** 126 en `.bago/tools/`
> **Guardian health:** 0% (CHG-002 pendiente)
> **Última actualización:** 2026-05-04

---

## Índice de categorías

| Categoría | Tools principales | Propósito |
|-----------|------------------|-----------|
| [Diagnóstico](#diagnóstico) | `audit_v2`, `health_score`, `doctor`, `stale_detector` | Estado del pack |
| [Calidad de código](#calidad-de-código) | `lint_runner`, `code_quality_orchestrator`, `sincerity_detector` | Análisis |
| [Generativo](#generativo) | `emit_ideas`, `cosecha`, `ideas_selector` | Generación |
| [Reporting](#reporting) | `pack_dashboard`, `health_report`, `chronicle_reporter` | Reportes |
| [Git/CI](#gitci) | `git_context`, `ci_generator`, `commit_readiness` | Integración |
| [Workflows](#workflows) | `workflow_selector`, `intent_router`, `launch_workflow_maestro` | Gestión |
| [Sesiones](#sesiones) | `session_logger`, `session_opener`, `search_history` | Sesiones |
| [Seguridad](#seguridad) | `security_audit`, `sincerity_detector` | Auditoría |
| [Imagen](#imagen) | `image_gen` | Generación de imágenes |
| [Entorno](#entorno) | `env_manager`, `deps_check`, `env_setup` | Entorno |
| [Contratos](#contratos) | `contracts` | Contratos BAGO |

---

## Diagnóstico

### `audit_v2.py`
**Propósito:** Auditoría integral del pack  
**Tipo:** diagnostic  
**Uso:**
```bash
python3 .bago/tools/audit_v2.py
python3 .bago/tools/audit_v2.py --full
```
**Produce:** sync + validate + health + vértice + workflow report  
**Estado CHG-002:** ⚠️ --test pendiente

---

### `health_score.py`
**Propósito:** Puntuación de salud del pack (0-100)  
**Tipo:** diagnostic  
**Uso:**
```bash
python3 .bago/tools/health_score.py
python3 .bago/tools/health_score.py --verbose
```
**Output:** Score numérico + breakdown por categoría  
**Estado CHG-002:** ⚠️ --test pendiente

---

### `doctor.py`
**Propósito:** Diagnóstico general con opción de autofix  
**Tipo:** diagnostic  
**Uso:**
```bash
python3 .bago/tools/doctor.py           # diagnóstico
python3 .bago/tools/doctor.py --fix     # autofix safe
python3 .bago/tools/doctor.py --report  # informe detallado
```
**Estado CHG-002:** ⚠️ --test pendiente

---

### `stale_detector.py`
**Propósito:** Detecta archivos y referencias obsoletas  
**Tipo:** diagnostic  
**Uso:**
```bash
python3 .bago/tools/stale_detector.py
python3 .bago/tools/stale_detector.py --threshold 30  # días
```
**Output:** Lista de archivos stale con antigüedad

---

### `tool_guardian.py`
**Propósito:** Verifica que todos los tools tienen --test, routing, docstring  
**Tipo:** diagnostic  
**Estado actual:** Detecta por grep (TRAMPA #3) — CHG-003 pendiente  
**Uso:**
```bash
python3 .bago/tools/tool_guardian.py
python3 .bago/tools/tool_guardian.py --tool sincerity_detector.py
```
**Output conocido:**
```
guardian_health: 0%
E001 (no --test): 33 tools
E002 (not registered): 29 tools
W001 (no routing): 18 tools
W002 (no docstring): 2 tools
```

---

### `stability_summary.py`
**Propósito:** Resumen de estabilidad del pack  
**Tipo:** reporting  
**Uso:**
```bash
python3 .bago/tools/stability_summary.py
```

---

### `context_detector.py`
**Propósito:** Detecta el contexto del repositorio activo  
**Tipo:** diagnostic  
**Alias CLI:** `bago detector`

---

### `context_map.py`
**Propósito:** Mapa de contexto del repositorio  
**Tipo:** diagnostic  
**Alias CLI:** `bago map`

---

## Calidad de código

### `sincerity_detector.py` ⭐ ALTA UTILIDAD
**Propósito:** Centinela contra trampa semántica y sycophancy  
**Tipo:** diagnostic (reads_only)  
**Alias CLI:** `bago sincerity`  
**Uso:**
```bash
python3 .bago/tools/sincerity_detector.py --target docs/
python3 .bago/tools/sincerity_detector.py --file .bago/state/ESTADO_BAGO_ACTUAL.md
python3 .bago/tools/sincerity_detector.py --all  # todos los .md del pack
```
**Detecta:**
- "ALL PASS" sin evidencia
- Badges sin provenance
- Afirmaciones sin fuente
- Lenguaje hedging excesivo

---

### `lint_runner.py`
**Propósito:** Runner unificado de linters  
**Tipo:** diagnostic  
**Alias CLI:** `bago lint`  
**Uso:**
```bash
python3 .bago/tools/lint_runner.py
python3 .bago/tools/lint_runner.py --lang python
python3 .bago/tools/lint_runner.py --lang typescript
```

---

### `code_quality_orchestrator.py`
**Propósito:** Orquesta todos los análisis de calidad  
**Tipo:** diagnostic  
**Uso:**
```bash
python3 .bago/tools/code_quality_orchestrator.py
python3 .bago/tools/code_quality_orchestrator.py --report
```

---

### `naming_check.py`
**Propósito:** Lint de convenciones de nombres  
**Tipo:** diagnostic (reads_only)  
**Alias CLI:** `bago naming`  
**Uso:**
```bash
python3 .bago/tools/naming_check.py --target src/
```

---

### `type_check.py`
**Propósito:** Chequeo de tipos estáticos  
**Tipo:** diagnostic (reads_only)  
**Alias CLI:** `bago types`

---

### `dead_code.py`
**Propósito:** Detecta código muerto/no referenciado  
**Alias CLI:** `bago dead-code`

---

### `complexity.py`
**Propósito:** Análisis de complejidad ciclomática  
**Alias CLI:** `bago complexity`

---

### `duplicate_check.py`
**Propósito:** Detecta código duplicado  
**Alias CLI:** `bago duplicate-check`

---

## Generativo

### `cosecha.py` ⭐ ALTA UTILIDAD
**Propósito:** Recolección y síntesis de aprendizajes de sesión  
**Tipo:** generative  
**Alias CLI:** `bago cosecha`  
**Uso:**
```bash
python3 .bago/tools/cosecha.py
python3 .bago/tools/cosecha.py --session ultima
python3 .bago/tools/cosecha.py --output docs/harvest_2026-05.md
```
**⚠️ CHG-002:** Una de las 5 prioritarias sin --test real

---

### `emit_ideas.py` ⭐ ALTA UTILIDAD
**Propósito:** Generación de nuevas ideas para el proyecto activo  
**Tipo:** reporting  
**Alias CLI:** `bago ideas`  
**Uso:**
```bash
python3 .bago/tools/emit_ideas.py
python3 .bago/tools/emit_ideas.py --domain "imagen_generacion"
python3 .bago/tools/emit_ideas.py --count 5
```

---

### `ideas_selector.py`
**Propósito:** Selección y priorización de ideas generadas  
**Tipo:** interactive  
**Uso:**
```bash
python3 .bago/tools/ideas_selector.py --from docs/ideas.md
```

---

### `ci_generator.py`
**Propósito:** Genera pipelines CI/CD para el proyecto  
**Tipo:** generative  
**Alias CLI:** `bago ci-baseline`  
**Uso:**
```bash
python3 .bago/tools/ci_generator.py --platform github-actions
python3 .bago/tools/ci_generator.py --platform gitlab-ci
```

---

### `auto_register.py`
**Propósito:** Registra automáticamente nuevos tools en el pack  
**Tipo:** generative  
**Uso:**
```bash
python3 .bago/tools/auto_register.py --tool tools/mi_nuevo_tool.py
```

---

## Reporting

### `pack_dashboard.py`
**Propósito:** Dashboard visual del pack  
**Tipo:** reporting  
**Alias CLI:** `bago dashboard`  
**Uso:**
```bash
python3 .bago/tools/pack_dashboard.py
```

---

### `health_report.py`
**Propósito:** Health report completo en Markdown  
**Tipo:** reporting  
**Alias CLI:** `bago report`  
**Uso:**
```bash
python3 .bago/tools/health_report.py
python3 .bago/tools/health_report.py --output docs/health_2026-05.md
```

---

### `chronicle_reporter.py`
**Propósito:** Reporte cronológico de actividad  
**Tipo:** reporting  
**Alias CLI:** `bago timeline`

---

### `efficiency_meter.py`
**Propósito:** Métricas de eficiencia de la sesión  
**Tipo:** reporting  
**Alias CLI:** `bago efficiency`

---

## Git/CI

### `git_context.py`
**Propósito:** Contexto git (log/diff/brief) para workflows  
**Tipo:** diagnostic (reads_only)  
**Alias CLI:** `bago git`  
**Uso:**
```bash
python3 .bago/tools/git_context.py --brief
python3 .bago/tools/git_context.py --diff HEAD~3
python3 .bago/tools/git_context.py --log 10
```

---

### `commit_readiness.py`
**Propósito:** Evaluación de preparación para commit  
**Tipo:** diagnostic (reads_only)  
**Alias CLI:** `bago commit`  
**Uso:**
```bash
python3 .bago/tools/commit_readiness.py
# Output: GO / WARN / FAIL con checklist
```

---

### `pre_commit_gen.py`
**Propósito:** Genera hooks pre-commit  
**Alias CLI:** `bago pre-commit-gen`

---

### `branch_check.py`
**Propósito:** Verifica estado y naming de branches  
**Alias CLI:** `bago branch-check`

---

## Workflows

### `workflow_selector.py`
**Propósito:** Selector interactivo de workflow BAGO  
**Tipo:** interactive  
**Alias CLI:** `bago workflow`  
**Uso:**
```bash
python3 .bago/tools/workflow_selector.py
python3 .bago/tools/workflow_selector.py --workflow validacion
python3 .bago/tools/workflow_selector.py --list
```

---

### `intent_router.py`
**Propósito:** Router lenguaje natural → tools BAGO  
**Tipo:** interactive  
**Alias CLI:** `bago ask`  
**⚠️ Dead ref:** Referencia `legacy-fix` que no existe  
**Uso:**
```bash
python3 .bago/tools/intent_router.py "necesito auditar el pack"
python3 .bago/tools/intent_router.py "generar ideas para BIANCA"
```

---

### `flow.py`
**Propósito:** Lista workflows BAGO disponibles  
**Tipo:** reporting (reads_only)  
**Alias CLI:** `bago flow`

---

## Sesiones

### `session_preflight.py` ⭐ ALTA UTILIDAD
**Propósito:** Preflight ESCENARIO-001 antes de sesión W7  
**Tipo:** verification  
**Uso OBLIGATORIO en sesiones productivas:**
```bash
python3 .bago/tools/session_preflight.py \
  --objetivo "Implementar image gen pipeline para BIANCA sprites [done]" \
  --roles "MAESTRO_BAGO,role_generativo" \
  --artefactos "knowledge/image_generation_guide.md,scripts/generate_sprite.py" \
  --task-type system_change
# Output: GO → abrir sesión / KO → corregir y repetir
```

---

### `session_logger.py`
**Propósito:** Registro automático de sesión  
**Tipo:** generative  
**Alias CLI:** `bago session`

---

### `session_opener.py`
**Propósito:** Abre y configura nueva sesión BAGO  
**Tipo:** interactive

---

### `search_history.py`
**Propósito:** Búsqueda en historial de sesiones  
**Alias CLI:** `bago search`

---

## Seguridad

### `security_audit.py`
**Propósito:** Auditoría de seguridad del código  
**Alias CLI:** `bago scan`

---

### `secret_scan.py`
**Propósito:** Detecta secrets/credentials hardcodeados  
**Alias CLI:** `bago secret-scan`

---

### `permission_check.py`
**Propósito:** Verifica permisos de archivos  
**Alias CLI:** `bago permission-check`

---

## Imagen

### `image_gen.py`
**Propósito:** Generación de imágenes T2I (wrapper multi-método)  
**Tipo:** generative  
**Alias CLI:** `bago image` (pendiente registro)  
**Uso:**
```bash
python3 .bago/tools/image_gen.py --method codex --prompt "anime sprite BIANCA"
python3 .bago/tools/image_gen.py --method hf-space --prompt "..."
python3 .bago/tools/image_gen.py --list-methods
```
**Ver:** `knowledge/image_generation_guide.md` para detalles completos

---

## Entorno

### `env_manager.py`
**Propósito:** Gestión de variables de entorno del proyecto  
**Alias CLI:** `bago config`

---

### `deps_check.py`
**Propósito:** Verifica dependencias instaladas  
**Alias CLI:** `bago install-deps`

---

### `env_setup.py`
**Propósito:** Setup inicial de entorno  
**Alias CLI:** `bago env-check`

---

### `dep_audit.py`
**Propósito:** Auditoría de dependencias del proyecto  
**Tipo:** diagnostic (reads_only)  
**Alias CLI:** `bago deps`

---

## Contratos

### `contracts.py`
**Propósito:** Contratos BAGO con estados (ACTIVE/EXPIRED)  
**Tipo:** verification  
**⚠️ TRAMPA #5:** Falta estado BREACHING — CHG-004 pendiente  
**Uso:**
```bash
python3 .bago/tools/contracts.py --list
python3 .bago/tools/contracts.py --status CHG-002
python3 .bago/tools/contracts.py --check-all
```

---

## Orquestación

### `cabinet_orchestrator.py` ⭐ ALTA UTILIDAD
**Propósito:** Orquesta el gabinete de agentes BAGO y emite informe unificado  
**Tipo:** orchestration  
**Alias CLI:** `bago cabinet`  
**Uso:**
```bash
python3 .bago/tools/cabinet_orchestrator.py
python3 .bago/tools/cabinet_orchestrator.py --agents "bago-tester,bago-organizativo"
python3 .bago/tools/cabinet_orchestrator.py --report
```

---

## Validación

### `validate_manifest.py` ⚠️ CHG-002 PRIORITARIO
**Propósito:** Valida integridad del tools.manifest.json  
**Reads only:** true  
**Alias CLI:** `bago validate manifest`

---

### `validate_state.py` ⚠️ CHG-002 PRIORITARIO
**Propósito:** Valida integridad de global_state.json  
**Reads only:** true

---

### `validate_pack.py` ⚠️ CHG-002 PRIORITARIO
**Propósito:** Verifica integridad completa del pack  
**Alias CLI:** `bago validate`  
**Uso:**
```bash
python3 .bago/tools/validate_pack.py          # validación completa
python3 .bago/tools/validate_pack.py --quick  # solo críticos
```

---

### `check_validate_purity.py`
**Propósito:** Static purity check — verifica que validate_* no escriben  
**Tipo:** verification (reads_only)  
**Alias CLI:** `bago check`

---

## Otros tools destacados

### `show_task.py` ⚠️ CHG-002 PRIORITARIO
**Propósito:** Muestra y gestiona tareas activas  
**Alias CLI:** `bago task`  
**Uso:**
```bash
python3 .bago/tools/show_task.py              # tarea activa
python3 .bago/tools/show_task.py --done       # cerrar sesión/tarea
python3 .bago/tools/show_task.py --list       # todas las tareas
```

---

### `sync_pack_metadata.py`
**Propósito:** Sincroniza metadatos (genera TREE.txt y CHECKSUMS.sha256)  
**Alias CLI:** `bago sync` (via pack.json commands.sync)

---

### `tool_search.py`
**Propósito:** Busca la herramienta BAGO adecuada para un problema  
**Alias CLI:** `bago find-tool`  
**Uso:**
```bash
python3 .bago/tools/tool_search.py "necesito validar el corpus"
python3 .bago/tools/tool_search.py "detectar código duplicado"
```

---

### `rule_catalog.py`
**Propósito:** Catálogo completo de reglas BAGO  
**Alias CLI:** `bago rules`

---

## CHG-002 — Pendiente urgente

**Descripción:** Añadir `--test` con asserts funcionales reales a los 33 tools sin él.

**5 prioritarios (empezar aquí):**

| Tool | Por qué es crítico |
|------|--------------------|
| `validate_manifest.py` | SoT del inventario — debe testear que detecta manifests rotos |
| `validate_state.py` | Validación del estado global — debe testear estados corruptos |
| `validate_pack.py` | Validación del pack — debe testear packs incompletos |
| `show_task.py` | Gestión de tareas — debe testear creación/cierre de tarea |
| `cosecha.py` | Cosecha de aprendizajes — debe testear que produce output válido |

**Template --test correcto:**
```python
if args.test:
    import json
    result = run_with_test_fixtures()
    report = {
        "tool": "nombre_tool",
        "status": "ok" if result.ok else "fail",
        "checks": [
            {"name": "can_read_input", "pass": result.can_read},
            {"name": "produces_output", "pass": result.output is not None},
            {"name": "output_valid_schema", "pass": result.schema_valid},
        ]
    }
    print(json.dumps(report, indent=2))
    sys.exit(0 if result.ok else 1)
```

---

*Referencia generada por BAGO MAESTRO · 2026-05-04*
*Framework: BAGO v2.5-stable · Tools totales: 126*
