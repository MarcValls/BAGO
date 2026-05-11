"""_registry_entries.py — Canonical REGISTRY dict of all BAGO tools.

This is the single source of truth for tool definitions.
Add new tools here; auto_register.py will append entries automatically.

Internal module: import via tool_registry, not directly.
"""
from __future__ import annotations

from _registry_models import PreflightCheck, ToolEntry
from _registry_paths import BAGO_ROOT, TOOLS_DIR

# ── Canonical registry ─────────────────────────────────────────────────────────

REGISTRY: dict[str, ToolEntry] = {
    "dashboard": ToolEntry(
        cmd="dashboard", module="pack_dashboard",
        description="Muestra el dashboard del pack",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "pack_dashboard.py"))],
    ),
    "ideas": ToolEntry(
        cmd="ideas", module="emit_ideas",
        description="Emite ideas W2",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "emit_ideas.py"))],
    ),
    "cosecha": ToolEntry(
        cmd="cosecha", module="cosecha",
        description="Cosecha de artefactos del proyecto",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "cosecha.py"))],
        deprecated=True, see_also="bago session harvest",
    ),
    "detector": ToolEntry(
        cmd="detector", module="context_detector",
        description="Detector de contexto del repo",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "context_detector.py"))],
        deprecated=True, see_also="bago context detect",
    ),
    "validate": ToolEntry(
        cmd="validate", module="validate",
        description="Verifica el pack (manifiesto, estado, roles, ZIP) — subcomandos: manifest, state, contents",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "validate.py"))],
    ),
    "docs": ToolEntry(
        cmd="docs", module="generate_commands_doc",
        description="Genera docs/COMMANDS.md desde tool_registry.py (fuente única de verdad)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "generate_commands_doc.py"))],
        layer="calidad", scope="framework",
    ),
    "doc-agent": ToolEntry(
        cmd="doc-agent", module="doc_agent",
        description=(
            "Agente de documentación: detecta y actualiza COMMANDS.md, LAYERS.md y README.md. "
            "Subcomandos/flags: --check | --dry-run | --json | --only <doc> | --no-stage"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "doc_agent.py"))],
        layer="calidad",
        scope="framework",
        agent="CENTINELA",
        stability="core",
        risk="mutating",
        preflight_policy="required",
        supports_dry_run=True,
        layer_group="core",
    ),
    "sync": ToolEntry(
        cmd="sync", module="sync_pack_metadata",
        description="Regenera TREE.txt y CHECKSUMS",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "sync_pack_metadata.py"))],
    ),
    "check": ToolEntry(
        cmd="check", module="check_validate_purity",
        description="Chequeo estático de pureza",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "check_validate_purity.py"))],
        deprecated=True, see_also="bago audit purity",
    ),
    "health": ToolEntry(
        cmd="health", module="health",
        description="Salud del framework: score | report | stability | efficiency | consistency | sincerity",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "health" / "__main__.py"))],
    ),
    "audit": ToolEntry(
        cmd="audit", module="audit",
        description="Auditoría y calidad: full | pack | scan | commit | push | doctor | heal | quality | purity",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "audit" / "__main__.py"))],
    ),
    "version": ToolEntry(
        cmd="version", module="bago_version",
        description="Gestión de versiones beta/release: bump | beta | release | tag | commit | sync-check",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_version.py"))],
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
    ),
    "workflow": ToolEntry(
        cmd="workflow", module="workflow_selector",
        description="Selector de workflow (interactivo)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "workflow_selector.py"))],
    ),
    "stale": ToolEntry(
        cmd="stale", module="stale_detector",
        description="Detecta tools obsoletas o sin mantenimiento",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "stale_detector.py"))],
        deprecated=True, see_also="bago context stale",
    ),
    "v2": ToolEntry(
        cmd="v2", module="v2_close_checklist",
        description="Checklist de cierre v2",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "v2_close_checklist.py"))],
        deprecated=True, see_also="bago session v2",
    ),
    "task": ToolEntry(
        cmd="task", module="show_task",
        description="Muestra la tarea W2 pendiente",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "show_task.py"))],
    ),
    "stability": ToolEntry(
        cmd="stability", module="stability_summary",
        description="Resumen de estabilidad del pack",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "stability_summary.py"))],
        deprecated=True, see_also="bago health stability",
    ),
    "session": ToolEntry(
        cmd="session", module="session",
        description="Ciclo de sesión: open | close | harvest | v2",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "session" / "__main__.py"))],
    ),
    "efficiency": ToolEntry(
        cmd="efficiency", module="efficiency_meter",
        description="Medidor de eficiencia inter-versiones",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "efficiency_meter.py"))],
        deprecated=True, see_also="bago health efficiency",
    ),
    "sincerity": ToolEntry(
        cmd="sincerity", module="sincerity_detector",
        description="Centinela de sinceridad: detecta sincofancía en docs .md",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "sincerity_detector.py"))],
        deprecated=True, see_also="bago health sincerity",
    ),
    "scope": ToolEntry(
        cmd="scope", module="scope_detector",
        description="Detecta scope (framework/project/both) de scripts Python por análisis estático",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "scope_detector.py"))],
    ),
    "cabinet": ToolEntry(
        cmd="cabinet", module="cabinet_orchestrator",
        description="Gabinete BAGO: orquesta agentes en paralelo e informa unificado",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "cabinet_orchestrator.py"))],
    ),
    # ── Importadas desde BAGO_CAJAFISICA (evaluadas OK, cubren gaps reales) ──
    "git": ToolEntry(
        cmd="git", module="git_context",
        description="Contexto git (log/diff/brief) para workflows",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "git_context.py"))],
        deprecated=True, see_also="bago context git",
    ),
    "deps": ToolEntry(
        cmd="deps", module="dep_audit",
        description="Auditoría de dependencias (requirements/pyproject)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "dep_audit.py"))],
    ),
    "naming": ToolEntry(
        cmd="naming", module="naming_check",
        description="Lint de convenciones de nombres",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "naming_check.py"))],
    ),
    "types": ToolEntry(
        cmd="types", module="type_check",
        description="Chequeo de tipos estáticos",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "type_check.py"))],
    ),
    "map": ToolEntry(
        cmd="map", module="context_map",
        description="Mapa de contexto del repositorio",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "context_map.py"))],
        deprecated=True, see_also="bago context map",
    ),
    "report": ToolEntry(
        cmd="report", module="health",
        description="Health report en Markdown",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "health" / "__main__.py"))],
        deprecated=True, see_also="bago health report",
    ),
    "commit": ToolEntry(
        cmd="commit", module="commit_readiness",
        description="Evaluación de preparación para commit",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "commit_readiness.py"))],
        deprecated=True, see_also="bago audit commit",
    ),
    "flow": ToolEntry(
        cmd="flow", module="flow",
        description="Flowchart ASCII de workflows + gestión de estado activo (start/done/status)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "flow.py"))],
    ),
    "find-tool": ToolEntry(
        cmd="find-tool", module="tool_search",
        description="Busca la herramienta BAGO adecuada para un problema",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "tool_search.py"))],
    ),
    "ask": ToolEntry(
        cmd="ask", module="intent_router",
        description="Router lenguaje natural → tools BAGO",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "intent_router.py"))],
    ),
    "rules": ToolEntry(
        cmd="rules", module="rule_catalog",
        description="Catálogo de reglas BAGO",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "rule_catalog.py"))],
    ),
    "peer": ToolEntry(
        cmd="peer", module="peer_link",
        description="Comunicacion peer-to-peer LAN (serve/discover/ping/send/chat)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "peer_link.py"))],
    ),
    "banner": ToolEntry(
        cmd="banner", module="bago_banner",
        description="Muestra el banner animado de BAGO con estado actual",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_banner.py"))],
    ),
    "session_close": ToolEntry(
        cmd="session_close", module="session",
        description="Genera el informe de cierre de sesion BAGO",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "session" / "__main__.py"))],
        deprecated=True, see_also="bago session close",
    ),
    "reopen": ToolEntry(
        cmd="reopen", module="bago_reopen",
        description="Reanuda sesión desde el último cierre sin reconstruir contexto manualmente",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_reopen.py"))],
    ),
    "image_gen": ToolEntry(
        cmd="image_gen", module="image_gen",
        description="Generador de imagenes PNG local sin API",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "image_gen.py"))],
    ),
    "ableton-template": ToolEntry(
        cmd="ableton-template", module="ableton_template",
        description="Genera un scaffold de proyecto Ableton techno 4/4",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "ableton_template.py"))],
        layer="visual", scope="project", agent="GENERADOR",
    ),
    "code-quality": ToolEntry(
        cmd="code-quality", module="code_quality_orchestrator",
        description="Orquestador de calidad de código — ejecuta agentes especializados",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "code_quality_orchestrator.py")),
            PreflightCheck("file", str(BAGO_ROOT / "agents" / "ANALISTA_Contexto.md"),
                           severity="warning", message="Agente ANALISTA_Contexto no encontrado en .bago/agents/"),
        ],
        deprecated=True, see_also="bago audit quality",
    ),
    "consistency": ToolEntry(
        cmd="consistency", module="bago_consistency_check",
        description="Guard anti-drift: valida CI, preflight, README y badge del framework",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_consistency_check.py"))],
        deprecated=True, see_also="bago health consistency",
    ),
    "config-check": ToolEntry(
        cmd="config-check", module="config",
        description="Valida integridad de configs JSON en state/config/ y cruza con registry",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "config.py"))],
    ),
    "why": ToolEntry(
        cmd="why", module="why",
        description="Explica qué hace un comando BAGO, cuándo usarlo y sus relaciones",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "why.py"))],
    ),
    "db": ToolEntry(
        cmd="db", module="bago_db",
        description="Gestiona bago.db: estado de ideas, historial guardian, init/status/reset",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_db.py"))],
    ),
    "hello": ToolEntry(
        cmd="hello", module="bago_hello",
        description="Guía de inicio para nuevos usuarios y recordatorio de comandos esenciales",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_hello.py"))],
    ),
    "next": ToolEntry(
        cmd="next", module="bago_next",
        description="Meta-comando de ciclo mínimo: elige idea + acepta + inicia flujo en un paso",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_next.py"))],
    ),
    "diff": ToolEntry(
        cmd="diff", module="bago_diff",
        description="Muestra ficheros modificados entre las últimas sesiones BAGO",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_diff.py"))],
    ),
    "done": ToolEntry(
        cmd="done", module="show_task",
        description="Cierra la tarea actual y muestra el siguiente paso sugerido",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "show_task.py"))],
    ),
    "status": ToolEntry(
        cmd="status", module="flow",
        description="Estado actual: flujo activo, tarea pendiente y salud del sistema",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "flow.py"))],
    ),
    "install": ToolEntry(
        cmd="install", module="bago_install",
        description="Auto-lanzamiento al insertar el pendrive (macOS/Linux/Windows/Android/iPad)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_install.py"))],
    ),
    "llm": ToolEntry(
        cmd="llm", module="bago_llm",
        description="Motor LLM local offline: modelos GGUF en pendrive via Ollama (macOS/Linux/Windows)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_llm.py"))],
    ),
    "music": ToolEntry(
        cmd="music", module="bago_music",
        description=(
            "Pipeline musical (MarcValls/BAGO_MUSIC_PIPELINE): "
            "plan | convert | transpose | validate | render | run"
        ),
        preflight=[
            # Gate: router principal — error si falta
            PreflightCheck("file", str(TOOLS_DIR / "bago_music.py")),
            # Módulos de pipeline (external repo synced) — warning para degradación elegante
            PreflightCheck("file", str(TOOLS_DIR / "music_transpose_plan.py"),
                           severity="warning",
                           message="Módulo plan no encontrado — instala BAGO_MUSIC_PIPELINE o clona MarcValls/BAGO_MUSIC_PIPELINE"),
            PreflightCheck("file", str(TOOLS_DIR / "music_to_musicxml_pipeline.py"),
                           severity="warning",
                           message="Módulo convert no encontrado — instala BAGO_MUSIC_PIPELINE o clona MarcValls/BAGO_MUSIC_PIPELINE"),
            PreflightCheck("file", str(TOOLS_DIR / "musicxml_target_select.py"),
                           severity="warning",
                           message="Módulo inventory no encontrado — instala BAGO_MUSIC_PIPELINE o clona MarcValls/BAGO_MUSIC_PIPELINE"),
            PreflightCheck("file", str(TOOLS_DIR / "musicxml_transpose.py"),
                           severity="warning",
                           message="Módulo transpose no encontrado — instala BAGO_MUSIC_PIPELINE o clona MarcValls/BAGO_MUSIC_PIPELINE"),
            PreflightCheck("file", str(TOOLS_DIR / "musicxml_validate.py"),
                           severity="warning",
                           message="Módulo validate no encontrado — instala BAGO_MUSIC_PIPELINE o clona MarcValls/BAGO_MUSIC_PIPELINE"),
            PreflightCheck("file", str(TOOLS_DIR / "musicxml_render.py"),
                           severity="warning",
                           message="Módulo render no encontrado — instala BAGO_MUSIC_PIPELINE o clona MarcValls/BAGO_MUSIC_PIPELINE"),
        ],
        layer="avanzado",
        scope="project",
        agent="ARQUITECTO",
        stability="experimental",
        risk="safe",
        layer_group="labs",
        preflight_policy="optional",
    ),
    "route": ToolEntry(
        cmd="route", module="agent_router",
        description="Router hibrido balanceado/adaptativo: decide entre Ollama local, Codex y Copilot",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "agent_router.py"))],
        layer="avanzado",
        scope="both",
        agent="ARQUITECTO",
    ),
    "doctor": ToolEntry(
        cmd="doctor", module="bago_doctor",
        description="Diagnóstico completo del entorno BAGO: Python, Git, Ollama, modelo LLM, espacio",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_doctor.py"))],
        deprecated=True, see_also="bago audit doctor",
    ),
    "research": ToolEntry(
        cmd="research", module="research_orchestrator",
        description="Modo Research integrando GitHub Copilot CLI /research — investigación temática estructurada",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "research_orchestrator.py")),
            PreflightCheck("file", str(BAGO_ROOT / "state")),
        ],
    ),
    "chronicle": ToolEntry(
        cmd="chronicle", module="chronicle_reporter",
        description="Sesión Chronicle integrando Copilot CLI /chronicle — historial de sesiones y recomendaciones",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "chronicle_reporter.py")),
            PreflightCheck("file", str(BAGO_ROOT / "state")),
        ],
    ),
    "lsp": ToolEntry(
        cmd="lsp", module="lsp_manager",
        description="Orquestación de Language Servers — registra y gestiona servidores LSP para inteligencia de código",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "lsp_manager.py")),
            PreflightCheck("file", str(BAGO_ROOT / "state")),
        ],
    ),
    "repo-clone": ToolEntry(
        cmd="repo-clone", module="repo_clone",
        description="Clona repositorios GitHub en workspace con auto-BAGO setup",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "repo_clone.py"))],
        deprecated=True, see_also="bago repo clone",
    ),
    "repo-list": ToolEntry(
        cmd="repo-list", module="repo_list",
        description="Lista repositorios clonados en workspace con estado",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "repo_list.py"))],
        deprecated=True, see_also="bago repo list",
    ),
    "repo-switch": ToolEntry(
        cmd="repo-switch", module="repo_switch",
        description="Cambia contexto activo entre repositorios del workspace",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "repo_switch.py"))],
        deprecated=True, see_also="bago repo switch",
    ),
    "repo": ToolEntry(
        cmd="repo", module="repo",
        description="Gestión de repositorios: clone | list | switch",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "repo.py"))],
    ),
    "select": ToolEntry(
        cmd="select", module="ideas_selector",
        description="Selector interactivo de ideas por slot con plan de implementación",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "ideas_selector.py"))],
    ),
    "start": ToolEntry(
        cmd="start", module="bago_start",
        description="Entrada rápida al repo: health + top ideas + aceptar tarea activa",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_start.py"))],
    ),
    "pre-push": ToolEntry(
        cmd="pre-push", module="pre_push_guard",
        description="Gate de sincronizacion remota: bloquea pushes con BAGO roto",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "pre_push_guard.py"))],
        deprecated=True, see_also="bago audit push",
    ),
    "sprite-studio": ToolEntry(
        cmd="sprite-studio", module="sprite_studio",
        description="Generador de sprites BIANCA via Codex/HF sin API key, con galería browser",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "sprite_studio.py"))],
    ),
    "image-studio": ToolEntry(
        cmd="image-studio", module="image_studio",
        description="Generador de assets visuales coherentes (sprites, botones, fondos, iconos, tiles, banners) con perfil de proyecto",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "image_studio.py"))],
    ),
    "hub": ToolEntry(
        cmd="hub", module="bago_hub",
        description="BAGO Hub — interfaz central Gradio con dashboard, herramientas, Image Studio e ideas",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_hub.py"))],
    ),
    "project-init": ToolEntry(
        cmd="project-init", module="project_memory",
        description="Inicializa .bago/ local en el directorio del proyecto actual",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "project_memory.py"))],
        deprecated=True, see_also="bago project init",
    ),
    "project-link": ToolEntry(
        cmd="project-link", module="project_memory",
        description="Vincula el proyecto al framework (sesiones se guardan en el proyecto)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "project_memory.py"))],
        deprecated=True, see_also="bago project link",
    ),
    "project-unlink": ToolEntry(
        cmd="project-unlink", module="project_memory",
        description="Desvincula el proyecto — sesiones vuelven al framework",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "project_memory.py"))],
        deprecated=True, see_also="bago project unlink",
    ),
    "project-state": ToolEntry(
        cmd="project-state", module="project_memory",
        description="Muestra el estado del proyecto actualmente vinculado",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "project_memory.py"))],
        deprecated=True, see_also="bago project state",
    ),
    "deactivate": ToolEntry(
        cmd="deactivate", module="backup_manager",
        description="Crea un archivo comprimido de desactivación y lo oculta en Windows",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "backup_manager.py"))],
        layer="salud", scope="framework",
        agent="VALIDADOR",
        stability="experimental",
        risk="mutating",
    ),
    "promote": ToolEntry(
        cmd="promote", module="project_memory",
        description="Promueve un aprendizaje del proyecto al knowledge del framework",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "project_memory.py"))],
        deprecated=True, see_also="bago project promote",
    ),
    "learn": ToolEntry(
        cmd="learn", module="project_memory",
        description="Guarda un aprendizaje en learnings.md del proyecto vinculado",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "project_memory.py"))],
        deprecated=True, see_also="bago project learn",
    ),
    "project": ToolEntry(
        cmd="project", module="project_memory",
        description="Memoria distribuida por proyecto: init | link | unlink | state | learn | promote",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "project_memory.py"))],
    ),
    "context": ToolEntry(
        cmd="context", module="bago_context",
        description="Contexto del workspace: detect | map | git | stale",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_context.py"))],
    ),
    # ── Migradas desde CAJAFISICA (v3.0) ──────────────────────────────────────
    "heal": ToolEntry(
        cmd="heal", module="auto_heal",
        description="Auto-detecta y repara problemas del framework de forma segura y trazable",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "auto_heal.py"))],
        deprecated=True, see_also="bago audit heal",
    ),
    "auto": ToolEntry(
        cmd="auto", module="auto_mode",
        description="Modo automático: evalúa y actúa. --loop para bucle, --infinite para sin límite (Ctrl+C)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "auto_mode.py"))],
        supports_dry_run=True,
    ),
    "sprint": ToolEntry(
        cmd="sprint", module="sprint_manager",
        description="Gestor de sprints BAGO — crear, listar, cerrar sprints de trabajo",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "sprint_manager.py"))],
    ),
    "goals": ToolEntry(
        cmd="goals", module="goals",
        description="Gestor de objetivos del pack con seguimiento de progreso",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "goals.py"))],
    ),
    "habit": ToolEntry(
        cmd="habit", module="habit",
        description="Detecta hábitos de trabajo positivos y mejorables desde patrones de sesiones",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "habit.py"))],
    ),
    "insights": ToolEntry(
        cmd="insights", module="insights",
        description="Análisis de patrones e insights del historial de sesiones BAGO",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "insights.py"))],
    ),
    "orchestrate": ToolEntry(
        cmd="orchestrate", module="orchestrator",
        description="Orquestador de workflows multi-tool en secuencia con condiciones",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "orchestrator.py"))],
    ),
    "scan": ToolEntry(
        cmd="scan", module="scan",
        description="Escaneo de calidad de código: hallazgos, severidad, autofixable",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "scan.py"))],
        deprecated=True, see_also="bago audit scan",
    ),
    "review": ToolEntry(
        cmd="review", module="code_review",
        description="Code review automatizado fail-closed con estado explícito por scanner",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "code_review.py"))],
    ),
    "placeholder_scan": ToolEntry(
        cmd="placeholder_scan", module="placeholder_scan",
        description="Detecta placeholders y datos ficticios en código Python (FAKE_DATE, STUB_RAISE, ELLIPSIS_BODY, TODO_COMMENT, PLACEHOLDER_STR)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "placeholder_scan.py"))],
        layer="calidad", scope="framework",
    ),
    "debt": ToolEntry(
        cmd="debt", module="debt_ledger",
        description="Ledger de deuda técnica — registra, prioriza y hace seguimiento",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "debt_ledger.py"))],
    ),
    "risk": ToolEntry(
        cmd="risk", module="risk_matrix",
        description="Matriz de riesgo del proyecto — evalúa impacto y probabilidad",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "risk_matrix.py"))],
    ),
    "secrets": ToolEntry(
        cmd="secrets", module="secret_scan",
        description="Escanea el repositorio buscando secretos y credenciales expuestas",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "secret_scan.py"))],
    ),
    "hardcode": ToolEntry(
        cmd="hardcode", module="hardcode_detector",
        description="Detecta datos hardcodeados que deberían ser dinámicos (rutas, intérpretes, versiones, puertos)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "hardcode_detector.py"))],
        scope="framework",
    ),
    "spanish": ToolEntry(
        cmd="spanish", module="spanish_audit",
        description="Detecta inconsistencias ortográficas en español: tildes y singular/plural en claves y rutas",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "spanish_audit.py"))],
        scope="framework",
    ),
    "toolsmith": ToolEntry(
        cmd="toolsmith", module="toolsmith",
        description="Agente dinámico de toolboxes: assign|sprint|agent|missing|create|catalog|listen — asigna cajas de herramientas por tarea y crea tools faltantes",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "toolsmith.py")),
            PreflightCheck("file", str(BAGO_ROOT / "mcp" / "toolbox_catalog.json"),
                           severity="warning", message="Catálogo toolbox_catalog.json no encontrado en .bago/mcp/"),
        ],
        layer="infraestructura", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        supports_dry_run=False,
    ),
    "llm-node": ToolEntry(
        cmd="llm-node", module="llm_node",
        description="Nodo LLM del Neural Bus: escucha llm.request, llama a Ollama con streaming, emite llm.chunk + llm.response. Modos: chat|tool_suggest|classify_intent",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "llm_node.py")),
            PreflightCheck("file", str(TOOLS_DIR / "bago_node.py")),
        ],
        layer="infraestructura", scope="framework",
        agent="ARQUITECTO",
        stability="experimental",
        risk="safe",
        supports_dry_run=True,
    ),
    "advisor": ToolEntry(
        cmd="advisor", module="bago_advisor",
        description="Advisor LLM adaptativo: ask|next|explain|run|context|rubber-duck — orientación continua con modelo pequeño local",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "bago_advisor.py")),
        ],
        layer="infraestructura", scope="both",
        agent="NAVEGADOR",
        stability="experimental",
        risk="safe",
        supports_dry_run=True,
    ),
    "rubber-duck": ToolEntry(
        cmd="rubber-duck", module="bago_rubber_duck",
        description="Rubber duck debugging automático: repite qué hace el código, detecta pasos faltantes e inconsistencias — auto-trigger en toolsmith create",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "bago_rubber_duck.py")),
        ],
        layer="calidad", scope="both",
        agent="ANALISTA",
        stability="experimental",
        risk="safe",
        supports_dry_run=False,
    ),
    # ── Autonomía real ─────────────────────────────────────────────────────────
    "autonomous": ToolEntry(
        cmd="autonomous", module="autonomous_loop",
        description="Loop autónomo BAGO: SENSE→PLAN→ACT→OBSERVE→LEARN→DECIDE [--dry-run] [--loop] [--unsafe]",
        preflight=[PreflightCheck("file", str(BAGO_ROOT / "core" / "autonomous_loop.py"))],
        agent="ARQUITECTO",
        supports_dry_run=True,
    ),
    "inbox": ToolEntry(
        cmd="inbox", module="autonomous_loop",
        description="Inbox de tareas autónomas: add <intent> | list | clear",
        preflight=[PreflightCheck("file", str(BAGO_ROOT / "core" / "autonomous_loop.py"))],
        agent="ORGANIZADOR",
    ),
    "siembra": ToolEntry(
        cmd="siembra", module="siembra_manager",
        description="Gestión de siembras BAGO v3.0: create | list | update | diff | sync | status",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "siembra_manager.py"))],
        layer="salud", scope="framework",
        agent="ARQUITECTO",
        stability="experimental",
        risk="mutating",
        supports_dry_run=False,
    ),
    "recientes": ToolEntry(
        cmd="recientes", module="recientes_cli",
        description="Bitácora paginada de últimos trabajos: sesiones, sprints, ideas, cierres y commits ordenados cronológicamente",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "recientes_cli.py"))],
        layer="analítica", scope="both",
        agent="ORGANIZADOR",
        stability="experimental",
        risk="safe",
        supports_dry_run=False,
    ),
    "work_matrix": ToolEntry(
        cmd="work_matrix", module="work_matrix",
        description="Matriz de rutas de trabajo: qué agente y herramientas MCP usar según el tipo de tarea",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "work_matrix.py")),
            PreflightCheck("file", str(BAGO_ROOT / "mcp" / "agent_tool_matrix.json"),
                           severity="warning", message="Matriz agent_tool_matrix.json no encontrada en .bago/mcp/"),
        ],
        layer="analítica", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        supports_dry_run=False,
    ),
    "neural": ToolEntry(
        cmd="neural", module="bago_neural",
        description="Neural Bus — servidor SSE de mensajes inter-agente (start/stop/status/nodes/map)",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "bago_neural.py")),
        ],
        layer="infraestructura", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        supports_dry_run=False,
    ),
    "heal-paths": ToolEntry(
        cmd="heal-paths", module="path_healer",
        description="Detecta y repara rutas rotas tras reorganizaciones. Memoria persistente en state/.",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "path_healer.py")),
        ],
        layer="salud", scope="framework",
        agent="GUARDIAN",
        stability="experimental",
        risk="safe",
        supports_dry_run=True,
    ),
    "npath": ToolEntry(
        cmd="npath", module="npath",
        description="Neural Path — grafo cognitivo versionado: branch/commit/merge/unmerge/split/recall/map",
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "npath" / "__main__.py")),
        ],
        layer="conocimiento", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        supports_dry_run=False,
    ),
    # ── Tools synced from root .bago instance ─────────────────────────────────
    "build-clean": ToolEntry(
        cmd="build-clean", module="build_cleaner",
        description="Elimina node_modules/dist/build para liberar espacio en disco. Dry-run por defecto.",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "build_cleaner.py"))],
        layer="salud", scope="project",
        agent="ARQUITECTO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=True,
    ),
    "build-run": ToolEntry(
        cmd="build-run", module="build_runner",
        description="Ejecuta el proceso de build de las apps del proyecto (server, web, electron, raíz).",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "build_runner.py"))],
        layer="ejecución", scope="project",
        agent="ARQUITECTO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
    ),
    "notify-desktop": ToolEntry(
        cmd="notify-desktop", module="notifier",
        description="Envía notificaciones de escritorio (Windows toast via BurntToast PowerShell).",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "notifier.py"))],
        layer="avanzado", scope="framework",
        agent="ORGANIZADOR",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
    ),
    "notify-whatsapp": ToolEntry(
        cmd="notify-whatsapp", module="notify_whatsapp",
        description="Notificación BAGO vía WhatsApp usando CallMeBot API.",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "notify_whatsapp.py"))],
        layer="avanzado", scope="framework",
        agent="ORGANIZADOR",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
    ),
    "notify-bago": ToolEntry(
        cmd="notify-bago", module="notify_bago",
        description="Notificación BAGO universal: whatsapp (Green API), telegram, desktop.",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "notify_bago.py"))],
        layer="avanzado", scope="framework",
        agent="ORGANIZADOR",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
    ),
    "preflight-check": ToolEntry(
        cmd="preflight-check", module="preflight",
        description="Pre-flight checks declarativos para herramientas BAGO: file/env/cmd conditions.",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "preflight.py"))],
        layer="salud", scope="framework",
        agent="VALIDADOR",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
    ),
    "snapshot": ToolEntry(
        cmd="snapshot", module="snapshot_compare",
        description="Compara dos snapshots de estado BAGO: diferencias en tools, ideas e inventario.",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "snapshot_compare.py"))],
        layer="analítica", scope="framework",
        agent="ANALISTA",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
    ),
    "autonomy": ToolEntry(
        cmd="autonomy", module="workflow_autonomy",
        description="Reconciliación automática del flujo activo: aplica pasos seguros sin permiso, reporta el resto.",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "workflow_autonomy.py"))],
        layer="ejecución", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=True,
    ),
    # ── Multi-Agent Gateway ────────────────────────────────────────────────────
    "agent": ToolEntry(
        cmd="agent", module="agent_gateway",
        description=(
            "Multi-Agent Gateway: dispatch | list | status — "
            "orquesta herramientas BAGO desde cualquier agente externo "
            "(local, Ollama, MCP/Claude, Codex, cloud). "
            "Adapters: local | ollama | mcp | codex | cloud"
        ),
        preflight=[
            PreflightCheck("file", str(BAGO_ROOT / "agents" / "agent_gateway.py")),
        ],
        layer="infraestructura", scope="framework",
        agent="ARQUITECTO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=True,
        layer_group="agents",
    ),
    # ── PADRE / SIEMBRA seed ───────────────────────────────────────────────────
    "seed": ToolEntry(
        cmd="seed", module="bago_seed",
        description=(
            "BAGO Seed — planta la huella mínima de BAGO en un proyecto externo: "
            "crea .bago/pack.json + state/ + launcher y registra la siembra. "
            "Subcomandos: [path] | --name | --dry-run | --list | --status"
        ),
        preflight=[
            PreflightCheck("file", str(TOOLS_DIR / "bago_seed.py")),
        ],
        layer="infraestructura", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=True,
    ),
    # ── NEURAL FABRIC ─────────────────────────────────────────────────────────
    "neural-toolbox": ToolEntry(
        cmd="neural-toolbox", module="neural_toolbox",
        description=(
            "Motor de activación dinámica de herramientas: convierte contexto en lenguaje "
            "natural en un toolbox adaptado. Perfiles derivados del registry, "
            "filtros scope/risk, feedback adaptativo. "
            "Subcomandos: --context | --run | --explain | --json | --dry-run"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "neural_toolbox.py"))],
        layer="core", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=True,
    ),
}
