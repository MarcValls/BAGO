# Arco de Abril 2026 — BAGO Knowledge

> **Período:** Abril 2026 (Apr 14 → Apr 24)
> **Framework:** BAGO v2.2.2 → v2.5-stable
> **Compilado:** 2026-05-04
> **Fuente:** Sesiones reales, auditorías, cosechas de sprint

---

## Resumen ejecutivo

Abril 2026 fue el mes de consolidación del framework BAGO. Se ejecutaron 6 proyectos en paralelo,
se evolucionó el framework de v2.2.2 a v2.5-stable en 10 días, se identificaron 13 trampas
estructurales y se iniciaron los fundamentos de BIANCA. Mes de alta densidad técnica.

---

## PROYECTO 1 — PANDAMIEN (Apr 14)

**Tipo:** Corpus de narrativa de horror psicológico
**Tool BAGO usada:** BAGO AMTEC V2.2.2

### Trabajo realizado
- Validación formal del corpus con `workflow_validacion` ejecutado sobre corpus completo
- P0 canon fix: edad y referencias hardcodeadas detectadas y corregidas
- `workflow_validacion` empleado como tool estándar para validar corpus documental

### Lecciones extraídas

> **LECCIÓN-001:** Datos canónicos NUNCA hardcodeados.

```
❌ MAL: "Tiene 17 años y vive en Madrid"
✅ BIEN: "Tiene {{chr_pandamien.age}} años y vive en {{chr_pandamien.city}}"
```

Datos canónicos siempre en `docs/characters.json` o `docs/canon_numbers.json`.
Si el dato aparece en más de un lugar hardcodeado → P0 inmediato.

> **LECCIÓN-002:** `workflow_validacion` como tool estándar para validar corpus documental.

No solo para código — aplica igualmente a documentos narrativos, biblias de personaje,
contratos de arte. Cualquier corpus con datos interrelacionados necesita validación formal.

---

## PROYECTO 2 — BAGO FRAMEWORK EVOLUTION (Apr 14–23)

**Evolución de versiones:**
```
V2.2.2 (Apr 14) → V2.3-clean (Apr 15) → V2.4-v2rc (Apr 18-19) → V2.5-stable (Apr 21-23)
```

### Hitos por versión

#### V2.2.2 → V2.3-clean (Apr 14-15)
- Limpieza de deuda técnica acumulada
- Separación de concerns en directorio `.bago/`
- Estandarización de entrypoints

#### V2.3-clean → V2.4-v2rc (Apr 15-19)
- `workflow_bootstrap_repo_first` implementado y probado
- Detección automática de prerequisites faltantes en `workflow-info`
- Session preflight ESCENARIO-001 (W7_FOCO_SESION obligatorio)
- `bago auto` con sincronización de contexto dinámico

#### V2.4-v2rc → V2.5-stable (Apr 21-23)
- 80+ comandos BAGO implementados
- `auto_register.py` para integración automática de tools
- `ci_generator.py` para generar pipelines CI/CD
- `sincerity_detector.py` — centinela contra trampa semántica
- `cabinet_orchestrator.py` — orquesta gabinete de agentes
- Tool guardian: detecta tools sin --test, sin routing, sin docstring

### Comandos BAGO implementados en Abril

```
bago audit, auto, chat, cosecha, dashboard, debug, detector, efficiency,
health, map, on, recolecta, repo-build, repo-debug, repo-lint, repo-on,
repo-test, stability, stale, task, v2, validate, workflow, workspace,
sprint, search, timeline, report, metrics, doctor, git, export, watch,
test, changelog, snapshot, diff, session-stats, compare, goals, lint,
summary, tags, flow, insights, config, check, archive, stats, remind,
habit, review, velocity, patch, notes, template, scan, bago-lint,
multi-scan, ast-scan, permission-check, install-deps, rule-catalog,
lint-report, config-check, ci-baseline, health-report, changelog-gen,
dead-code, branch-check, complexity, env-check, size-track, secret-scan,
test-gen, impact-map, hotspot, fix, gh, chart-engine, duplicate-check,
pre-commit-gen, metrics-export, code-review, refactor-suggest, api-check,
coverage-gate, naming-check, type-check, license-check, dep-audit,
readme-check, ci-report, tool-guardian, pre-push, tool-search, legacy-fix
```
*Total: 91 comandos*

### Deuda técnica identificada al cierre (Mayo)
- `guardian_health = 0%`
- 33 tools sin `--test` (BAGO-E001)
- 29 tools sin routing en CLI (BAGO-E002)
- CHG-002 pendiente

---

## PROYECTO 3 — TPV/CONTABILIDAD (Apr 16)

**Sistema:** TPV en `/Users/INTELIA_Manager/Documents/INTELIA_Manager_2026/Contabilidad/TPV_Contabilidad 2`
**Repo:** `MarcValls/INTELIA_Manager_TPV_V0.1.0`

### Trabajo realizado
- BAGO aplicado a proyecto de contabilidad por primera vez
- Validación de que el framework es transferible a proyectos no-narrativos
- Confirmación de que los workflows BAGO funcionan en dominio financiero/TPV

### Lección
> BAGO no es específico de proyectos creativos — aplica a cualquier proyecto técnico.

---

## PROYECTO 4 — TERROR/NIGHTFRAME (Apr 2026)

**Ubicación:** `/Volumes/Warehouse/AMTEC/2026/ABRIL2026/TERROR/nightframe_sim_ui`
**Stack:** Python Flask/Gradio

### Trabajo realizado
- `app.py` + `generate_sample.py` — UI de simulación
- Proyecto experimental: visualización de datos narrativos de horror
- Prueba de concepto: Gradio como frontend rápido para exploración de datos

### Lección
> Gradio/Flask son excelentes para UIs de exploración rápida en proyectos narrativos.
> No requieren infraestructura — ideal para prototipos de visualización.

---

## PROYECTO 5 — TEST_BAGO_03: IMAGE GENERATION PIPELINE (Apr 23-24)

**Objetivo:** Prueba sistemática de todos los métodos T2I disponibles en macOS M1
**Contexto:** Necesidad de sprites para BIANCA sin dependencia de API keys

### Trabajo realizado
- 9+ métodos testeados (ver `image_generation_guide.md` para detalles completos)
- Codex CLI identificado como **mejor opción SIN API KEY** para BIANCA
- Scripts reutilizables en `/Users/INTELIA_Manager/Desktop/BAGO_CAJAFISICA/TEST_BAGO_03(IMG)/methods/`

### Hallazgo crítico
```
Codex CLI genera imágenes de calidad ⭐⭐⭐⭐ sin ninguna API key
REGLA: NUNCA pipear la salida de codex exec
REGLA: Imágenes generadas en ~/.codex/generated_images/{session_id}/
```

---

## PROYECTO 6 — AUDITORÍA: TRAMPAS DEL FRAMEWORK (Apr 23)

**Trigger:** Inconsistencias detectadas en guardian health + inventarios incompatibles
**Resultado:** 13 trampas identificadas (ver `framework_traps.md`)

### Impacto
- Sesión más importante del mes en términos de calidad del framework
- Estableció roadmap de remediación CHG-002
- Evidenció que métricas de cantidad (count) son contraproducentes

---

## PROYECTO 7 — BIANCA PREP (Apr → Mayo)

**Estado al cierre de Abril:** Iniciado, no completado

### Trabajo realizado
- Compilación de assets BIANCA (~1.5GB) en BIANCA_MASTER
- 6 contratos de producción generados
- Engine paperdoll iniciado desde cero
- Paleta de colores definida: Azul Lecturia `#4da8ff`, Oro Arcana `#f7d774`, Rojo Energía `#ff6b6b`
- Hoodie: verde oscuro (override sobre biblia)
- Formato sprites: 256×512 o 256×1024

---

## Cronología consolidada

```
Apr 14  → PANDAMIEN corpus validation + BAGO V2.2.2 baseline
Apr 14  → Framework evolution inicia (V2.3-clean)
Apr 15  → workflow_bootstrap_repo_first implementado
Apr 16  → TPV/Contabilidad (primer proyecto no-narrativo)
Apr 18  → V2.4-v2rc: session preflight + bago auto
Apr 19  → 80+ comandos BAGO implementados
Apr 21  → V2.5-stable: sincerity_detector + cabinet_orchestrator
Apr 23  → AUDITORÍA CRÍTICA: 13 trampas identificadas
Apr 23  → TEST_BAGO_03 IMAGE GENERATION inicia
Apr 24  → Codex CLI confirmado como método principal T2I
Apr 2026 → BIANCA PREP: assets + contratos + paperdoll engine
```

---

## Lecciones del mes — Consolidadas

| ID | Lección | Proyecto |
|----|---------|----------|
| L-001 | Datos canónicos NUNCA hardcodeados → `{{chr_X.campo}}` | PANDAMIEN |
| L-002 | `workflow_validacion` aplica a corpus documental, no solo código | PANDAMIEN |
| L-003 | BAGO es transferible a cualquier dominio técnico | TPV |
| L-004 | Gradio/Flask para UIs de exploración rápida | NIGHTFRAME |
| L-005 | Codex CLI = mejor T2I sin API key en macOS M1 | TEST_BAGO_03 |
| L-006 | NUNCA pipear salida de `codex exec` | TEST_BAGO_03 |
| L-007 | Métricas de cantidad incentivan inflar — usar métricas de calidad | FRAMEWORK |
| L-008 | `--test` actual es trampa semántica — necesita asserts reales | FRAMEWORK |
| L-009 | Guardian con grep es frágil — necesita AST parsing | FRAMEWORK |
| L-010 | Compilar TODOS los assets ANTES de pivotar proyecto | BIANCA |

---

*Documento generado por BAGO MAESTRO · 2026-05-04*
*Fuente: sesiones reales Apr 14-24, auditoría May 1*
