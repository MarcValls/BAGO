# CHANGELOG

All notable changes to BAGO are documented here.
Format: `[version] — date · summary · efficiency index`

---

## [3.3.0] — Structural — 2026-05-06 · Efficiency Index: 100/100

### Summary
Structural release closing all 3 v3.3 milestone issues. Adds auto-generated
command reference, CI wheel gate, and cleans the dead `legacy-fix` launcher ref.
All 8 gates green on main. 48 tests passing, 0 failures.

### Issue #1 — P1: docs: generate COMMANDS.md from registry
- `generate_commands_doc.py` (`.bago/tools/`) reads `tool_registry.py` and renders
  a full human-readable `docs/COMMANDS.md` grouped by stability bucket.
- New `gate-docs` CI job: runs generator in `--check` mode; fails if committed
  `COMMANDS.md` differs from freshly generated output (stale guard).
- Generator supports `--write`, `--check`, `--stdout`, `--test` modes.

### Issue #2 — P1: wheel: verify and gate installable bago package
- `tests/test_wheel.py` — 18 tests covering package structure, importability,
  version alignment, launcher presence, and pyproject.toml contract.
- New `gate-wheel` CI job: `pip install -e .` → smoke tests → `pytest tests/test_wheel.py`
  → full wheel build → artifact upload.
- Known limitation documented: standalone `pip install bago` (non-editable) requires
  bundling the launcher — scoped for a future structural release.

### Issue #3 — P2: launcher: refactor routing + fix dead legacy-fix ref
- Removed dead `legacy-fix` command reference from `intent_router.py`.
- Routing now uses registry-aware detection instead of a hardcoded legacy map.
- `bago validate` and `gate-registry` remain clean.

### CI gates status (all green)
| Gate | Status |
|------|--------|
| gate-registry | ✅ |
| gate-syntax | ✅ |
| gate-security | ✅ |
| gate-tests | ✅ |
| gate-package | ✅ |
| gate-validate | ✅ |
| gate-docs | ✅ |
| gate-wheel | ✅ |

### Metrics
| Metric | Value |
|--------|-------|
| Tests passing | 48 |
| Tests xfailed | 1 (expected) |
| Active commands | 51 |
| CI jobs | 8 gates + 2 reports |

---

## [2.6-taxonomy] — 2026-05-06 · Efficiency Index: 100/100

### Summary
Major organisational release. Introduces a 6-layer taxonomy and a scope axis
(framework/project/both) across all 80 registered commands. Three command groups
(health, audit, session) are promoted to explicit routers that absorb 29 deprecated
direct calls. `bago help` is completely rewritten to display commands grouped by
layer with visual scope badges. Foundation laid for the future PADRE/SIEMBRA model.

### Architecture: taxonomy + scope
- `ToolEntry` gains `layer` and `scope` fields (all 80 commands classified)
- `LAYERS` dict: 6 layers — EJECUCIÓN · CALIDAD · SALUD · ANALÍTICA · VISUAL · AVANZADO
- `_LAYER_MAP` + `_SCOPE_MAP`: declarative maps injected at registry load time
- `SCOPE_BADGE`: 🔵 framework · 🟢 project · ⚪ both
- `get_by_layer()` public API for grouped rendering
- `scope_detector.py`: static analyzer — detects scope of any Python script by pattern matching

### New Routers (3 activated)
- `bago health`  → `bago_health_router`  (score|report|stability|efficiency|consistency|sincerity)
- `bago audit`   → `bago_audit_router`   (full|pack|scan|commit|push|doctor|heal|quality|purity)
- `bago session` → `bago_session_router` (open|close|harvest|v2)
  - ⚠️ **Breaking**: `bago session` (no args) now shows menu instead of opening a session

### Deprecations (29 total)
Commands consolidated into routers with `see_also` migration hints:
- **health group**: stability, efficiency, sincerity, report, consistency
- **audit group**: doctor, heal, scan, validate, check, commit, pre-push, code-quality
- **session group**: cosecha → session harvest · v2 → session v2 · session_close → session close
- + 13 deprecations from prior session (repo-*, project-*, context-*, detector, map, git, stale)

### `bago help` redesign
- Dynamic grouped display: 6 layers, each command with scope badge
- Replaced hardcoded 9-line flat list — now reads live from `tool_registry`
- Fallback to flat list if registry import fails (safe degradation)

### New Tools (28 added)
`auto_heal.py` · `bago_bs4_playwright_ref.py` · `bago_context.py` · `bago_hub.py`
`bago_miniapp_server.py` · `bago_propose_tasks.mjs` · `bago_repo.py`
`bago_repo_audit.sh` · `bago_telegram_daemon.py` · `bago_wa_daemon.py`
`bago_web_scraper_ref.py` · `code_review.py` · `dead_code.py` · `debt_ledger.py`
`findings_engine.py` · `goals.py` · `habit.py` · `image_studio.py` · `insights.py`
`launch_miniapp.sh` · `notify_bago.py` · `notify_whatsapp.py` · `orchestrator.py`
`project_memory.py` · `risk_matrix.py` · `scope_detector.py` · `secret_scan.py`
`smoke_runner.py` · `sprint_manager.py` · `sprite_studio.py` · `workspace_selector.py`

### Memory: sessions migrated to DB
- 58 historical sessions imported from JSON into `bago.db` (table `sessions`)
- `cosecha.py` now syncs session rows after every JSON write

### Repo cleanup
- Removed `adb/platform-tools/` (Android Debug Bridge, ~25 MB, Windows artefact)
- Removed `eth_capture.*`, `pktmon_eth*` (Windows network captures)
- Removed `admin_output.txt`, `lenovo_instructions.txt`
- `.gitignore` extended: state privado, backups (`*.bak`), image_studio dirs

### Idea captured (pending)
- `fw-padre-siembra` (bago.db slot 3): PADRE/SIEMBRA model — framework parent should
  not fully replicate into projects. `scope=project` commands are candidates for the seed.
  **Prerequisite (scope classification) is done. Implementation deferred to 3.0.**

### Fixes
- Python 3.13 + importlib + dataclasses: `sys.modules["_tr_bago"] = _tr` before `exec_module`
- `ToolEntry.scope` default `""` (was `"both"`) so `_SCOPE_MAP` injection fires correctly
- `_print_quick_action` unpacking 3-tuple `active_task` (was assuming 2-tuple)
- Removed duplicate `doctor` entry (old `doctor.py` silently overridden — now explicit)

### Metrics
| Metric | Value |
|---|---|
| CLI Commands (active) | 51 |
| CLI Commands (deprecated) | 29 |
| CLI Commands (total registered) | 80 |
| Tools (.py) | 177 |
| Docs (.md) | 278 |
| Workflows | 8 |
| tool_registry self-tests | 7/7 |
| scope_detector tests | 4/4 |
| Health Score | 100/100 |

> **Provenance note:** metrics captured at release time (`2026-05-06`) by `bago health` and
> `tool_registry --test` on the build that produced this tag.

---

## [2.5-stable] — 2026-04-19 · Efficiency Index: 100/100

### Summary
First fully stable release with complete self-evolution chain, task lifecycle, and efficiency measurement. Built using BAGO itself across 40+ registered changes.

### New CLI Commands
- `python3 bago efficiency` — Cross-version efficiency metrics with weighted index
- `python3 bago task` — Active task management (start, done, clear)
- `python3 bago stability` — Full stability report (smoke + VM + soak + validators)
- `python3 bago session` — Session opener with context bootstrapping

### New Tools (11 added)
- `audit_v2.py` — Full session audit trail
- `dashboard_v2.py` — System overview dashboard
- `efficiency_meter.py` — Inter-version efficiency comparison
- `health_score.py` — Composite health score (0–100) across 5 dimensions
- `reconcile_state.py` — State ↔ reality reconciliation
- `session_opener.py` — Structured session bootstrap
- `show_task.py` — Task viewer and lifecycle manager
- `stale_detector.py` — Detects stale tasks (>3 days)
- `v2_close_checklist.py` — Session closure checklist
- `vertice_activator.py` — Vértice role activation
- `workflow_selector.py` — Context-aware workflow selection

### Implemented Ideas (9 registered)
1. Handoff automático idea → W2
2. Resumen único de estabilidad
3. Gate canónico de validación
4. Opener de sesión desde task
5. Banner muestra task activa
6. Registro de ideas implementadas
7. Ideas baseline documentation
8. Alinear README con selector
9. Medidor de eficiencia inter-versiones

### Metrics
| Metric | Value |
|---|---|
| CLI Commands | 13 |
| Tools | 30 |
| Docs | 74 |
| Workflows | 12 |
| Registered CHGs | 40 |
| Efficiency Index | 100/100 |
| Health Score | 100/100 |

> **Provenance note:** these metrics were captured at release time (`2026-04-19`) by `python3 bago efficiency` and `python3 bago health` on the build that produced this tag. They are not live values. See CI badge in README for current test status.

---

## [2.4-v2rc] — 2026-04-18 · Efficiency Index: 89.3/100

### Summary
Dynamic BAGO release introducing the v2 bootstrap prompt (template seed), role activation system, and expanded toolset. Introduced session-level governance and first structured task management.

### New Features
- Bootstrap prompt: first run asks whether to evolve framework or start new project
- v2 close checklist for session closure discipline
- Vértice role for sensitive change review
- Reconcile state tool for inventory validation
- Session opener with structured context

### New Tools (8 added vs 2.3)
`audit_v2.py` · `dashboard_v2.py` · `health_score.py` · `reconcile_state.py` · `session_opener.py` · `show_task.py` · `stale_detector.py` · `v2_close_checklist.py` · `vertice_activator.py` · `workflow_selector.py`

### Metrics
| Metric | Value |
|---|---|
| CLI Commands | 10 |
| Tools | 27 |
| Docs | 73 |
| Workflows | 12 |
| Efficiency Index | 89.3/100 |

---

## [2.3-clean] — 2026-04-18 · Efficiency Index: 78.6/100 *(baseline)*

### Summary
Clean baseline release. Establishes the core BAGO operational layer: 10 workflows, fundamental tools, and the three-validator system (manifest + state + pack).

### Core capabilities
- 10 CLI commands via `python3 bago`
- 3 validators: `validate_manifest.py`, `validate_state.py`, `validate_pack.py`
- 12 structured workflows (W0–W9 + WORKFLOW_MAESTRO + WORKFLOWS_INDEX)
- Session lifecycle: open → work → cosecha → close
- Ideas system with scored selector
- Health monitoring via `bago health`
- Context drift detection

### Metrics
| Metric | Value |
|---|---|
| CLI Commands | 10 |
| Tools | 19 |
| Docs | 68 |
| Workflows | 12 |
| Efficiency Index | 78.6/100 |

---

*Growth summary: 2.3 → 2.5 = +27.2% efficiency · +3 CLI commands · +11 tools · +6 docs*
