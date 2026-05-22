"""_registry_entries_visual.py — Subset of BAGO tool registry."""
from __future__ import annotations

from _registry_models import PreflightCheck, ToolEntry
from _registry_paths import BAGO_ROOT, TOOLS_DIR

_ENTRIES: dict[str, ToolEntry] = {
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
        cmd="create", module="creation_studio",
        description=(
            "BAGO Creation Studio: selector de capa arquitectónica + modo creación 3 paneles. "
            "Capas: frontend, backend, db, api, infra, all. "
            "Cada capa filtra cambios, archivos y preview por patrón de archivo. "
            "Flags: --layer L | --sublayer S | --once | --tab cambios|archivos|preview|issues"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "creation_studio.py"))],
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
    "backup-vault": ToolEntry(
        cmd="backup-vault", module="bago_backup_vault",
        description=(
            "Sistema de backups trifasico BAGO: engine, engine+memory, memory-only. "
            "create --type engine|engine-memory|memory [--max N]. "
            "Engine: instalacion limpia con rotacion. "
            "Memory: fusion incremental (solo 1 backup consolidado). "
            "Engine-memory: combinado con rotacion."
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_backup_vault.py"))],
        layer="core", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        layer_group="infra",
    ),
    "portable": ToolEntry(
        cmd="portable", module="bago_portable",
        description=(
            "BAGO Portable: gestion de instalaciones en pen drive. "
            "detect | create <drive> [--models] | sync <drive> | status <drive> | boot <drive>"
        ),
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_portable.py"))],
        layer="core", scope="framework",
        agent="MAESTRO_BAGO",
        stability="experimental",
        risk="safe",
        layer_group="infra",
    ),
}
