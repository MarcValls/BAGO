# BAGO Command Audit — Clasificación completa


Generado automáticamente desde tool_registry.py.
Clasificación basada en: estabilidad, riesgo y uso previsto.

---

## CORE — Interfaz pública estable (12 comandos)

Requieren: test, preflight, documentación, salida clara.

| Comando | Módulo | Descripción | Risk |
|---------|--------|-------------|------|
| `bago audit` | bago_audit_router | Auditoría y calidad: full | pack | scan | commit | push | do... | safe |
| `bago context` | bago_context | Contexto del workspace: detect | map | git | stale | safe |
| `bago flow` | flow | Flowchart ASCII de workflows + gestión de estado activo (sta... | safe |
| `bago health` | bago_health_router | Salud del framework: score | report | stability | efficiency... | safe |
| `bago project` | project_memory | Memoria distribuida por proyecto: init | link | unlink | sta... | safe |
| `bago scope` | scope_detector | Detecta scope (framework/project/both) de scripts Python por... | safe |
| `bago secrets` | secret_scan | Escanea el repositorio buscando secretos y credenciales expu... | safe |
| `bago session` | bago_session_router | Ciclo de sesión: open | close | harvest | v2 | safe |
| `bago status` | flow | Estado actual: flujo activo, tarea pendiente y salud del sis... | safe |
| `bago sync` | sync_pack_metadata | Regenera TREE.txt y CHECKSUMS | safe |
| `bago task` | show_task | Muestra la tarea W2 pendiente | safe |
| `bago validate` | validate_pack | Verifica el pack (solo lectura) | safe |

---

## DANGEROUS — Requieren --yes o --unsafe (7 comandos)

Nunca ejecutan sin confirmación explícita. Nunca por autonomous sin --unsafe.

| Comando | Módulo | Descripción | Risk |
|---------|--------|-------------|------|
| `bago auto` | auto_mode | Modo automático: evalúa y actúa. --loop para bucle, --infini... | dangerous |
| `bago autonomous` | autonomous_loop | Loop autónomo BAGO: SENSE→PLAN→ACT→OBSERVE→LEARN→DECIDE [--d... | dangerous |
| `bago cabinet` | cabinet_orchestrator | Gabinete BAGO: orquesta agentes en paralelo e informa unific... | dangerous |
| `bago db` | bago_db | Gestiona bago.db: estado de ideas, historial guardian, init/... | dangerous |
| `bago install` | bago_install | Auto-lanzamiento al insertar el pendrive (macOS/Linux/Window... | dangerous |
| `bago orchestrate` | orchestrator | Orquestador de workflows multi-tool en secuencia con condici... | dangerous |
| `bago peer` | peer_link | Comunicacion peer-to-peer LAN (serve/discover/ping/send/chat... | dangerous |

---

## EXPERIMENTAL (30 comandos)

Pueden cambiar. No forman parte del quickstart. No bloquean instalación.

| Comando | Módulo | Descripción | Risk |
|---------|--------|-------------|------|
| `bago ask` | intent_router | Router lenguaje natural → tools BAGO | safe |
| `bago chronicle` | chronicle_reporter | Sesión Chronicle integrando Copilot CLI /chronicle — histori... | safe |
| `bago config-check` | config_check | Valida integridad de configs JSON en state/config/ y cruza c... | safe |
| `bago dashboard` | pack_dashboard | Muestra el dashboard del pack | safe |
| `bago debt` | debt_ledger | Ledger de deuda técnica — registra, prioriza y hace seguimie... | safe |
| `bago deps` | dep_audit | Auditoría de dependencias (requirements/pyproject) | safe |
| `bago diff` | bago_diff | Muestra ficheros modificados entre las últimas sesiones BAGO | safe |
| `bago find-tool` | tool_search | Busca la herramienta BAGO adecuada para un problema | safe |
| `bago goals` | goals | Gestor de objetivos del pack con seguimiento de progreso | safe |
| `bago habit` | habit | Detecta hábitos de trabajo positivos y mejorables desde patr... | safe |
| `bago ideas` | emit_ideas | Emite ideas W2 | safe |
| `bago image-studio` | image_studio | Generador de assets visuales coherentes (sprites, botones, f... | safe |
| `bago image_gen` | image_gen | Generador de imagenes PNG local sin API | safe |
| `bago inbox` | autonomous_loop | Inbox de tareas autónomas: add <intent> | list | clear | safe |
| `bago insights` | insights | Análisis de patrones e insights del historial de sesiones BA... | safe |
| `bago llm` | bago_llm | Motor LLM local offline: modelos GGUF en pendrive via Ollama... | safe |
| `bago lsp` | lsp_manager | Orquestación de Language Servers — registra y gestiona servi... | safe |
| `bago naming` | naming_check | Lint de convenciones de nombres | safe |
| `bago next` | bago_next | Meta-comando de ciclo mínimo: elige idea + acepta + inicia f... | safe |
| `bago reopen` | bago_reopen | Reanuda sesión desde el último cierre sin reconstruir contex... | safe |
| `bago repo` | bago_repo | Gestión de repositorios: clone | list | switch | safe |
| `bago research` | research_orchestrator | Modo Research integrando GitHub Copilot CLI /research — inve... | safe |
| `bago review` | code_review | Code review automatizado — analiza cambios y genera feedback | safe |
| `bago risk` | risk_matrix | Matriz de riesgo del proyecto — evalúa impacto y probabilida... | safe |
| `bago rules` | rule_catalog | Catálogo de reglas BAGO | safe |
| `bago select` | ideas_selector | Selector interactivo de ideas por slot con plan de implement... | safe |
| `bago sprint` | sprint_manager | Gestor de sprints BAGO — crear, listar, cerrar sprints de tr... | safe |
| `bago sprite-studio` | sprite_studio | Generador de sprites BIANCA via Codex/HF sin API key, con ga... | safe |
| `bago types` | type_check | Chequeo de tipos estáticos | safe |
| `bago why` | why | Explica qué hace un comando BAGO, cuándo usarlo y sus relaci... | safe |
| `bago workflow` | workflow_selector | Selector de workflow (interactivo) | safe |

---

## INTERNAL — No user-facing (5 comandos)

| Comando | Módulo | Descripción | Risk |
|---------|--------|-------------|------|
| `bago banner` | bago_banner | Muestra el banner animado de BAGO con estado actual | safe |
| `bago done` | show_task | Cierra la tarea actual y muestra el siguiente paso sugerido | safe |
| `bago hello` | bago_hello | Guía de inicio para nuevos usuarios y recordatorio de comand... | safe |
| `bago hub` | bago_hub | BAGO Hub — interfaz central Gradio con dashboard, herramient... | safe |
| `bago start` | bago_start | Entrada rápida al repo: health + top ideas + aceptar tarea a... | safe |

---

## LEGACY — Deprecated (28 comandos)

Solo redirigen. No se desarrollan. Se eliminarán en versión futura.

| Comando | Reemplazado por | Módulo |
|---------|----------------|--------|
| `bago check` | `bago audit purity` | check_validate_purity |
| `bago code-quality` | `bago audit quality` | code_quality_orchestrator |
| `bago commit` | `bago audit commit` | commit_readiness |
| `bago consistency` | `bago health consistency` | bago_consistency_check |
| `bago cosecha` | `bago session harvest` | cosecha |
| `bago detector` | `bago context detect` | context_detector |
| `bago doctor` | `bago audit doctor` | bago_doctor |
| `bago efficiency` | `bago health efficiency` | efficiency_meter |
| `bago git` | `bago context git` | git_context |
| `bago heal` | `bago audit heal` | auto_heal |
| `bago learn` | `bago project learn` | project_memory |
| `bago map` | `bago context map` | context_map |
| `bago pre-push` | `bago audit push` | pre_push_guard |
| `bago project-init` | `bago project init` | project_memory |
| `bago project-link` | `bago project link` | project_memory |
| `bago project-state` | `bago project state` | project_memory |
| `bago project-unlink` | `bago project unlink` | project_memory |
| `bago promote` | `bago project promote` | project_memory |
| `bago repo-clone` | `bago repo clone` | repo_clone |
| `bago repo-list` | `bago repo list` | repo_list |
| `bago repo-switch` | `bago repo switch` | repo_switch |
| `bago report` | `bago health report` | health_report |
| `bago scan` | `bago audit scan` | scan |
| `bago session_close` | `bago session close` | session_close_generator |
| `bago sincerity` | `bago health sincerity` | sincerity_detector |
| `bago stability` | `bago health stability` | stability_summary |
| `bago stale` | `bago context stale` | stale_detector |
| `bago v2` | `bago session v2` | v2_close_checklist |

---

## Resumen

| Categoría | Cantidad |
|-----------|---------|
| core | 12 |
| dangerous | 7 |
| experimental | 31 |
| internal | 5 |
| legacy | 28 |
| **TOTAL** | **83** |

### Duplicados detectados

Los siguientes módulos tienen múltiples alias registrados (posible duplicación):

- `autonomous_loop`: autonomous / inbox
- `flow`: flow / status
- `project_memory`: learn / project / project-init / project-link / project-state / project-unlink / promote
- `show_task`: done / task
