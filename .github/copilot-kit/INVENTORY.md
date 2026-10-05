# Inventario granular BAGO Copilot CLI

HEAD: `13c34397f4d197bdc4803052e6157ccc372dcd03`. Fuentes del worktree actual; integracion runtime: NOT_RUN.

Archivos fuente: 611. Herramientas: 33 declaradas / 54 fuentes Python.

## Discrepancias del manifiesto

No declaradas: _path_helper.py, _registry_entries.py, _registry_models.py, _registry_paths.py, _registry_taxonomy.py, agent_router.py, bago_backup_vault.py, bago_canary.py, bago_infra_scan.py, bago_inventory.py, bago_security_audit.py, bago_utils.py, effect_sink_inventory.py, orchestrator_v4.py, preflight_engine.py, process_monitor.py, skill_engine.py, spiral_agent.py, tool_registry.py, toolsmith.py, world_state_snapshot_inventory.py.
Ausentes: ninguna.
Hashes distintos del manifiesto: auto_heal.py, code_metrics.py, commit_readiness.py, dead_code.py, debt_guard.py, debt_scanner.py, dep_audit.py, dir_list.py, doctor.py, file_edit.py, file_read.py, find_dependents.py, find_references.py, forced_dependency_scan.py, git_context.py, harmony_gate.py, issues_take.py, naming_check.py, net_scan.py, project_memory.py, project_scaffold.py, read_git_diff.py, read_lines.py, read_repository_map.py, runtime_control.py, search_symbol.py, search_text.py, secret_scan.py, sincerity_detector.py, todo_scan.py, token_rotation_guard.py, validate_syntax.py.

## Fuentes por seccion y significado

| Seccion | Significado | Fuente y linea | Descripcion orientativa |
|---|---|---|---|
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-architecture-auditor.agent.md:3` | Auditor arquitectónico principal de BAGO para decisiones de alta consecuencia, fronteras y conflictos de autoridad. |
| 01-copilot | Soporte y procedimiento | `.github/agents/bago-assistant.agent.md:3` | Asistente principal de BAGO que guia los siguientes pasos y orquesta el gabinete de agentes con alcance, autoridad y evidencia explicitos. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-backend-auditor.agent.md:3` | Auditor backend de BAGO para rutas, handlers, validación, persistencia, subprocess y fronteras de confianza. |
| 01-copilot | Observacion y conocimiento | `.github/agents/bago-code-mapper.agent.md:3` | Mapeador de flujos y dependencias de BAGO para reconstruir rutas UI/API/backend y ownership de estado. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-contracts-auditor.agent.md:3` | Auditor de contratos frontend-backend, tipos, rutas y compatibilidad de BAGO. |
| 01-copilot | Verificacion y evidencia | `.github/agents/bago-final-verifier.agent.md:3` | Independent read-only BAGO closure auditor for final-state evidence, acceptance criteria, regressions, scope drift and stale verification. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-frontend-auditor.agent.md:3` | Compatibilidad: auditor frontend BAGO; delega la disciplina completa al dominio repository.engineering.frontend. |
| 01-copilot | Soporte y procedimiento | `.github/agents/bago-frontend-engineer.agent.md:3` | Implementador especialista del frontend BAGO: React, TypeScript, estado, navegación, API, tokens y pruebas. |
| 01-copilot | Verificacion y evidencia | `.github/agents/bago-frontend-verifier.agent.md:3` | Verificador independiente de cambios frontend BAGO, centrado en contratos, ownership, regresiones y evidencia fresca. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-hygiene-scanner.agent.md:3` | Escáner de bajo coste para código muerto, legacy, dependencias, CSS y documentación divergente. |
| 01-copilot | Intervencion | `.github/agents/bago-implementation-worker.agent.md:3` | Implementador principal para PRs de BAGO ya definidos y aprobados. |
| 01-copilot | Intervencion | `.github/agents/bago-mechanical-worker.agent.md:3` | Trabajador rápido para cambios mecánicos, repetitivos y totalmente especificados en BAGO. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-performance-auditor.agent.md:3` | Auditor de performance de BAGO con foco en renders, effects, IO, árboles, parsing, listeners y procesos. |
| 01-copilot | Soporte y procedimiento | `.github/agents/bago-refactor-planner.agent.md:3` | Planificador de refactor incremental de BAGO a partir de hallazgos verificados. |
| 01-copilot | Observacion y conocimiento | `.github/agents/bago-repo-explorer.agent.md:3` | Explorador read-only de BAGO para inventarios, búsquedas masivas y localización rápida de código. |
| 01-copilot | Soporte y procedimiento | `.github/agents/bago-repository-engineer.agent.md:3` | Main BAGO repository-engineering coordinator. Use for scoped implementation, repository audits, architecture-sensitive changes, evidence-backed verification and handoffs. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-security-auditor.agent.md:3` | Auditor de seguridad de BAGO para filesystem, subprocess, credenciales, Electron, herramientas IA y acciones destructivas. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-test-auditor.agent.md:3` | Auditor de tests, CI, build y runtime de BAGO. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-truth-auditor.agent.md:3` | Auditor de estado, evidencia y verdad operacional de BAGO. |
| 01-copilot | Evaluacion y diagnostico | `.github/agents/bago-ui-architecture-auditor.agent.md:3` | Auditor read-only de arquitectura UI BAGO: shell, ownership, módulos, navegación, efectos, API, tokens y mantenibilidad. |
| 01-copilot | Soporte y procedimiento | `.github/agents/bago-ui-state-tracer.agent.md:3` | Trazador read-only de estado y flujo UI de BAGO desde interacción hasta backend, render y prueba. |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/00-preflight.md:1` | Fijar objeto auditado |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/01-inventory.md:1` | Inventario completo |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/02-architecture.md:1` | Arquitectura real y God Components |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/03-frontend.md:1` | Frontend completo |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/04-backend.md:1` | Backend completo |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/05-contracts.md:1` | Contratos frontend-backend |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/06-workspace.md:1` | Workspace en profundidad |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/07-features.md:1` | Agents, Interpreter y GitHub |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/08-security.md:1` | Seguridad y trust boundaries |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/09-tests-ci.md:1` | Tests, build, CI y runtime |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/10-hygiene.md:1` | Dead code, legacy, dependencias, CSS y docs |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/11-performance.md:1` | Performance |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/12-truth-authority.md:1` | Estado, evidencia y verdad operacional |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/13-synthesis.md:1` | Síntesis integral |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/14-refactor-plan.md:1` | Plan de corrección por PR |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/20-implement-approved-pr.md:1` | Implementar PR aprobado |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/references/tasks/21-mechanical-approved.md:1` | Cambio mecánico aprobado |
| 01-copilot | Verificacion y evidencia | `.github/skills/bago-audit/references/tasks/22-verify-change.md:1` | Verificación independiente |
| 01-copilot | Evaluacion y diagnostico | `.github/skills/bago-audit/SKILL.md:3` | Run the BAGO repository audit pipeline adapted from the Codex workpack using Copilot custom agents, preserving evidence, RunId isolation and read-only audit boundaries. |
| 01-copilot | Autoridad y limites | `.github/skills/bago-core/references/CLOSURE_PROTOCOL.md:1` | BAGO Closure Protocol — Provisional Adapter |
| 01-copilot | Autoridad y limites | `.github/skills/bago-core/references/CONTEXT_PROTOCOL.md:1` | BAGO Context Protocol — Provisional Adapter |
| 01-copilot | Verificacion y evidencia | `.github/skills/bago-core/references/EVIDENCE_PROTOCOL.md:1` | BAGO Evidence Protocol — Provisional Adapter |
| 01-copilot | Autoridad y limites | `.github/skills/bago-core/references/HOOK_PROTOCOL.md:1` | Hook Protocol |
| 01-copilot | Soporte y procedimiento | `.github/skills/bago-core/references/STATE_MODEL.md:1` | BAGO State Model — Provisional Adapter |
| 01-copilot | Soporte y procedimiento | `.github/skills/bago-core/SKILL.md:3` | Apply BAGO context architecture, project isolation, evidence-first execution and final-state verification. Use for non-trivial work, continuation, conflicts, implementation, verification, validation or closure-sensitive  |
| 01-copilot | Soporte y procedimiento | `.github/skills/bago-frontend-engineering/SKILL.md:3` | Specialized BAGO frontend engineering for React/TypeScript UI architecture, state ownership, UI-to-backend tracing, tokens, implementation and verification. Use for material work under frontend/ or UI behavior in BAGO. |
| 01-copilot | Soporte y procedimiento | `.github/skills/bago-toolkit/SKILL.md:3` | Discover and reuse BAGO scripts, tools, prompts, roles, skills, agents, workflows, and Copilot CLI adapters. Use when assembling or adapting BAGO capabilities for GitHub Copilot CLI. |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/BAGO_REPO_BINDING.md:1` | BAGO repository binding |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN.md:1` | DOMAIN — repository.engineering v0.1.1 |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_CANON.md:1` | DOMAIN CANON — candidate for repository.engineering v0.1.1 |
| 01-copilot | Verificacion y evidencia | `.github/skills/repository-engineering/references/DOMAIN_EVIDENCE.md:1` | DOMAIN EVIDENCE — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_MANIFEST.json:1` | Fuente .json; contenido de referencia |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_MEMORY.md:1` | DOMAIN MEMORY — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_OPERATIONS.md:1` | DOMAIN OPERATIONS — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_PROCEDURES.md:1` | DOMAIN PROCEDURES — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_PROJECT_BINDINGS.md:1` | DOMAIN PROJECT BINDINGS — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_RELATIONS.md:1` | DOMAIN RELATIONS — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_ROUTING.md:1` | DOMAIN ROUTING — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_RUNTIME_BINDINGS.md:1` | DOMAIN RUNTIME BINDINGS — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/DOMAIN_STATE.md:1` | DOMAIN STATE — repository.engineering |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/KERNEL_PROFILE.md:1` | Kernel profile used by this skill |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/references/README.md:1` | REPOSITORY ENGINEERING — repository.engineering v0.1.1 |
| 01-copilot | Soporte y procedimiento | `.github/skills/repository-engineering/SKILL.md:3` | Candidate repository.engineering v0.1.1 operational projection for auditing, planning, modifying, verifying, governing and containing repository changes with explicit baseline, evidence and authority separation. |
| 01-copilot | Coordinacion y preparacion | `.github/prompts/bago-00-preflight.prompt.md:3` | BAGO workpack: 00 preflight |
| 01-copilot | Observacion y conocimiento | `.github/prompts/bago-01-inventory.prompt.md:3` | BAGO workpack: 01 inventory |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-02-architecture.prompt.md:3` | BAGO workpack: 02 architecture |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-03-frontend.prompt.md:3` | BAGO workpack: 03 frontend |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-04-backend.prompt.md:3` | BAGO workpack: 04 backend |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-05-contracts.prompt.md:3` | BAGO workpack: 05 contracts |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-06-workspace.prompt.md:3` | BAGO workpack: 06 workspace |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-07-features.prompt.md:3` | BAGO workpack: 07 features |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-08-security.prompt.md:3` | BAGO workpack: 08 security |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-09-tests-ci.prompt.md:3` | BAGO workpack: 09 tests ci |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-10-hygiene.prompt.md:3` | BAGO workpack: 10 hygiene |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-11-performance.prompt.md:3` | BAGO workpack: 11 performance |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-12-truth-authority.prompt.md:3` | BAGO workpack: 12 truth authority |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-13-synthesis.prompt.md:3` | BAGO workpack: 13 synthesis |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-14-refactor-plan.prompt.md:3` | BAGO workpack: 14 refactor plan |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-20-implement-approved-pr.prompt.md:3` | BAGO workpack: 20 implement approved pr |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-21-mechanical-approved.prompt.md:3` | BAGO workpack: 21 mechanical approved |
| 01-copilot | Verificacion y evidencia | `.github/prompts/bago-22-verify-change.prompt.md:3` | BAGO workpack: 22 verify change |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-frontend-add-feature.prompt.md:3` | BAGO frontend: añadir superficie/feature |
| 01-copilot | Evaluacion y diagnostico | `.github/prompts/bago-frontend-audit.prompt.md:3` | BAGO frontend: auditoría completa |
| 01-copilot | Evaluacion y diagnostico | `.github/prompts/bago-frontend-check-hardcoded.prompt.md:3` | BAGO frontend: revisar hardcoded/tokens |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-frontend-fix.prompt.md:3` | BAGO frontend: corregir bug |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-frontend-refactor.prompt.md:3` | BAGO frontend: refactor seguro |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-frontend-refresh-map.prompt.md:3` | BAGO frontend: refrescar mapa de superficies |
| 01-copilot | Soporte y procedimiento | `.github/prompts/bago-frontend-trace-state.prompt.md:3` | BAGO frontend: trazar estado/flujo |
| 01-copilot | Verificacion y evidencia | `.github/prompts/bago-frontend-verify.prompt.md:3` | BAGO frontend: verificar cambio |
| 01-copilot | Autoridad y limites | `.github/instructions/backend.instructions.md:5` | BAGO backend instructions |
| 01-copilot | Autoridad y limites | `.github/instructions/frontend.instructions.md:5` | BAGO Frontend Engineering v1.0 |
| 01-copilot | Autoridad y limites | `.github/instructions/governance.instructions.md:5` | BAGO governance and contract instructions |
| 01-copilot | Autoridad y limites | `.github/instructions/release.instructions.md:5` | BAGO release instructions |
| 01-copilot | Autoridad y limites | `.github/instructions/tests.instructions.md:5` | BAGO tests and CI instructions |
| 01-copilot | Autoridad y limites | `.github/copilot-instructions.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/ADAPTADOR_PROYECTO.md:1` | AGENTE · ADAPTADOR_PROYECTO |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/agent_command_execution.py:1` | Operation-bound execution interface for commands dispatched by agents. |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/agent_contract.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Coordinacion y preparacion | `backend/.bago/agents/agent_factory.py:3` | agent_factory.py — FÁBRICA DE AGENTES BAGO |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/agent_gateway.py:2` | agent_gateway.py — BAGO Multi-Agent Orchestration Gateway |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/COPILOT_ALIADO_BAGO.md:1` | COPILOT_ALIADO_BAGO |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/duplication_finder.py:3` | duplication_finder.py — AGENTE especializado en detección de código duplicado. |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/INICIADOR_MAESTRO.md:1` | AGENTE · INICIADOR_MAESTRO |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/agents/logic_checker.py:3` | logic_checker.py — AGENTE especializado en detección de errores lógicos. |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/README.md:1` | agents/ |
| 02-framework | Soporte y procedimiento | `backend/.bago/agents/security_analyzer.py:3` | security_analyzer.py — AGENTE especializado en detección de vulnerabilidades. |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/agents/smell_detector.py:3` | smell_detector.py — AGENTE especializado en detección de code smells. |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/especialistas/INTEGRADOR_REPO.md:1` | INTEGRADOR REPO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/especialistas/REVISOR_PERFORMANCE.md:1` | REVISOR PERFORMANCE |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/especialistas/REVISOR_SEGURIDAD.md:1` | REVISOR SEGURIDAD |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/especialistas/REVISOR_UX.md:1` | REVISOR UX |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/gobierno/MAESTRO_BAGO.md:1` | MAESTRO_BAGO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/gobierno/ORQUESTADOR_CENTRAL.md:1` | ORQUESTADOR CENTRAL |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/manifest.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/produccion/ANALISTA.md:1` | ANALISTA |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/produccion/ARQUITECTO.md:1` | ARQUITECTO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/produccion/GENERADOR.md:1` | GENERADOR |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/produccion/ORGANIZADOR.md:1` | ORGANIZADOR |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/produccion/VALIDADOR.md:1` | VALIDADOR |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/README.md:1` | Roles Factory — BAGO Cabinet |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/role_factory.py:3` | role_factory.py — FÁBRICA DE ROLES BAGO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/ROLE_TEMPLATE.md:1` | PLANTILLA DE ROL BAGO |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/roles/supervision/AUDITOR_CANONICO.md:1` | AUDITOR CANÓNICO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/supervision/CENTINELA_SINCERIDAD.md:1` | CENTINELA DE SINCERIDAD |
| 02-framework | Coordinacion y preparacion | `backend/.bago/roles/supervision/VERTICE.md:1` | REVISOR ESTRUCTURAL · VÉRTICE EVOLUTIVO |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/00_BOOTSTRAP_PROYECTO.md:1` | BOOTSTRAP_PROYECTO |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/01_ARRANQUE_MAESTRO.md:1` | ARRANQUE_MAESTRO |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/02_ANALISIS_REPO.md:1` | ANALISIS_REPO |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/03_TAREA_DE_PROYECTO.md:1` | TAREA_DE_PROYECTO |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/04_REVISION_EVOLUTIVA.md:1` | REVISION_EVOLUTIVA |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/05_ACTUALIZACION_ESTADO_BAGO.md:1` | ACTUALIZACION_ESTADO_BAGO |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/06_PROMPTS_README.md:1` | prompts/ |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/activar_maestro.md:1` | PROMPT DE ACTIVACIÓN · MAESTRO_BAGO |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/activar_migracion_historial.md:1` | PROMPT DE ACTIVACIÓN · MIGRACIÓN DE HISTORIAL |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/activar_orquestador.md:1` | PROMPT DE ACTIVACIÓN · ORQUESTADOR CENTRAL |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/activar_revision_canonica.md:1` | PROMPT DE ACTIVACIÓN · REVISIÓN CANÓNICA |
| 02-framework | Soporte y procedimiento | `backend/.bago/prompts/activar_workflow.md:1` | PROMPT DE ACTIVACIÓN · WORKFLOW |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/music-score-transposition.md:1` | Music score transposition operational workflow |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/README.md:1` | Core Workflows Index |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W0_FREE_SESSION.md:1` | W0 · SESIÓN LIBRE (sin estructura BAGO) |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/workflows/W10_AUDITORIA_SINCERIDAD.md:1` | W10 · Auditoría de Sinceridad |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W1_COLD_START.md:1` | W1 · Cold Start |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W2_IMPLEMENTACION_CONTROLADA.md:1` | W2 · Implementación Controlada |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W3_REFACTOR_SENSIBLE.md:1` | W3 · Refactor Sensible |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W4_DEBUG_MULTICAUSA.md:1` | W4 · Debug Multicausa |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W5_CIERRE_Y_CONTINUIDAD.md:1` | W5 · Cierre y Continuidad |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W6_IDEACION_APLICADA.md:1` | W6 · Ideación Aplicada |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W7_FOCO_SESION.md:1` | W7 · FOCO DE SESIÓN |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W8_EXPLORACION.md:1` | W8 · Sesión de Exploración |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/W9_COSECHA.md:1` | W9 · Cosecha Contextual |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/WORKFLOW_GRAPH.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/WORKFLOW_MAESTRO_BAGO.md:1` | WORKFLOW_MAESTRO_BAGO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/workflows/WORKFLOWS_INDEX.md:1` | WORKFLOWS_INDEX |
| 02-framework | Produccion de artefactos | `backend/.bago/templates/plantilla_cambio.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Produccion de artefactos | `backend/.bago/templates/plantilla_evaluacion_brutal.md:1` | PLANTILLA · EVALUACIÓN BRUTAL DE BAGO |
| 02-framework | Produccion de artefactos | `backend/.bago/templates/plantilla_evidencia.md:1` | PLANTILLA DE EVIDENCIA |
| 02-framework | Produccion de artefactos | `backend/.bago/templates/plantilla_rol.md:1` | PLANTILLA DE ROL |
| 02-framework | Produccion de artefactos | `backend/.bago/templates/plantilla_workflow.md:1` | PLANTILLA DE WORKFLOW |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/_path_helper.py:2` | _path_helper.py — Centralized sys.path bootstrap for .bago/tools scripts. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/_registry_entries.py:1` | _registry_entries.py — Canonical REGISTRY dict of BAGO tools. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/_registry_models.py:1` | _registry_models.py — Dataclasses for BAGO tool registry entries. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/_registry_paths.py:1` | _registry_paths.py — Path constants shared across registry sub-modules. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/_registry_taxonomy.py:1` | _registry_taxonomy.py — Layer/scope/agent taxonomy maps and post-processing. |
| 02-framework | Coordinacion y preparacion | `backend/.bago/tools/agent_router.py:21` | Fuente Python; simbolo _default_ollama_url (comportamiento no ejecutado) |
| 02-framework | Intervencion | `backend/.bago/tools/auto_heal.py:33` | Fuente Python; simbolo _is_excluded_path (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/bago_backup_vault.py:2` | Portable backup vault for BAGO 4.x. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/bago_canary.py:2` | Portable honeytoken manager for BAGO 4.x. |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/bago_infra_scan.py:2` | Portable local LLM infrastructure scanner. |
| 02-framework | Observacion y conocimiento | `backend/.bago/tools/bago_inventory.py:2` | Portable workspace inventory for BAGO. |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/bago_security_audit.py:24` | Fuente Python; simbolo _display (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/bago_utils.py:3` | bago_utils.py — Utilities compartidas para herramientas BAGO |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/code_metrics.py:19` | Fuente Python; simbolo _normalize_exts (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/commit_readiness.py:2` | Portable pre-commit readiness checker for BAGO 4.x. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/dead_code.py:2` | dead_code.py — Herramienta #102: Detector de código muerto (Python). |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/debt_guard.py:2` | debt_guard.py — BAGO Guardián de Deuda Técnica |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/debt_scanner.py:2` | debt_scanner.py — BAGO Sonda de Deuda Técnica Invisible |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/dep_audit.py:2` | dep_audit.py — Herramienta #123: Auditoría de seguridad de dependencias Python. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/dir_list.py:2` | dir_list.py — BAGO tool: list directory contents in the workspace. |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/doctor.py:2` | Portable project doctor for BAGO 4.x. |
| 02-framework | Observacion y conocimiento | `backend/.bago/tools/effect_sink_inventory.py:2` | Static inventory of BAGO effect sinks. |
| 02-framework | Intervencion | `backend/.bago/tools/file_edit.py:2` | file_edit.py — BAGO tool: replace text within a file in the workspace. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/file_read.py:2` | file_read.py — BAGO tool: read a file from the workspace. |
| 02-framework | Intervencion | `backend/.bago/tools/file_write.py:2` | file_write.py — BAGO tool: write or create a file in the workspace. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/find_dependents.py:15` | Fuente Python; simbolo main (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/find_references.py:15` | Fuente Python; simbolo main (comportamiento no ejecutado) |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/forced_dependency_scan.py:2` | Detecta dependencias forzadas, pins raros y patrones de instalacion directa. |
| 02-framework | Observacion y conocimiento | `backend/.bago/tools/git_context.py:2` | Portable git context snapshot for BAGO 4.x. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/harmony_gate.py:23` | Fuente Python; simbolo phase_consonance (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/issues_take.py:15` | Fuente Python; simbolo _usage (comportamiento no ejecutado) |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/naming_check.py:2` | naming_check.py — Herramienta #120: Validador de convenciones de nombres. |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/net_scan.py:15` | Fuente Python; simbolo _run (comportamiento no ejecutado) |
| 02-framework | Coordinacion y preparacion | `backend/.bago/tools/orchestrator_v4.py:3` | orchestrator_v4.py — BAGO Orchestrator |
| 02-framework | Coordinacion y preparacion | `backend/.bago/tools/preflight_engine.py:2` | Portable preflight check engine. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/process_monitor.py:1` | BAGO Process Monitor — monitor HTML en tiempo real de todos los procesos internos. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/project_memory.py:2` | Portable BAGO project memory manager. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/project_scaffold.py:2` | project_scaffold.py — BAGO tool: scaffold a new project structure. |
| 02-framework | Observacion y conocimiento | `backend/.bago/tools/read_git_diff.py:12` | Fuente Python; simbolo main (comportamiento no ejecutado) |
| 02-framework | Observacion y conocimiento | `backend/.bago/tools/read_lines.py:11` | Fuente Python; simbolo _workspace_root (comportamiento no ejecutado) |
| 02-framework | Observacion y conocimiento | `backend/.bago/tools/read_repository_map.py:14` | Fuente Python; simbolo workspace_root (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/README.md:1` | BAGO Tools — Historical ports and active utilities |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/runtime_control.py:1` | Session-bound entry point for governed BAGO runtime control. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/search_symbol.py:15` | Fuente Python; simbolo main (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/search_text.py:15` | Fuente Python; simbolo main (comportamiento no ejecutado) |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/secret_scan.py:2` | secret_scan.py — Herramienta #108: Escáner de secretos y credenciales hardcodeadas. |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/sincerity_detector.py:76` | Fuente Python; simbolo Finding (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/skill_engine.py:29` | Fuente Python; simbolo _resolve_bago_root (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/spiral_agent.py:32` | Fuente Python; simbolo _resolve_bago_root (comportamiento no ejecutado) |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/tools/todo_scan.py:3` | todo_scan.py — Escanea el código fuente del proyecto buscando TODOs y FIXMEs. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/token_rotation_guard.py:2` | token_rotation_guard.py — Escanea un proyecto buscando tokens de API hardcodeados. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/tool_registry.py:2` | tool_registry.py — Registro central de herramientas BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools/toolsmith.py:30` | Fuente Python; simbolo _resolve_bago_root (comportamiento no ejecutado) |
| 02-framework | Verificacion y evidencia | `backend/.bago/tools/validate_syntax.py:12` | Fuente Python; simbolo main (comportamiento no ejecutado) |
| 02-framework | Observacion y conocimiento | `backend/.bago/tools/world_state_snapshot_inventory.py:1` | Generate and verify the production WorldStateSnapshot callsite inventory. |
| 02-framework | Autoridad y limites | `backend/.bago/contracts/bago.capability-definition.v1.schema.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Autoridad y limites | `backend/.bago/contracts/bago.effect-registry.v1.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Autoridad y limites | `backend/.bago/contracts/bago.execution-request.v2.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Autoridad y limites | `backend/.bago/contracts/bago.execution-request.v3.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Autoridad y limites | `backend/.bago/contracts/bago.kernel-boundary.v1.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Autoridad y limites | `backend/.bago/contracts/bago.package.v1.schema.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Autoridad y limites | `backend/.bago/contracts/bago.pipeline-definition.v1.schema.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/__init__.py:1` | Fuente .py; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/agent_dispatcher.py:2` | agent_dispatcher.py — BAGO v3.0 Agent Dispatcher |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/agent_gateway.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/architecture/PADRE_SIEMBRA.md:1` | BAGO v3.0 — Modelo PADRE / SIEMBRA |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/architecture/README.md:1` | Core Architecture Index |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/authorization_boundary.py:1` | User authorization provenance boundary for governed BAGO execution. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/autonomous_loop.py:2` | autonomous_loop.py — BAGO Real Autonomy Loop |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_context.py:2` | bago_context.py — BAGO v3.0 Shared Context Service |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/__init__.py:1` | BAGO Semantic Procedural Behavior Engine (SPBE). |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/cycles.py:7` | Fuente Python; simbolo SemanticCycleValidator (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/eligibility.py:6` | Fuente Python; simbolo EligibilityEvaluator (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/engine.py:26` | Fuente Python; simbolo SemanticProceduralBehaviorEngine (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/model.py:9` | Fuente Python; simbolo Eligibility (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/PACK_PROVENANCE.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/pipeline.py:12` | Fuente Python; simbolo SPBEPipeline (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/ports.py:15` | Fuente Python; simbolo SemanticInterpreterPort (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/bago_spbe/resolution.py:6` | Fuente Python; simbolo CapabilityResolver (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/CANON.md:1` | CANON · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/CONTRATOS/contrato_cambio.md:1` | CONTRATO DE CAMBIO · BAGO AMTEC línea canónica previa |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/CONTRATOS/contrato_evidencia.md:1` | CONTRATO DE EVIDENCIA · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/CONTRATOS/contrato_rol.md:1` | CONTRATO DE ROL · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/CONTRATOS/contrato_workflow.md:1` | CONTRATO DE WORKFLOW · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/CONTRATOS/README.md:1` | CONTRATOS LEGACY · BAGO AMTEC línea canónica previa |
| 02-framework | Autoridad y limites | `backend/.bago/core/canon/PROTOCOLO_DE_CAMBIO.md:1` | PROTOCOLO DE CAMBIO · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/README.md:1` | Core Canon Index |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/REGLAS_DE_ACTIVACION.md:1` | REGLAS DE ACTIVACIÓN · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/canon/TAXONOMIA.md:1` | TAXONOMÍA · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/capability_packages.py:1` | Capability package lifecycle backed by the generic BAGO Package v1 contract. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/command_intents.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/config_manager.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_budget.py:1` | context_budget.py — ContextBudget tracker y BudgetReport. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_compressor.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_envelope.py:1` | context_envelope.py — ContextFragment, ContextEnvelope, ContextReceipt, SystemPromptCapsule. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_governance.py:2` | context_governance.py — source routing, ranking, claims and canon cache. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_patterns/manifest.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_patterns/README.md:1` | Core Context Patterns |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_patterns/workspace_discourse.md:1` | Workspace Followups |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_patterns/workspace_markers.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_patterns/workspace_questions.toml:1` | Fuente .toml; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_patterns.py:2` | Canonical pattern registry for context routing. |
| 02-framework | Verificacion y evidencia | `backend/.bago/core/context_receipt_validator.py:1` | context_receipt_validator.py — Independent receipt validation for BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/context_store.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/contract_state.py:2` | contract_state.py - canonical DTO builders for BAGO surfaces. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/credential_manager.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/database_write_request.py:1` | Canonical request construction for persistent memory database writes. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/delegation_grant.py:1` | Persistent, fail-closed delegation grants for scheduled execution. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/directory_context.py:2` | directory_context.py - deterministic directory context engine for BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/effect_registry.py:1` | Canonical effect registry for BAGO execution governance. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/embedding_store.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapter_contract.py:1` | Shared runtime types for gateway-owned effect adapters. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/__init__.py:1` | Server-owned adapters selected through ExecutionGateway. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/archive_rollback.py:1` | Strong CLI owner for restoring a named Program Files rollback archive. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/autonomous.py:1` | Operation-bound execution for the autonomous loop's fixed CLI tools. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/canary.py:1` | Strong, operation-bound owner for synthetic project canary files. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/capability.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/capability_import.py:1` | Permit-bound materialization of imported Capability Packages. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/context.py:1` | Gateway-owned context bundle attachment. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/credentials.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/database_write.py:1` | Gateway owner for bounded KnowledgeBase and EmbeddingStore mutations. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/delegation.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Verificacion y evidencia | `backend/.bago/core/execution_adapters/evidence_bundle.py:1` | Strong CLI owner for evidence-bundle materialization and replacement. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/filesystem.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/install_uninstall_lifecycle.py:1` | Materialization helpers for the Permit-ticketed system uninstall owner. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/manager_settings.py:1` | Gateway owner for Electron manager settings persisted in canonical user state. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/monitor.py:1` | Operation-bound materialization of a generated Process Monitor report. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/network.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/pi_sidecar.py:1` | Narrow process operation for the trusted PI provider sidecar. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/plan.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/process.py:1` | Registered server-owned process execution adapter. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/project.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/release.py:1` | Server-owned release download adapter. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/release_job_archive.py:1` | Explicit, operation-bound archival of terminal release jobs. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/release_job_log.py:1` | Policy adapter for bounded append-only release-job log records. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/release_job_state.py:1` | Policy adapter for durable release-job JSON state. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/release_signature.py:1` | Server-owned signature verification for cached release-job bundles. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/release_stage.py:1` | Safely stage a verified release ZIP inside the canonical release-job area. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/repository_guard.py:1` | Gateway owner for BAGO's repository-local debt guard settings and hook. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/repository_inspection.py:1` | Bounded, read-only Git inspection under direct CLI authorization. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/role_definition.py:1` | Gateway owner for creating repository role definitions and their manifest entry. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/runtime_state.py:1` | Gateway owner for runtime state directory and example initialization. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/session_state.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/source_update.py:1` | Strong-Permit owner for fast-forwarding one clean BAGO source checkout. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/structured_logging.py:1` | Server-owned writer and rotator for the canonical bridge log. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/system_install.py:1` | Strong-Permit owner for launching a prepared BAGO installation. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/system_install_rollback.py:1` | Strong-Permit owner for restoring one release-job installation. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/system_install_uninstall.py:1` | Strong-Permit dispatcher for one ticket-bound BAGO uninstall operation. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/system_update.py:1` | Server-owned, directly authorized system update application. |
| 02-framework | Verificacion y evidencia | `backend/.bago/core/execution_adapters/validation_staging.py:1` | Server-owned materializer and cleanup for temporary validation snapshots. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_adapters/workspace.py:1` | Registered server-owned effect adapters for this domain. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_claims.py:1` | Execution coordination claims for the governed runtime. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_envelope.py:1` | Canonical envelope crossing the authorization/effect boundary. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_gateway.py:1` | Closed execution gateway for governed BAGO effects. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_operations.py:1` | Durable operation records for reconciling idempotent desired-state effects. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/execution_request.py:1` | Generic execution request contract for governed BAGO effects. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/filesystem_effects.py:1` | Trusted filesystem effect implementation for :mod:`execution_gateway`. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/gabo_connector.py:1` | gabo_connector.py — Conecta .gabo/ manifests al runtime de BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/governed_work_pipeline.py:1` | 04-FIX2 runtime sidecar for bounded PlanEngine work. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/guardrails.py:1` | guardrails.py — F4: Forbidden paths, structured tool log, no claims without execution. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/install_plan.py:1` | Canonical identity for a prepared BAGO installation operation. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/install_uninstall_plan.py:1` | Read-only identity and safety preflight for an uninstall operation. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/intent_engine.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/intent_examples.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/knowledge_base.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/learning_writer.py:2` | learning_writer.py — BAGO Aprendiz: cierra el loop de aprendizaje autónomo. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/memory_database_schema.py:1` | Shared SQLite schema declarations for the persistent memory stores. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/message_adapter.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/model_buffer.py:1` | model_buffer.py — Buffer cleaner para modelos locales (Ollama). |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/model_equivalence.py:1` | Compatibility facade for versioned provider routing policy. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/msix_bootstrap.py:1` | In-process MSIX bootstrap checks and canonical BAGO session initialization. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/native_approval.py:1` | Server-owned Windows confirmation for strong BAGO authorization. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/ollama_discovery.py:2` | ollama_discovery.py - helpers para descubrir modelos Ollama. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/operational_intent.py:1` | Operational-intent value object. |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/orchestrator/MATRIZ_DE_ENRUTADO.md:1` | MATRIZ DE ENRUTADO · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/orchestrator/ORQUESTADOR_CENTRAL.md:1` | ORQUESTADOR CENTRAL · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/orchestrator/README.md:1` | Core Orchestrator Index |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/orchestrator/ROUTER_DE_ROLES.md:1` | Router de roles — gabinete BAGO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/package_contract.py:1` | Validation and deterministic serialization for ``bago.package/v1``. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/plan_engine.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/project_patch_operations.py:1` | Request construction and dispatch helpers for project patch operations. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompt_loader.py:2` | Small file-backed prompt loader for BAGO prompt blocks. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/bc_policy.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/behavior_policy.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/intent_chat.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/intent_execute.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/intent_review.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/intent_work.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/README.md:1` | Core Prompt Blocks |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/prompts/router.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/task_response_contract.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/translation_en_to_es.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/translation_es_to_en.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/workspace_authority.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/prompts/workspace_question.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/provider_adapter.py:1` | Compatibility facade for the stable provider contracts package. |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/core/reflexive_audit_ledger.py:2` | Append-only evidence ledger for Reflexive Interpreter analyses. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/reflexive_interpreter.py:2` | Deterministic reflexive interpretation core for BAGO. |
| 02-framework | Autoridad y limites | `backend/.bago/core/reflexive_rules.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/release_job_paths.py:1` | Canonical and symlink-safe paths owned by the release-job subsystem. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/rl_engine.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/runtime.py:2` | runtime.py — BAGO runtime path resolver (PR-06 Kernel Lockdown). |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/schedule_registry.py:1` | Persistent schedule registry without stored-confirmation authority. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/script_registry.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_adapters_mixin.py:2` | session_adapters_mixin.py — Adapter management mixin for SessionManager. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_context_envelope_mixin.py:2` | Context envelope, metrics and certification helpers for SessionManager. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_context_mixin.py:2` | Facade mixin that composes the modularized session context helpers. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_context_policy_mixin.py:2` | Policy, retrieval and classifier helpers for SessionManager context. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_context_workspace_mixin.py:2` | Workspace and prompt helpers for SessionManager context construction. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_manager.py:2` | session_manager.py — BAGO Session Manager (slim core). |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_persistence_mixin.py:2` | session_persistence_mixin.py — Persistence and status mixin for SessionManager. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_registry.py:1` | Índice canónico y puntero de la sesión activa de BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_tools_mixin.py:2` | session_tools_mixin.py — Tool approval, feedback, and memory mixin for SessionManager. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_turn_mixin.py:2` | session_turn_mixin.py - Turn execution mixin for SessionManager. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/session_utils.py:2` | session_utils.py — Free functions and constants for SessionManager. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/spbe_runtime.py:2` | BAGO host adapter for the frozen SPBE behavior-engine implementation. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/state_paths.py:8` | Fuente Python; simbolo resolve_state_root (comportamiento no ejecutado) |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/core/supervision/AUDITOR_CANONICO.md:1` | AUDITOR CANÓNICO · SUPERVISIÓN DE COHERENCIA |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/supervision/MATRIZ_DE_ALERTAS.md:1` | MATRIZ DE ALERTAS · BAGO AMTEC línea canónica previa CORREGIDO |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/supervision/README.md:1` | Core Supervision Index |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/supervision/VERTICE.md:1` | VÉRTICE · SUPERVISIÓN EVOLUTIVA |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/switch_engine.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/task_response_contract.py:2` | task_response_contract.py - JSON contract for task-oriented model turns. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/task_response_presenter.py:2` | Present internal task contracts as concise user-facing responses. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/tool_receipt.py:1` | tool_receipt.py — tipo canónico de ToolReceipt BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/tool_registry.py:1` | Compatibility shim for the tool registry. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/translation_adapter.py:1` | translation_adapter.py — Wrap de un ProviderAdapter que aplica el |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/translation_middleware.py:1` | translation_middleware.py — Wrap de un provider adapter que traduce |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/version.py:2` | version.py — BAGO Version Index Reader |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/windows_execution.py:1` | Resolve fixed, OS-owned executables for Windows runtime effects. |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/README.md:1` | Core Workflow Playbooks |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/workflow_analisis.md:1` | WORKFLOW · ANÁLISIS |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/workflow_bootstrap_repo_first.md:1` | WORKFLOW · BOOTSTRAP REPO-FIRST |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/workflow_cambio_sistemico.md:1` | WORKFLOW · CAMBIO SISTÉMICO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/workflow_cross_learning.md:1` | workflow_cross_learning · Transferencia de Conocimiento Entre Proyectos |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/workflow_diseno.md:1` | WORKFLOW · DISEÑO |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/workflow_ejecucion.md:1` | WORKFLOW · EJECUCIÓN |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/workflow_migracion_historial.md:1` | WORKFLOW · MIGRACIÓN DE HISTORIAL |
| 02-framework | Coordinacion y preparacion | `backend/.bago/core/workflows/workflow_validacion.md:1` | WORKFLOW · VALIDACIÓN |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/workspace_binding.py:2` | workspace_binding.py - canonical workspace/project/framework binding. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/workspace_patch_storage.py:1` | Materialize authorized workspace patch batches and recover their snapshots. |
| 02-framework | Soporte y procedimiento | `backend/.bago/core/world_state_snapshot.py:1` | Canonical world-state snapshot used by governed material effects. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/__init__.py:1` | Fuente .py; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/_chk_handlers.py:1` | Fuente .py; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/api_auth.py:1` | api_auth.py — auth + CORS helpers for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/api_dispatch.py:1` | api_dispatch.py — HTTP routing for the BAGO API bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/api_response.py:1` | Stable JSON response envelopes for BAGO API handlers. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/api_routes.py:1` | api_routes.py — Indice vivo de rutas del bridge BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/api_serializers.py:1` | api_serializers.py — JSON serialization helpers for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/api_state.py:1` | api_state.py — shared state-root resolution for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/apply_release_update.ps1:194` | This check is deliberately outside the effect try/catch. An unauthorized |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/auto_configurator.py:1` | auto_configurator.py — Genera configuración personalizada por usuario |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/blacklist_models.py:1` | blacklist_models.py — Blocklist de modelos por máquina (no global). |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/bridge.py:2` | api_bridge.py — BAGO HTTP API Bridge |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/capability_contract.py:1` | Contrato backend de Anatomía de capacidades BAGO v0.2. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/chat_turns.py:1` | Process-local chat operation identity; retries never create another turn. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/control_shadow.py:2` | control_shadow.py — Simulación segura del bus de control compartido. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/error_payload_filter.py:1` | error_payload_filter.py — Detect and rewrite BAGO's internal error payload. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/event_bus.py:1` | event_bus.py — Minimal in-process pub/sub for UI live updates. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handler_support.py:1` | handler_support.py — Shared helpers for BAGO API handlers. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_agents.py:1` | handlers_agents.py — CRUD API for configurable agents (AgentFactory + AgentGateway). |
| 02-framework | Evaluacion y diagnostico | `backend/.bago/api/handlers_audit.py:1` | handlers_audit.py - Project and runtime audit endpoints for BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_auto_config.py:1` | handlers_auto_config.py — Endpoints REST para /configure/auto/* |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_capabilities.py:1` | GET read-only de Anatomía de capacidades. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_capability_packages.py:1` | HTTP lifecycle for user-installed Capability Packages. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_catalog.py:1` | handlers_catalog.py — catalog mode endpoints for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_chat.py:1` | handlers_chat.py — POST /chat for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_chat_stream.py:1` | POST /chat/stream: incremental SSE backed by shared per-manager turn admission. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_command.py:1` | handlers_command.py — POST /command for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_context_attach.py:1` | Explicit authorization endpoint for materializing a session context bundle. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_conversations.py:1` | GET/POST /conversations - conversaciones persistentes de la sesión activa. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_desktop.py:1` | Loopback desktop diagnostics forwarded to the canonical structured logger. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_events.py:1` | handlers_events.py — GET /api/v1/events (Server-Sent Events). |
| 02-framework | Verificacion y evidencia | `backend/.bago/api/handlers_evidence.py:1` | handlers_evidence.py - Evidence endpoints for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_files.py:1` | handlers_files.py — file listing + read endpoints for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_github.py:1` | GitHub capabilities exposed to the UI through the authenticated gh CLI. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_health.py:1` | handlers_health.py — GET /health for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_history.py:1` | handlers_history.py — GET /history for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_install.py:1` | Direct-user authorization for one prepared system installation. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_interpret.py:1` | handlers_interpret.py - Reflexive Interpreter API endpoints. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_interpretations.py:1` | handlers_interpretations.py — Interpretation entity endpoints. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_jobs.py:1` | handlers_jobs.py - Pipeline/job endpoints for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_kv.py:1` | Versioned key/value integration API backed by the canonical state root. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_manager_settings.py:1` | Challenge/approve/execute facade for bounded Electron manager settings. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_memory.py:1` | handlers_memory.py — GET /memory/list[?scope=...] for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_menu.py:1` | handlers_menu.py - GET /menu for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_models.py:1` | handlers_models.py — GET /models/<provider> for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_process.py:1` | Desktop-confirmed process execution through the canonical Gateway. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_project.py:1` | handlers_project.py - Real HTTP endpoints for project/workspace control. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_project_patch.py:1` | Explicit authorization boundary for atomic workspace patch application. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_provider_buffer.py:3` | handlers_provider_buffer.py -- Provider buffer management endpoints. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_providers.py:1` | handlers_providers.py — GET /providers + POST /providers/configure. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_release.py:1` | Endpoints de actualización integrada. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_release_jobs.py:1` | Release-job operations dispatched through the canonical execution gateway. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_rl.py:1` | handlers_rl.py — RLBridge endpoints for the BAGO HTTP bridge. |
| 02-framework | Coordinacion y preparacion | `backend/.bago/api/handlers_router.py:1` | handlers_router.py — GET /router/list[?refresh=1] for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_routes.py:1` | handlers_routes.py — GET /routes para el bridge BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_schedule.py:1` | Governed schedule CRUD and delegated execution handlers. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_session.py:1` | handlers_session.py — GET /session for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_sessions.py:1` | GET/POST /sessions - recuperación real de sesiones persistentes. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_simulation.py:1` | handlers_simulation.py — ControlShadow endpoints for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_status.py:1` | handlers_status.py — GET /status for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_subagents.py:1` | GET /subagents/catalogue backed by the canonical roles manifest. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_switch.py:1` | handlers_switch.py — POST /switch for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_ui_bootstrap.py:1` | handlers_ui_bootstrap.py - GET /api/v1/ui/bootstrap for modern clients. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_vision.py:1` | handlers_vision.py — POST /vision for the BAGO HTTP bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_workspace.py:1` | handlers_workspace.py - Workspace authority endpoints for BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/handlers_workspace_conversation.py:1` | Keep chat history scoped to the confirmed workspace. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/legacy_aliases.py:3` | legacy_aliases.py -- Aliases para rutas legacy/obsoletas del frontend. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/provider_catalog.py:1` | Canonical provider descriptors shared by API handlers and UI payloads. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/rate_limit.py:1` | rate_limit.py — Token-bucket rate limiter per provider for the BAGO API bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/request_context.py:1` | request_context.py — shared per-request state for legacy chat/command/switch. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/secret_store.py:1` | Compatibility facade for the backend-owned secret store. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/structured_log.py:1` | structured_log.py — JSON-structured logging with rotation for the BAGO bridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/api/update_manager.py:1` | Actualizador integrado de BAGO basado en GitHub Releases. |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/__init__.py:1` | Fuente .py; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/command_utils.py:7` | Fuente Python; simbolo load_tool_module (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/commands.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/context_commands.py:18` | Fuente Python; simbolo cmd_context (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/memory_commands.py:6` | Fuente Python; simbolo cmd_memory (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/project_commands.py:17` | Fuente Python; simbolo _same_path (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/renderer.py:2` | renderer.py — BAGO Chat Visual Renderer |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/repl.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/repl_history.py:1` | Server-owned persistence adapters for interactive REPL history. |
| 02-framework | Observacion y conocimiento | `backend/.bago/chat/repl_inventory.py:2` | Startup inventory helpers for the BAGO REPL. |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/repl_menu.py:2` | Menu y asistentes del REPL de BAGO, extraidos de repl.py. |
| 02-framework | Coordinacion y preparacion | `backend/.bago/chat/repl_model_router.py:1` | repl_model_router.py — Model routing for BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/repl_startup.py:1` | repl_startup.py — Mixin de arranque, input y navegación para BagoREPL. |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/repl_utils.py:1` | repl_utils.py — Utilidades libres para el REPL de BAGO. |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/system_prompt.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/system_prompt_base.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Verificacion y evidencia | `backend/.bago/chat/system_prompt_evidence.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/system_prompt_format.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/system_prompt_identity.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/system_prompt_manifest.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/system_prompt_understanding.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/system_prompt_workspace.md:1` | Fuente .md; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/chat/tool_approval_commands.py:6` | Fuente Python; simbolo _normalize_tool_approval_mode (comportamiento no ejecutado) |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/__init__.py:1` | Fuente .py; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/anthropic.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/cli_bridge.py:1` | Safe non-interactive helpers shared by CLI-backed provider adapters. |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/codex.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/copilot.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/cpp_local.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/ollama_cloud.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/ollama_local.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/providers/opencode.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Coordinacion y preparacion | `backend/.bago/providers/openrouter.py:2` | _CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/__init__.py:1` | BagoPiBridge — paquete en cuarentena (Sprint 1 / Fase 0). |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/agent_runner.py:1` | agent_runner.py — Fase 3: agent runner con captura completa. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/ARQ-v0.3-separacion-autoridad.md:1` | BagoPiBridge — ARQ v0.3 · Separación de autoridad BAGO↔PI |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/attestation.py:1` | attestation.py — Fase 1: provider/model/endpoint attestation. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/CHANGELOG.md:1` | BagoPiBridge — CHANGELOG |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/config.py:1` | config.py — carga de configuración del BagoPiBridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/contracts.py:1` | contracts.py — modelos validados del protocolo BagoPiBridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/CRIT-v0.3-separacion-autoridad.md:1` | BagoPiBridge — CRIT v0.3 · Revisión del ARQ v0.3 |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/diagnostics.py:1` | diagnostics.py — estado de cuarentena y capacidades activas. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/errors.py:1` | errors.py — códigos de error estables del BagoPiBridge. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/event_capture.py:1` | event_capture.py — captura, numeración y hash encadenado de eventos. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/identity_paths.py:1` | Injective, Windows-safe path components for PI execution artifacts. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/mutation_gate.py:1` | mutation_gate.py — denegador explícito de mutaciones. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/PLAN-v0.3-separacion-autoridad.md:1` | BagoPiBridge — PLAN v0.3 · Implementación de la separación de autoridad |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/policy_gate.py:1` | policy_gate.py — matriz de capacidades del BagoPiBridge. |
| 02-framework | Coordinacion y preparacion | `backend/.bago/integrations/pi/preflight.py:1` | preflight.py — validación de una petición antes de invocar al sidecar. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/process_boundary.py:1` | process_boundary.py — frontera de proceso con el sidecar. |
| 02-framework | Autoridad y limites | `backend/.bago/integrations/pi/protocol.py:1` | protocol.py — serialización JSONL, validación de orden y límites. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/provider_adapter.py:1` | provider_adapter.py — `BagoPiProviderAdapter`. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/readonly_tool_proxy.py:1` | readonly_tool_proxy.py — proxy BAGO de tools de solo lectura. |
| 02-framework | Coordinacion y preparacion | `backend/.bago/integrations/pi/receipt_factory.py:1` | receipt_factory.py — emite `ContextReceipt` canónico y `ToolReceipt` local. |
| 02-framework | Verificacion y evidencia | `backend/.bago/integrations/pi/scope_validator.py:1` | scope_validator.py — validación de rutas contra `workspace_scope_root`. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/sidecar/package-lock.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/sidecar/package.json:1` | Fuente .json; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/sidecar/src/main.js:1` | Fuente .js; contenido de referencia |
| 02-framework | Autoridad y limites | `backend/.bago/integrations/pi/sidecar/src/protocol.js:1` | Fuente .js; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/sidecar/src/provider_attestation.js:1` | Fuente .js; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/sidecar/src/provider_runner.js:1` | Fuente .js; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/sidecar/src/runtime_guard.js:1` | Fuente .js; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/sidecar/src/tool_rpc.js:1` | Fuente .js; contenido de referencia |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/tool_event_flow.py:1` | tool_event_flow.py — orquesta el ciclo tool_requested → tool_result_attached. |
| 02-framework | Soporte y procedimiento | `backend/.bago/integrations/pi/wal.py:1` | wal.py — Write-Ahead Log para el bridge. |
| 02-framework | Continuidad y runtime | `backend/.bago/bin/bago.py:2` | Canonical BAGO runtime wrapper. |
| 02-framework | Soporte y procedimiento | `backend/.bago/tools.manifest.json:1` | Fuente .json; contenido de referencia |
| 03-integrations-review | Integracion y transporte | `backend/.bago/mcp/agent_tool_matrix.json:1` | Fuente .json; contenido de referencia |
| 03-integrations-review | Integracion y transporte | `backend/.bago/mcp/bago_mcp_server.py:3` | bago_mcp_server.py — MCP readonly bridge for BAGO. |
| 03-integrations-review | Integracion y transporte | `backend/.bago/mcp/mcp_config.json:1` | Fuente .json; contenido de referencia |
| 03-integrations-review | Integracion y transporte | `backend/.bago/mcp/run_bago_mcp.cmd:1` | Fuente .cmd; contenido de referencia |
| 03-integrations-review | Integracion y transporte | `backend/.bago/mcp/toolbox_catalog.json:1` | Fuente .json; contenido de referencia |
| 03-integrations-review | Integracion y transporte | `backend/.bago/extensions/bash-runner/extension.mjs:1` | Fuente .mjs; contenido de referencia |
| 03-integrations-review | Integracion y transporte | `.github/hooks/bago-runtime.json:1` | Fuente .json; contenido de referencia |
| 03-integrations-review | Integracion y transporte | `.github/hooks/bago_hook.py:15` | Fuente Python; simbolo utcnow (comportamiento no ejecutado) |
| 03-integrations-review | Integracion y transporte | `.github/plugin/marketplace.json:1` | Fuente .json; contenido de referencia |
| 03-integrations-review | Soporte y procedimiento | `plugins/bago-github-admin/.mcp.json:1` | Fuente .json; contenido de referencia |
| 03-integrations-review | Integracion y transporte | `plugins/bago-github-admin/mcp/github_repository_admin.py:21` | Fuente Python; simbolo token_from_environment (comportamiento no ejecutado) |
| 03-integrations-review | Soporte y procedimiento | `plugins/bago-github-admin/plugin.json:1` | Fuente .json; contenido de referencia |
| 03-integrations-review | Soporte y procedimiento | `plugins/bago-github-admin/skills/github-repository-admin/SKILL.md:3` | Create a GitHub repository through the BAGO GitHub Admin MCP when the user explicitly requests repository creation. Verify the created repository identity before making a verified claim. |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_architecture_auditor.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_backend_auditor.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Observacion y conocimiento | `.codex/agents/bago_code_mapper.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_contracts_auditor.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Verificacion y evidencia | `.codex/agents/bago_final_verifier.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_frontend_auditor.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_hygiene_scanner.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Intervencion | `.codex/agents/bago_implementation_worker.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Intervencion | `.codex/agents/bago_mechanical_worker.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_performance_auditor.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Soporte y procedimiento | `.codex/agents/bago_refactor_planner.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Observacion y conocimiento | `.codex/agents/bago_repo_explorer.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_security_auditor.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_test_auditor.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/agents/bago_truth_auditor.toml:1` | Fuente .toml; contenido de referencia |
| 04-other-harnesses | Autoridad y limites | `.codex/bago-workpack/COMMON_RULES.md:1` | BAGO CODEX WORKPACK — REGLAS COMUNES |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/List-Tasks.ps1:1` | Fuente .ps1; contenido de referencia |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/manifest.json:1` | Fuente .json; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.codex/bago-workpack/Run-Audit.ps1:1` | Fuente .ps1; contenido de referencia |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/Run.ps1:1` | Fuente .ps1; contenido de referencia |
| 04-other-harnesses | Coordinacion y preparacion | `.codex/bago-workpack/tasks/00-preflight.md:1` | Fijar objeto auditado |
| 04-other-harnesses | Observacion y conocimiento | `.codex/bago-workpack/tasks/01-inventory.md:1` | Inventario completo |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/02-architecture.md:1` | Arquitectura real y God Components |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/03-frontend.md:1` | Frontend completo |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/04-backend.md:1` | Backend completo |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/05-contracts.md:1` | Contratos frontend-backend |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/06-workspace.md:1` | Workspace en profundidad |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/07-features.md:1` | Agents, Interpreter y GitHub |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/08-security.md:1` | Seguridad y trust boundaries |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/09-tests-ci.md:1` | Tests, build, CI y runtime |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/10-hygiene.md:1` | Dead code, legacy, dependencias, CSS y docs |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/11-performance.md:1` | Performance |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/12-truth-authority.md:1` | Estado, evidencia y verdad operacional |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/13-synthesis.md:1` | Síntesis integral |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/14-refactor-plan.md:1` | Plan de corrección por PR |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/20-implement-approved-pr.md:1` | Implementar PR aprobado |
| 04-other-harnesses | Soporte y procedimiento | `.codex/bago-workpack/tasks/21-mechanical-approved.md:1` | Cambio mecánico aprobado |
| 04-other-harnesses | Verificacion y evidencia | `.codex/bago-workpack/tasks/22-verify-change.md:1` | Verificación independiente |
| 04-other-harnesses | Intervencion | `.codex/bago-remediation/README.md:1` | BAGO 15-point governed remediation |
| 04-other-harnesses | Intervencion | `.codex/bago-remediation/remediation-plan.json:1` | Fuente .json; contenido de referencia |
| 04-other-harnesses | Intervencion | `.codex/bago-remediation/Run-Remediation.ps1:338` | Bind every candidate to this exact trusted plan snapshot: the implementation |
| 04-other-harnesses | Intervencion | `.codex/bago-remediation/VerificationVerdict.psm1:1` | Fuente .psm1; contenido de referencia |
| 04-other-harnesses | Evaluacion y diagnostico | `.agents/skills/bago-auditors/SKILL.md:3` | Read-only audit swarm for BAGO. Use when asked to review architecture, backend routes, frontend React/state, contracts, security, performance, tests, hygiene, or truth/evidence. Pass the audit mode as the first argument. |
| 04-other-harnesses | Verificacion y evidencia | `.agents/skills/bago-final-verifier/SKILL.md:3` | Independent final verification of BAGO changes and closures. Use after implementation or before release to review diffs and evidence, looking for regressions, broken contracts, insufficient tests, scope creep, and unsupp |
| 04-other-harnesses | Intervencion | `.agents/skills/bago-workers/SKILL.md:3` | Implementation skill for BAGO. Use for approved, well-scoped PRs or mechanical, repetitive, fully-specified changes. Pass the mode as the first argument: implement or mechanical. |
| 04-other-harnesses | Soporte y procedimiento | `.pi/prompts/codex-models.md:2` | Switch Pi to the OpenAI provider and reasoning model used by Codex CLI |
| 04-other-harnesses | Integracion y transporte | `.pi/extensions/README.md:1` | Pi project-local extensions |
| 05-continuity-reference | Continuidad y runtime | `.bago/bin/bago.py:2` | BAGO runtime wrapper for the working tree. |
| 05-continuity-reference | Soporte y procedimiento | `.bago/bin/screenshot-help.cjs:1` | Fuente .cjs; contenido de referencia |
| 05-continuity-reference | Soporte y procedimiento | `.bago/bin/screenshot-home.cjs:1` | Fuente .cjs; contenido de referencia |
| 05-continuity-reference | Soporte y procedimiento | `.bago/bin/screenshot-panel.cjs:1` | Fuente .cjs; contenido de referencia |
| 05-continuity-reference | Verificacion y evidencia | `.bago/bin/verify-backend.cmd:1` | Fuente .cmd; contenido de referencia |
| 06-documentation | Produccion de artefactos | `.github/copilot-kit/build_pack.py:1` | Build a reviewed-source snapshot without activating any integration. |
| 06-documentation | Soporte y procedimiento | `.github/copilot-kit/INTEGRATION_PLAN.md:1` | BAGO Copilot CLI: pack e integracion |
| 06-documentation | Soporte y procedimiento | `.github/copilot-kit/README.md:1` | BAGO toolkit for GitHub Copilot CLI |
| 06-documentation | Produccion de artefactos | `.github/copilot-kit/test_build_pack.py:1` | Packaging selection and output contract tests; no BAGO capabilities run. |
| 06-documentation | Soporte y procedimiento | `LICENSE:1` | Fuente ; contenido de referencia |
