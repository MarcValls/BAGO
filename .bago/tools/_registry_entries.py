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
    "pack-cache": ToolEntry(
        cmd="pack-cache", module="pack_cache_db",
        description="Cache híbrida pack.json -> bago.db (sync | check | status)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "pack_cache_db.py"))],
        preflight_policy="required",
        layer="infraestructura", scope="framework", agent="ARQUITECTO",
        stability="core", risk="safe",
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
        description="Muestra la tarea W2 pendiente. --done | --assign <agente> | --clear",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "show_task.py"))],
    ),
    "assign": ToolEntry(
        cmd="assign", module="task_assign",
        description="Asigna tareas a agentes/roles. list-agents | assign <id> <agente> | pending | assigned",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "task_assign.py"))],
    ),
    "benchmark": ToolEntry(
        cmd="benchmark", module="bago_benchmark",
        description="Banco de pruebas de eficiencia BAGO (10 min). --duration N | --suite fast|full | --json",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_benchmark.py"))],
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
    "setup": ToolEntry(
        cmd="setup", module="setup_wizard",
        stability="core",
        description="Wizard de configuración inicial: notificaciones (Telegram/WhatsApp/ntfy), git hooks. --check | --reset | --clean-history",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "setup_wizard.py"))],
        preflight_policy="required",
        supports_dry_run=False,
    ),
    "doctor": ToolEntry(
        cmd="doctor", module="doctor",
        description="Diagnóstico completo del entorno BAGO: Python, Git, Ollama, modelo LLM, espacio",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "doctor.py"))],
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
    "launch": ToolEntry(
        cmd="launch", module="bago_chat",
        description=(
            "BAGO — interfaz conversacional principal. El usuario habla con BAGO; "
            "BAGO orquesta todos los agentes y modelos internamente. "
            "Escalado automático: local → local-grande → cloud según contexto. "
            "Uso: bago launch  |  --provider <p>  |  --model <m>  |  --task <tarea>"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_chat.py"))],
        layer="interfaz", scope="framework",
        agent="MAESTRO_BAGO",
        stability="core",
        risk="safe",
        preflight_policy="required",
    ),
    "self": ToolEntry(
        cmd="self", module="bago_selfrepair",
        description=(
            "BAGO Self-Repair — BAGO se centra en sí mismo y repara sus propios fallos. "
            "Dos modos: autoreparación (--auto) y manual (menú interactivo). "
            "Uso: bago self | --auto | --list | --regenerate | --error 'descripción'"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_selfrepair.py"))],
        layer="sistema", scope="framework",
        agent="MAESTRO_BAGO",
        stability="core",
        risk="safe",
        preflight_policy="required",
    ),
    "field": ToolEntry(
        cmd="field", module="bago_field",
        description=(
            "BAGO Field — Escáner del campo magnético de modelos/providers. "
            "Detecta disponibilidad, genera matriz de campo y gestiona bago-local. "
            "Uso: bago field [scan|status|pull <model>|calibrate <model>]"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_field.py"))],
        layer="sistema", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="required",
    ),
    "boot": ToolEntry(
        cmd="boot", module="bago_boot",
        description=(
            "BAGO Boot Examiner — Arranca BAGO de forma examinada: detecta proyecto, "
            "escanea campo de modelos, verifica safeguards y fabrica frases-operador. "
            "Uso: bago boot [examine|status|phrases]"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_boot.py"))],
        layer="sistema", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="required",
    ),
    "safeguard": ToolEntry(
        cmd="safeguard", module="bago_safeguard",
        description=(
            "BAGO Safeguard Panel — Gestiona los 4 genes de protección del sistema: "
            "identity, safety_contract, kill_switch_policy, project_boundary. "
            "Uso: bago safeguard [status|explain <gene>|set <gene> <state>|history]"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_safeguard.py"))],
        layer="sistema", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="required",
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
        supports_dry_run=False,
    ),
    "spiral": ToolEntry(
        cmd="spiral", module="spiral_loop",
        stability="dangerous",
        description="Bucle espiral cromático (Shepard Loop): 12 pasos de auto-redescrición AGI. --execute para actuar, --status, --history",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "spiral_loop.py"))],
        supports_dry_run=False,
    ),
    "skill": ToolEntry(
        cmd="skill", module="skill_engine",
        stability="experimental",
        description="Skill Layer (Fractal AGI nivel-2): mini-spirals de 3-6 pasos. list | run <id> | status",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "skill_engine.py"))],
        supports_dry_run=True,
        layer="avanzado",
        layer_group="core",
        agent="ORGANIZADOR",
    ),
    "orphans": ToolEntry(
        cmd="orphans", module="orphan_detector",
        stability="core",
        description="Detector de módulos huérfanos: archivos .py en tools/ sin registro. --baseline | --fix | --strict",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "orphan_detector.py"))],
        preflight_policy="required",
        supports_dry_run=False,
    ),
    "spiral-agent": ToolEntry(
        cmd="spiral-agent", module="spiral_agent",
        stability="experimental",
        description="Agent Layer (Fractal AGI nivel-1): BagoAgents con skills dinámicas. spawn | list | run <id> | kill | status",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "spiral_agent.py"))],
        supports_dry_run=True,
        layer="avanzado",
        layer_group="core",
        agent="ORGANIZADOR",
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
    # ── DEVELOPER MODE ────────────────────────────────────────────────────────
    "devmode": ToolEntry(
        cmd="devmode", module="bago_devmode",
        description=(
            "Alterna entre modo usuario (project-first) y modo desarrollador (framework-visible). "
            "Subcomandos: --enable | --disable | --status | --info"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_devmode.py"))],
        layer="configuración", scope="both",
        agent="MAESTRO_BAGO",
        stability="core",
        risk="safe",
        preflight_policy="required",
        supports_dry_run=False,
        layer_group="core",
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
    # ── MENÚ INTERACTIVO ──────────────────────────────────────────────────────
    "menu": ToolEntry(
        cmd="menu", module="bago_menu",
        description=(
            "Menú interactivo jerárquico de comandos BAGO (curses). "
            "Sidebar de 10 grupos por flujo de trabajo + lista + preview. "
            "Uso: bago menu  |  bago menu --list  (no interactivo)"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_menu.py"))],
        layer="ejecución", scope="both",
        agent="MAESTRO_BAGO",
        stability="core",
        risk="safe",
        preflight_policy="required",
        supports_dry_run=False,
        layer_group="core",
    ),
    "size-check": ToolEntry(
        cmd="size-check", module="file_size_guard",
        description=(
            "Detecta archivos .py en .bago/tools/ con más de 400 líneas "
            "y los reporta como monolitos candidatos a dividir."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "file_size_guard.py"))],
        layer="calidad", scope="framework",
        agent="CENTINELA",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="core",
    ),
    "orphan-shield": ToolEntry(
        cmd="orphan-shield", module="orphan_shield",
        description=(
            "Detecta 4 tipos de huérfanos: archivos .py no registrados, "
            "entradas de registry sin archivo, comandos del router sin registry "
            "y tools sin cobertura documental."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "orphan_shield.py"))],
        layer="calidad", scope="framework",
        agent="CENTINELA",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="core",
    ),
    "doc-index": ToolEntry(
        cmd="doc-index", module="doc_index",
        description=(
            "Índice reverso de cobertura documental: qué documentos en docs/ "
            "cubren qué herramientas. Detecta tools sin documentar y permite "
            "añadir anotaciones @covers a los .md."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "doc_index.py"))],
        layer="calidad", scope="framework",
        agent="CENTINELA",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="core",
    ),
    "canon": ToolEntry(
        cmd="canon", module="bago_canon",
        description=(
            "Bucle de Shepard: 4 modos x 3 voces · DETECT→DIAGNOSE→VERIFY→EVOLVE. "
            "Orquesta el ciclo completo de salud del framework. "
            "Modos: MODULAR (monolitos), SCAN (huerfanos/doc), "
            "CREATE (integracion), EVOLVE (lecciones). "
            "Uso: bago canon [--mode M] [--voice N] [--loop] [--json]"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_canon.py"))],
        layer="calidad", scope="framework",
        agent="CENTINELA",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="core",
    ),
    # ── SESIÓN / WORKSPACE ────────────────────────────────────────────────────
    "workspace-select": ToolEntry(
        cmd="workspace-select", module="workspace_selector",
        description=(
            "Selector de espacio de trabajo: elige entre framework (self), "
            "directorio padre o ruta/repo externo. Persiste en repo_context.json. "
            "Se invoca automáticamente al arrancar si no hay workspace configurado. "
            "Uso: bago workspace-select  |  opciones: --json --plain"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "workspace_selector.py"))],
        layer="configuración", scope="both",
        agent="MAESTRO_BAGO",
        stability="core",
        risk="safe",
        preflight_policy="required",
        supports_dry_run=False,
        layer_group="core",
    ),
    "recent-projects": ToolEntry(
        cmd="recent-projects", module="recent_projects",
        description=(
            "Historial de proyectos BAGO recientes: repos visitados, ideas implementadas, "
            "sesiones. Se alimenta automáticamente al arrancar. "
            "Uso: bago recent-projects  |  uso interno: --record"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "recent_projects.py"))],
        layer="configuración", scope="both",
        agent="MAESTRO_BAGO",
        stability="core",
        risk="safe",
        preflight_policy="required",
        supports_dry_run=False,
        layer_group="core",
    ),
    # ── LEGACY PROMOVIDOS ────────────────────────────────────────────────────
    "alias-manager": ToolEntry(
        cmd="alias-manager", module="alias_manager",
        description=(
            "Crea y ejecuta atajos de comandos bago personalizados. "
            "Los alias se guardan en .bago/state/bago_aliases.json. "
            "Subcomandos: --list | --set <nombre> <cmd> | --run <nombre> | --del <nombre> | --show <nombre>"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "alias_manager.py"))],
        layer="configuración", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "artifact-counter": ToolEntry(
        cmd="artifact-counter", module="artifact_counter",
        description=(
            "Mide y reporta la producción de artefactos útiles por sesión. "
            "Excluye artefactos de protocolo (sessions, changes, evidences). "
            "Útil para ver la velocidad real de entrega por sesión."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "artifact_counter.py"))],
        layer="analítica", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "code-metrics": ToolEntry(
        cmd="code-metrics", module="code_metrics",
        description=(
            "Métricas de código: líneas de código, conteo de archivos y tipos por app. "
            "Excluye node_modules, dist, build y archivos de lock. "
            "Soporta filtros de extensión y configuración via bago_config."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "code_metrics.py"))],
        layer="analítica", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "code-search": ToolEntry(
        cmd="code-search", module="code_search",
        description=(
            "Busca texto o patrones en el código fuente del proyecto. "
            "Sin dependencias externas. Excluye node_modules/dist/build. "
            "Subcomandos: --regex | -i (case-insensitive) | --ext ts,py | --files | --count"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "code_search.py"))],
        layer="calidad", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "env-manager": ToolEntry(
        cmd="env-manager", module="env_manager",
        description=(
            "Gestión de archivos de entorno (.env) del proyecto. "
            "Shim de compatibilidad para env.py. "
            "Subcomandos: list [-v] | table | diff [app] | check | set <app> KEY=value | setup"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "env_manager.py"))],
        layer="configuración", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "focus-mode": ToolEntry(
        cmd="focus-mode", module="focus_mode",
        description=(
            "Muestra la tarea activa en modo enfoque minimalista. "
            "Diseñado para mostrar en un corner de pantalla o en el prompt. "
            "Subcomandos: --compact (una línea) | --watch (refresca 30s) | --clear"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "focus_mode.py"))],
        layer="ejecución", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "git-status": ToolEntry(
        cmd="git-status", module="git_status",
        description=(
            "Resumen compacto del estado de git del proyecto activo. "
            "Usa comandos git estándar. Funciona en cualquier repositorio git. "
            "Subcomandos: --log N (últimos N commits) | --short (una línea) | --diff"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "git_status.py"))],
        layer="infraestructura", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "html-export": ToolEntry(
        cmd="html-export", module="html_export",
        description=(
            "Genera un informe HTML autocontenido del proyecto BAGO. "
            "Incluye ideas implementadas, herramientas, métricas por semana y estado. "
            "Subcomandos: --out DIR | --open (abre en navegador tras generar)"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "html_export.py"))],
        layer="visual", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "lint-runner": ToolEntry(
        cmd="lint-runner", module="lint_runner",
        description=(
            "Ejecuta el linter en las apps del proyecto y agrega resultados. "
            "Detecta scripts lint/typecheck en cada package.json. "
            "Subcomandos: --app <nombre> | --type (typecheck) | --fix | --list"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "lint_runner.py"))],
        layer="calidad", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "log-viewer": ToolEntry(
        cmd="log-viewer", module="log_viewer",
        description=(
            "Visor de logs en tiempo real para apps del monorepo. "
            "Detecta severidad (ERROR/WARN/INFO) y colorea la salida. "
            "Lee la ruta del proyecto desde global_state.json."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "log_viewer.py"))],
        layer="ejecución", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "net-scan": ToolEntry(
        cmd="net-scan", module="net_scan",
        description=(
            "Escáner de red: detecta adaptadores, estado de cable, velocidad y vecinos ARP. "
            "Útil para diagnóstico de conectividad local. "
            "Subcomandos: --scan (ARP de red local) | --watch (monitoriza cambios) | --adapters"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "net_scan.py"))],
        layer="infraestructura", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "personality-panel": ToolEntry(
        cmd="personality-panel", module="personality_panel",
        description=(
            "Panel de personalidad y configuración de agentes BAGO. "
            "Gestiona el perfil de personalidad del usuario en user_personality_profile.json. "
            "Configura estilo, idioma y vocabulario preferido de los agentes."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "personality_panel.py"))],
        layer="configuración", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "ping-server": ToolEntry(
        cmd="ping-server", module="ping_server",
        description=(
            "Verifica que el servidor local responde vía HTTP. "
            "Muestra status, latencia y errores. Lee la URL desde apps/server/.env. "
            "Subcomandos: --url <URL> | --path <endpoint> | --watch (ping cada 5s)"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "ping_server.py"))],
        layer="salud", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "project-summary": ToolEntry(
        cmd="project-summary", module="project_summary",
        description=(
            "Dashboard ejecutivo del proyecto: ideas implementadas, herramientas, "
            "tamaño en disco, estado de git y todos pendientes. "
            "Fuente única de verdad para el estado actual del proyecto."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "project_summary.py"))],
        layer="analítica", scope="both",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "script-runner": ToolEntry(
        cmd="script-runner", module="script_runner",
        description=(
            "Ejecuta cualquier script npm/pnpm del workspace del monorepo. "
            "Detecta scripts en root y apps/*/package.json. "
            "Lee el proyecto activo desde global_state.json."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "script_runner.py"))],
        layer="ejecución", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "search-history": ToolEntry(
        cmd="search-history", module="search_history",
        description=(
            "Busca en el historial de ideas implementadas. "
            "Sin argumentos muestra las últimas 10 ideas. "
            "Uso: bago search-history <término> [término2 ...]"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "search_history.py"))],
        layer="conocimiento", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "state-manager": ToolEntry(
        cmd="state-manager", module="state_manager",
        description=(
            "API unificada para el estado BAGO: health, sprint y knowledge. "
            "Gestiona global_state.json y ficheros divididos (health.json, sprint.json, knowledge_index.json). "
            "Subcomandos: --status | --materialize | --split | --read <sección> | --test"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "state_manager.py"))],
        layer="infraestructura", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "template-gen": ToolEntry(
        cmd="template-gen", module="template_gen",
        description=(
            "Genera archivos de proyecto desde plantillas predefinidas (component, hook, api-route, test, etc.). "
            "Variables: {{PROJECT}}, {{APP}}, {{NAME}}, {{DATE}}, {{AUTHOR}}. "
            "Subcomandos: --list | --show <nombre> | --add <nombre> | --out <dir>"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "template_gen.py"))],
        layer="ejecución", scope="project",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="mutating",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "weekly-report": ToolEntry(
        cmd="weekly-report", module="weekly_report",
        description=(
            "Informe semanal de actividad BAGO: ideas implementadas, sesiones y velocidad. "
            "Por defecto últimos 7 días. Genera resumen Markdown. "
            "Subcomandos: --days N | --save (guarda en .bago/state/reports/)"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "weekly_report.py"))],
        layer="analítica", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),
    "workflow-navigator": ToolEntry(
        cmd="workflow-navigator", module="workflow_navigator",
        description=(
            "Navegador de workflows BAGO: sugiere el workflow más adecuado dado el contexto actual. "
            "Lee WORKFLOW_GRAPH.json y el estado del sistema. "
            "Subcomandos: --from <workflow> | --list | --graph | --test"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "workflow_navigator.py"))],
        layer="avanzado", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        preflight_policy="optional",
        supports_dry_run=False,
        layer_group="tools",
    ),


    "create": ToolEntry(
        cmd="create", module="creation_mode",
        description=(
            "BAGO modo creación: layout 3 paneles tipo Copilot. "
            "Panel izquierdo: sesiones + personalizaciones. "
            "Panel central: área de trabajo + input hito. "
            "Panel derecho: cambios git / archivos. "
            "Flags: --once (render único) | --tab cambios|archivos"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "creation_mode.py"))],
        layer="visual", scope="both",
        agent="ORGANIZADOR",
        stability="experimental",
        risk="safe",
        layer_group="ui",
    ),
    "agent-config": ToolEntry(
        cmd="agent-config",
        module="agent_config",
        description="Configurador de agentes BAGO: TUI interactivo (Agentes, Habilidades, Instrucciones, MCP, Complementos)",
        preflight=[],
        schema="[list|show <agent>|edit <agent>]",
        layer="visual",
        scope="both",
        agent="ORGANIZADOR",
        stability="experimental",
        risk="safe",
        layer_group="ui",
    ),
    "gateway": ToolEntry(
        cmd="gateway",
        module="gateway",
        description="Messaging gateway unificado: WhatsApp, Telegram, Signal, Email, ntfy, Utopia P2P",
        preflight=[],
        schema="[list|setup <platform>|send <platform> <msg>|verify <platform>]",
        layer="visual",
        scope="global",
        agent="ops",
        stability="experimental",
        risk="safe",
        layer_group="ui",
    ),

    "music-saas": ToolEntry(
        cmd="music-saas",
        module="music_saas",
        description="CLI para BAGO Music SaaS — status, dev server, Telegram webhook, GitHub Actions build",
        preflight=[],
        schema="[status|dev|webhook <url>|test|open [tool]|build|config]",
        layer="visual",
        scope="global",
        agent="ops",
        stability="experimental",
        risk="safe",
        layer_group="ui",
    ),
    # ── SUPERVISION LAYER ─────────────────────────────────────────────────────
    "supervision": ToolEntry(
        cmd="supervision",
        module="supervision.supervisor",
        description=(
            "BAGO Supervision Layer — capa de guardianes sistémicos. "
            "Convierte fallos recurrentes en agentes con memoria, artefacto y contrato. "
            "Subcomandos: run [--loop pre_release|post_test_cleanup|legacy_decay|contract_drift] "
            "| status | check <agente> | report [--json] [--loop]"
        ),
        preflight=[
            PreflightCheck("file", str(BAGO_ROOT / "supervision" / "supervisor.py")),
        ],
        layer="calidad",
        scope="framework",
        agent="GUIA_VERTICE",
        stability="core",
        risk="safe",
        preflight_policy="required",
        supports_dry_run=True,
        layer_group="core",
    ),
}
