#!/usr/bin/env python3
"""tool_registry.py — Registro central de herramientas BAGO.

Fuente ÚNICA de verdad para:
  - Mapping cmd → módulo Python (reemplaza COMMANDS dict en bago)
  - Descripción por herramienta
  - Pre-flight checks declarativos por comando
  - Lista canónica de tools internas (excluidas de guardian/manifest)

Importado por: bago (script), tool_guardian.py, auto_register.py,
               contracts.py, ci_generator.py

Uso:
    python3 tool_registry.py --list          # lista todos los comandos
    python3 tool_registry.py --json          # JSON del registro completo
    python3 tool_registry.py --test          # self-tests (7/7)
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

TOOLS_DIR = Path(__file__).parent
BAGO_ROOT = TOOLS_DIR.parent        # .bago/
REPO_ROOT = BAGO_ROOT.parent        # repo raíz
PYTHON = sys.executable or "python3"


# ── Declarative pre-flight check ─────────────────────────────────────────────

@dataclass
class PreflightCheck:
    """A single declarative pre-flight condition."""
    kind: str       # "file" | "env" | "cmd"
    value: str      # path | env-var name | command name
    severity: str = "error"   # "error" | "warning"
    message: str = ""         # custom message (empty → auto-generated)


# ── Tool descriptor ───────────────────────────────────────────────────────────

@dataclass
class ToolEntry:
    """Full descriptor for a user-facing BAGO tool."""
    cmd: str                              # Public CLI command (bago <cmd>)
    module: str                           # Python module stem (without .py)
    description: str
    preflight: list[PreflightCheck] = field(default_factory=list)
    schema: dict = field(default_factory=dict)   # Arg schema (future use)
    deprecated: bool = False              # True → mostrar hint al ejecutar
    see_also: str = ""                    # Comando grupo preferido
    layer: str = ""                       # Capa taxonómica (ejecución|calidad|salud|analítica|visual|avanzado)
    scope: str = ""                       # Ámbito (framework|project|both) — inyectado desde _SCOPE_MAP
    agent: str = ""                       # Agente responsable — inyectado desde _AGENT_MAP
    subscribes: list[str] = field(default_factory=list)  # Eventos del bus a los que reacciona
    # Kernel Lockdown (v3.2) — classification fields
    stability: str = "experimental"       # "core"|"experimental"|"legacy"|"internal"|"dangerous"
    risk: str = "safe"                    # "safe"|"mutating"|"dangerous"
    preflight_policy: str = "optional"   # "required"|"optional"|"none"
    supports_dry_run: bool = False        # True → --dry-run is a valid safe bypass for dangerous


# ── Internal tools — excluded from guardian / manifest / integration_tests ────
# Single canonical source; all other files should import this set.
INTERNAL_TOOLS: frozenset[str] = frozenset({
    "tool_registry",
    "preflight",
    "session_logger",
    "integration_tests",
    "bago_utils",
    "bago_banner",
    "auto_register",
    "ci_generator",
    "tool_guardian",
    "contracts",
    "bago_start",
    "bago_on",
    "bago_debug",
    "bago_watch",
    "bago_chat_server",
    "bago_ask",
    "bago_lint_cli",
    "bago_search",
    "legacy_fixer",
    "bago_config",
})


# ── Canonical registry ────────────────────────────────────────────────────────
# Add new tools here; auto_register.py will append entries automatically.

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
        cmd="validate", module="validate_pack",
        description="Verifica el pack (solo lectura)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "validate_pack.py"))],
    ),
    "docs": ToolEntry(
        cmd="docs", module="generate_commands_doc",
        description="Genera docs/COMMANDS.md desde tool_registry.py (fuente única de verdad)",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "generate_commands_doc.py"))],
        layer="calidad", scope="framework",
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
        cmd="health", module="bago_health_router",
        description="Salud del framework: score | report | stability | efficiency | consistency | sincerity",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_health_router.py"))],
    ),
    "audit": ToolEntry(
        cmd="audit", module="bago_audit_router",
        description="Auditoría y calidad: full | pack | scan | commit | push | doctor | heal | quality | purity",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_audit_router.py"))],
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
        cmd="session", module="bago_session_router",
        description="Ciclo de sesión: open | close | harvest | v2",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_session_router.py"))],
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
        cmd="report", module="health_report",
        description="Health report en Markdown",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "health_report.py"))],
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
        cmd="session_close", module="session_close_generator",
        description="Genera el informe de cierre de sesion BAGO",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "session_close_generator.py"))],
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
        cmd="config-check", module="config_check",
        description="Valida integridad de configs JSON en state/config/ y cruza con registry",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "config_check.py"))],
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
        cmd="repo", module="bago_repo",
        description="Gestión de repositorios: clone | list | switch",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "bago_repo.py"))],
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
    # ── Migradas desde CAJAFISICA (v3.0) ─────────────────────────────────────
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
        description="Code review automatizado — analiza cambios y genera feedback",
        preflight=[PreflightCheck("file", str(TOOLS_DIR / "code_review.py"))],
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
    # ── Autonomía real ────────────────────────────────────────────────────────
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
}


# ── Taxonomía de capas ────────────────────────────────────────────────────────

LAYERS: dict[str, dict] = {
    "ejecución": {"icon": "⚡", "label": "EJECUCIÓN",  "desc": "ejecutar y avanzar trabajo activo"},
    "calidad":   {"icon": "🔍", "label": "CALIDAD",    "desc": "calidad de código del proyecto"},
    "salud":     {"icon": "💚", "label": "SALUD",      "desc": "salud y mantenimiento del framework"},
    "analítica": {"icon": "📊", "label": "ANALÍTICA",  "desc": "métricas, insights y patrones"},
    "visual":    {"icon": "🎨", "label": "VISUAL",     "desc": "generación de assets e interfaces"},
    "avanzado":  {"icon": "🔧", "label": "AVANZADO",   "desc": "herramientas avanzadas e integraciones"},
}

_LAYER_MAP: dict[str, str] = {
    # EJECUCIÓN
    "start": "ejecución", "next": "ejecución", "ideas": "ejecución",
    "select": "ejecución", "session": "ejecución", "task": "ejecución",
    "done": "ejecución", "flow": "ejecución", "sprint": "ejecución",
    "goals": "ejecución", "workflow": "ejecución", "reopen": "ejecución",
    "auto": "ejecución", "cosecha": "ejecución", "v2": "ejecución",
    "session_close": "ejecución",
    # CALIDAD
    "scan": "calidad", "review": "calidad", "commit": "calidad",
    "pre-push": "calidad", "secrets": "calidad", "debt": "calidad",
    "risk": "calidad", "naming": "calidad", "types": "calidad",
    "deps": "calidad", "code-quality": "calidad",
    # SALUD
    "health": "salud", "audit": "salud", "doctor": "salud", "heal": "salud",
    "validate": "salud", "sync": "salud", "check": "salud",
    "consistency": "salud", "config-check": "salud", "context": "salud",
    "repo": "salud", "project": "salud", "stale": "salud",
    "detector": "salud", "map": "salud", "scope": "salud",
    # ANALÍTICA
    "insights": "analítica", "habit": "analítica", "chronicle": "analítica",
    "dashboard": "analítica", "efficiency": "analítica", "stability": "analítica",
    "report": "analítica", "diff": "analítica", "status": "analítica",
    # VISUAL
    "hub": "visual", "image-studio": "visual", "sprite-studio": "visual",
    "image_gen": "visual", "banner": "visual",
    # AVANZADO
    "llm": "avanzado", "lsp": "avanzado", "orchestrate": "avanzado",
    "cabinet": "avanzado", "rules": "avanzado", "db": "avanzado",
    "peer": "avanzado", "find-tool": "avanzado", "ask": "avanzado",
    "why": "avanzado", "research": "avanzado", "install": "avanzado",
    "hello": "avanzado", "git": "avanzado",
    "siembra": "salud",
    "repo-clone": "salud", "repo-list": "salud", "repo-switch": "salud",
    "project-init": "salud", "project-link": "salud", "project-unlink": "salud",
    "project-state": "salud", "promote": "salud", "learn": "salud",
}

_SCOPE_MAP: dict[str, str] = {
    # framework — opera sobre el propio framework BAGO
    "health": "framework", "validate": "framework", "sync": "framework",
    "check": "framework", "consistency": "framework", "config-check": "framework",
    "stability": "framework", "efficiency": "framework", "sincerity": "framework",
    "doctor": "framework", "heal": "framework", "auto": "framework",
    "banner": "framework", "rules": "framework", "db": "framework",
    "cabinet": "framework", "install": "framework", "hello": "framework",
    "report": "framework", "scope": "framework", "siembra": "framework",
    # project — opera sobre el proyecto activo
    "scan": "project", "review": "project", "commit": "project",
    "pre-push": "project", "secrets": "project", "debt": "project",
    "risk": "project", "naming": "project", "types": "project",
    "deps": "project", "code-quality": "project",
    "image-studio": "project", "sprite-studio": "project",
    "image_gen": "project", "lsp": "project", "git": "project",
    # both — opera sobre el framework Y/O proyectos
    "start": "both", "next": "both", "ideas": "both", "select": "both",
    "session": "both", "task": "both", "done": "both", "flow": "both",
    "sprint": "both", "goals": "both", "workflow": "both", "reopen": "both",
    "cosecha": "both", "v2": "both", "session_close": "both",
    "audit": "both", "context": "both", "repo": "both", "project": "both",
    "insights": "both", "habit": "both", "chronicle": "both",
    "dashboard": "both", "diff": "both", "status": "both",
    "hub": "both", "llm": "both", "orchestrate": "both", "peer": "both",
    "find-tool": "both", "ask": "both", "why": "both", "research": "both",
    "detector": "both", "stale": "both", "map": "both",
    "repo-clone": "both", "repo-list": "both", "repo-switch": "both",
    "project-init": "both", "project-link": "both", "project-unlink": "both",
    "project-state": "both", "promote": "both", "learn": "both",
}

# ── Agent map — qué agente interno es responsable de cada comando ──────────────
# Agentes disponibles (ver .bago/roles/):
#   ANALISTA · ARQUITECTO · GENERADOR · ORGANIZADOR · VALIDADOR (produccion)
#   AUDITOR_CANONICO · CENTINELA_SINCERIDAD · VERTICE             (supervision)
#   REVISOR_SEGURIDAD · REVISOR_PERFORMANCE · REVISOR_UX          (especialistas)
#   INTEGRADOR_REPO                                                (especialistas)
_AGENT_MAP: dict[str, str] = {
    # ANALISTA — Análisis estático, detección, métricas, búsqueda
    "detector":    "ANALISTA",
    "scope":       "ANALISTA",
    "efficiency":  "ANALISTA",
    "stability":   "ANALISTA",
    "code-quality":"ANALISTA",
    "naming":      "ANALISTA",
    "types":       "ANALISTA",
    "deps":        "ANALISTA",
    "map":         "ANALISTA",
    "context":     "ANALISTA",
    "diff":        "ANALISTA",
    "why":         "ANALISTA",
    "research":    "ANALISTA",
    "scan":        "ANALISTA",
    "debt":        "ANALISTA",
    "risk":        "ANALISTA",
    "find-tool":   "ANALISTA",
    "insights":    "ANALISTA",
    "lsp":         "ANALISTA",
    "habit":       "ANALISTA",
    "review":      "ANALISTA",
    # ARQUITECTO — Flujo, automatización, planificación, clonado
    "auto":           "ARQUITECTO",
    "flow":           "ARQUITECTO",
    "cabinet":        "ARQUITECTO",
    "orchestrate":    "ARQUITECTO",
    "repo-clone":     "ARQUITECTO",
    "llm":            "ARQUITECTO",
    "project-init":   "ARQUITECTO",
    "project-link":   "ARQUITECTO",
    "project-unlink": "ARQUITECTO",
    "next":           "ARQUITECTO",
    "peer":           "ARQUITECTO",
    "hub":            "ARQUITECTO",
    "siembra":        "ARQUITECTO",
    # GENERADOR — Generación de artefactos, reportes, imágenes
    "cosecha":       "GENERADOR",
    "image_gen":     "GENERADOR",
    "report":        "GENERADOR",
    "banner":        "GENERADOR",
    "chronicle":     "GENERADOR",
    "sprite-studio": "GENERADOR",
    "image-studio":  "GENERADOR",
    # ORGANIZADOR — Sprint, workflow, sesión, estado, repos, DB
    "dashboard":     "ORGANIZADOR",
    "ideas":         "ORGANIZADOR",
    "workflow":      "ORGANIZADOR",
    "sprint":        "ORGANIZADOR",
    "task":          "ORGANIZADOR",
    "v2":            "ORGANIZADOR",
    "session":       "ORGANIZADOR",
    "session_close": "ORGANIZADOR",
    "reopen":        "ORGANIZADOR",
    "git":           "ORGANIZADOR",
    "db":            "ORGANIZADOR",
    "done":          "ORGANIZADOR",
    "status":        "ORGANIZADOR",
    "sync":          "ORGANIZADOR",
    "repo":          "ORGANIZADOR",
    "repo-list":     "ORGANIZADOR",
    "repo-switch":   "ORGANIZADOR",
    "select":        "ORGANIZADOR",
    "project-state": "ORGANIZADOR",
    "promote":       "ORGANIZADOR",
    "learn":         "ORGANIZADOR",
    "project":       "ORGANIZADOR",
    "ask":           "ORGANIZADOR",
    "goals":         "ORGANIZADOR",
    # VALIDADOR — Salud, validación, diagnóstico
    "health":        "VALIDADOR",
    "audit":         "VALIDADOR",
    "validate":      "VALIDADOR",
    "check":         "VALIDADOR",
    "stale":         "VALIDADOR",
    "config-check":  "VALIDADOR",
    "doctor":        "VALIDADOR",
    "heal":          "VALIDADOR",
    "consistency":   "VALIDADOR",
    # CENTINELA_SINCERIDAD — Integridad de commits y sinceridad
    "commit":        "CENTINELA_SINCERIDAD",
    "pre-push":      "CENTINELA_SINCERIDAD",
    "sincerity":     "CENTINELA_SINCERIDAD",
    # AUDITOR_CANONICO — Reglas y auditoría canónica
    "rules":         "AUDITOR_CANONICO",
    # REVISOR_SEGURIDAD — Seguridad y secretos
    "secrets":       "REVISOR_SEGURIDAD",
    # VERTICE — Gobierno del sistema, entrada, instalación
    "hello":         "VERTICE",
    "install":       "VERTICE",
    "start":         "VERTICE",
}

# Inyecta layer + scope + agent en cada entrada del registro
for _cmd, _entry in REGISTRY.items():
    if not _entry.layer:
        _entry.layer = _LAYER_MAP.get(_cmd, "avanzado")
    if not _entry.scope:
        _entry.scope = _SCOPE_MAP.get(_cmd, "both")
    if not _entry.agent:
        _entry.agent = _AGENT_MAP.get(_cmd, "ORGANIZADOR")

# ── Kernel Lockdown classification (v3.2) ─────────────────────────────────────
# Applied as post-processing so existing ToolEntry definitions stay clean.

_CORE_CMDS: frozenset[str] = frozenset({
    "health", "audit", "status", "task", "session", "flow",
    "project", "sync", "scope", "secrets", "validate", "context",
})
_DANGEROUS_CMDS: frozenset[str] = frozenset({
    "install", "autonomous", "orchestrate", "cabinet", "peer", "db", "auto",
})
_INTERNAL_CMDS: frozenset[str] = frozenset({
    "banner", "hello", "hub", "start", "done",
})

for _cmd, _entry in REGISTRY.items():
    if _entry.deprecated:
        _entry.stability = "legacy"
    elif _cmd in _CORE_CMDS:
        _entry.stability = "core"
        _entry.preflight_policy = "required"
    elif _cmd in _DANGEROUS_CMDS:
        _entry.stability = "dangerous"
        _entry.risk = "dangerous"
    elif _cmd in _INTERNAL_CMDS:
        _entry.stability = "internal"
        _entry.preflight_policy = "none"
    # else: stability="experimental", risk="safe", preflight_policy="optional" (defaults)



SCOPE_BADGE: dict[str, str] = {
    "framework": "🔵",
    "project":   "🟢",
    "both":      "⚪",
}


def get_deprecated_map() -> dict[str, str]:
    """Returns {cmd: see_also} for deprecated commands."""
    return {
        name: entry.see_also
        for name, entry in REGISTRY.items()
        if entry.deprecated
    }


def get_by_layer(include_deprecated: bool = False) -> dict[str, list[ToolEntry]]:
    """Returns commands grouped by layer.

    Keys match LAYERS dict order. Only non-deprecated entries unless
    include_deprecated=True.
    """
    result: dict[str, list[ToolEntry]] = {k: [] for k in LAYERS}
    result[""] = []  # bucket for entries with unknown layer
    for entry in REGISTRY.values():
        if not include_deprecated and entry.deprecated:
            continue
        bucket = entry.layer if entry.layer in result else ""
        result[bucket].append(entry)
    # Sort each layer alphabetically
    for bucket in result:
        result[bucket].sort(key=lambda e: e.cmd)
    return result


def get_commands() -> dict[str, list[str]]:
    """Returns COMMANDS-compatible dict for the bago script.

    Format: {"cmd": ["python3", "/path/to/module.py", ...extra_args]}
    Searches TOOLS_DIR first, then BAGO_ROOT/core/ for modules (e.g. autonomous_loop).
    """
    _extra_args: dict[str, list[str]] = {
        "done":           ["--done"],
        "status":         ["status"],
        "project-init":   ["project-init"],
        "project-link":   ["project-link"],
        "project-unlink": ["project-unlink"],
        "project-state":  ["project-state"],
        "promote":        ["promote"],
        "learn":          ["learn"],
    }
    result = {}
    for name, entry in REGISTRY.items():
        tools_path = TOOLS_DIR / f"{entry.module}.py"
        core_path  = BAGO_ROOT / "core" / f"{entry.module}.py"
        module_path = tools_path if tools_path.exists() else core_path
        cmd = [PYTHON, str(module_path)]
        if name in _extra_args:
            cmd += _extra_args[name]
        result[name] = cmd
    return result


def get_cmd_names() -> list[str]:
    """Sorted list of all registered public command names."""
    return sorted(REGISTRY.keys())


def load_registry(registry_path: "Path | None" = None) -> "dict[str, ToolEntry]":
    """Load REGISTRY from an explicit path via importlib (no sys.path needed).

    Falls back to this module's REGISTRY if registry_path is None or missing.
    """
    import importlib.util
    path = registry_path or Path(__file__)
    if not path.exists():
        return REGISTRY
    spec = importlib.util.spec_from_file_location("_tool_registry_loaded", path)
    if spec is None:
        return REGISTRY
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return getattr(mod, "REGISTRY", REGISTRY)
    except Exception:
        return REGISTRY


# ── CLI ───────────────────────────────────────────────────────────────────────

def _cmd_list() -> None:
    print("  BAGO — Registro central de herramientas")
    print(f"  {'CMD':<18} {'MÓDULO':<28} DESCRIPCIÓN")
    print("  " + "─" * 76)
    for name, entry in sorted(REGISTRY.items()):
        print(f"  {name:<18} {entry.module:<28} {entry.description}")
    print(f"\n  Comandos registrados: {len(REGISTRY)}")
    print(f"  Herramientas internas: {len(INTERNAL_TOOLS)}")


def _cmd_json() -> None:
    out = {
        "total": len(REGISTRY),
        "internal_count": len(INTERNAL_TOOLS),
        "internal_tools": sorted(INTERNAL_TOOLS),
        "tools": {
            name: {
                "cmd": e.cmd,
                "module": e.module,
                "description": e.description,
                "preflight": [
                    {"kind": p.kind, "value": p.value, "severity": p.severity}
                    for p in e.preflight
                ],
            }
            for name, e in sorted(REGISTRY.items())
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))


def _self_tests() -> None:
    results: list[dict] = []

    def _check(name: str, cond: bool, msg: str) -> None:
        results.append({"name": name, "passed": cond, "message": msg})
        print(f"  {'✅' if cond else '❌'} {name}: {msg}")

    # T1: REGISTRY non-empty
    _check("T1:registry-non-empty", len(REGISTRY) > 0,
           f"{len(REGISTRY)} entries in REGISTRY")

    # T2: every entry's cmd matches its dict key
    mismatches = [k for k, v in REGISTRY.items() if v.cmd != k]
    _check("T2:cmd-key-consistency", not mismatches,
           "all cmd == key" if not mismatches else f"mismatches: {mismatches}")

    # T3: no duplicate modules except explicit public aliases
    allowed_alias_modules = {"flow", "show_task", "project_memory", "autonomous_loop"}
    modules = [e.module for e in REGISTRY.values()]
    dupes = {m for m in modules if modules.count(m) > 1 and m not in allowed_alias_modules}
    _check("T3:no-duplicate-modules", not dupes,
           "no unexpected duplicate modules" if not dupes else f"duplicates: {dupes}")

    # T4: get_commands() returns current Python + .py format
    cmds = get_commands()
    fmt_ok = all(
        isinstance(v, list) and len(v) >= 2
        and v[0] in (PYTHON, "python3") and v[1].endswith(".py")
        for v in cmds.values()
    )
    _check("T4:get-commands-format", fmt_ok,
           f"{len(cmds)} commands with current-python+.py format")

    # T5: INTERNAL_TOOLS are all strings and non-empty
    _check("T5:internal-tools-valid",
           bool(INTERNAL_TOOLS) and all(isinstance(t, str) for t in INTERNAL_TOOLS),
           f"{len(INTERNAL_TOOLS)} internal tools, all strings")

    # T6: new framework modules are in INTERNAL_TOOLS
    new_mods = {"preflight", "session_logger", "tool_registry"}
    ok = new_mods.issubset(INTERNAL_TOOLS)
    _check("T6:new-modules-in-internal", ok,
           f"{new_mods} ⊆ INTERNAL_TOOLS")

    # T7: get_cmd_names() == REGISTRY keys
    _check("T7:cmd-names-consistent",
           set(get_cmd_names()) == set(REGISTRY.keys()),
           "get_cmd_names() matches REGISTRY keys")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    print(f"\n  {passed}/{total} tests pasaron")
    print(json.dumps({"tool": "tool_registry", "status": "ok" if passed == total else "fail",
                      "checks": results}))
    sys.exit(0 if passed == total else 1)


def main() -> None:
    if "--test" in sys.argv:
        _self_tests()
    elif "--json" in sys.argv:
        _cmd_json()
    else:
        _cmd_list()


if __name__ == "__main__":
    main()
