#!/usr/bin/env python3
"""
parsers.py — BAGO CLI surface completo.

Contiene ÚNICAMENTE la definición de argumentos argparse.
Sin lógica de negocio, sin imports de comandos.

Uso:
    from bago_core.parsers import build_parser
    parser = build_parser(version, base, default_provider, default_model)
    args = parser.parse_args(argv)
"""
from __future__ import annotations

import argparse


def build_parser(
    version: str,
    base: str,
    default_provider: str,
    default_model: str,
) -> argparse.ArgumentParser:
    """Construye y devuelve el ArgumentParser completo de BAGO."""

    parser = argparse.ArgumentParser(
        prog="bago",
        description=f"BAGO {version} — Session-First AI Chat",
    )
    parser.add_argument("--provider",  default=default_provider, help="Provider por defecto")
    parser.add_argument("--model",     default=default_model,    help="Modelo por defecto")
    parser.add_argument("--base-path", default=base,             help="Directorio base del proyecto")
    sub = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # ── chat / launch / start / validate ─────────────────────────────────────
    chat_parser     = sub.add_parser("chat",     help="Inicia el REPL de chat")
    chat_parser.add_argument("--no-monitor", action="store_true", help="No arrancar bago monitor en background")
    launch_parser   = sub.add_parser("launch",   help="Alias de chat: inicia BAGO")                                     # noqa: F841
    start_parser    = sub.add_parser("start",    help="Inicia BAGO y autoevoluciona (alias de chat con auto-aprendizaje al arrancar)")  # noqa: F841
    validate_parser = sub.add_parser("validate", help="Gate real de validación: security, contratos, culpas, claims, providers")  # noqa: F841

    # ── install / uninstall ───────────────────────────────────────────────────
    install_parser = sub.add_parser("install", help="Instala/repara BAGO desde la copia local, sin descarga")
    install_parser.add_argument("--source-root",  default="",                       help="Raiz local desde la que instalar")
    install_parser.add_argument("--package-zip",  default="",                       help="ZIP local desde el que instalar")
    install_parser.add_argument("--install-dir",  default="C:\\Program Files\\BAGO", help="Destino de instalacion")
    install_parser.add_argument("--mode",         choices=("Express", "Advanced"), default="", help="Modo de asistente")
    install_parser.add_argument("--repair-only",  action="store_true",              help="Solo repara registro PATH/comando")
    install_parser.add_argument("--skip-tests",   action="store_true",              help="Omite tests internos del instalador")
    install_parser.add_argument("--no-path-update", action="store_true",            help="No modifica PATH")
    install_parser.add_argument("--dry-run",      action="store_true",              help="Muestra lo que haria sin ejecutar")

    uninstall_parser = sub.add_parser("uninstall", help="Desinstala BAGO de la ruta indicada")
    uninstall_parser.add_argument("--install-dir",    default="C:\\Program Files\\BAGO", help="Destino a desinstalar")
    uninstall_parser.add_argument("--backup-root",    default="",                        help="Carpeta para el ZIP de backup")
    uninstall_parser.add_argument("--user-state-dir", default="",                        help="Carpeta de estado a preservar o purgar")
    uninstall_parser.add_argument("--purge-state",    action="store_true",               help="Borra tambien el estado de usuario")
    uninstall_parser.add_argument("--dry-run",        action="store_true",               help="Muestra lo que haria sin ejecutar")
    uninstall_parser.add_argument("--no-elevate",     action="store_true",               help=argparse.SUPPRESS)
    uninstall_parser.add_argument("--elevated-child", action="store_true",               help=argparse.SUPPRESS)

    # ── claim ─────────────────────────────────────────────────────────────────
    claim_parser = sub.add_parser("claim", help="Claim Evidence Ledger — afirmaciones trazables")
    claim_sub    = claim_parser.add_subparsers(dest="claim_action")
    claim_add    = claim_sub.add_parser("add", help="Añade un claim trazable")
    claim_add.add_argument("--claim",     dest="claim_text", required=True)
    claim_add.add_argument("--basis",     required=True)
    claim_add.add_argument("--command",   default="")
    claim_add.add_argument("--artifacts", default="")
    claim_add.add_argument("--limits",    default="")
    claim_add.add_argument("--status",    dest="status_val", default="open")
    claim_add.add_argument("--stdout",    dest="stdout_val", default="")
    claim_add.add_argument("--notes",     default="")
    claim_list   = claim_sub.add_parser("list",   help="Lista claims")
    claim_list.add_argument("--status", dest="filter_status", default="")
    claim_verify = claim_sub.add_parser("verify", help="Verifica artefactos de un claim")
    claim_verify.add_argument("claim_id")
    claim_report = claim_sub.add_parser("report", help="Resumen del ledger")  # noqa: F841

    # ── config ────────────────────────────────────────────────────────────────
    config_parser = sub.add_parser("config", help="Gestiona configuración")
    config_sub    = config_parser.add_subparsers(dest="config_cmd", help="Subcomandos de config")
    config_set    = config_sub.add_parser("set",   help="Establece clave de config")
    config_set.add_argument("key",   nargs="?")
    config_set.add_argument("value", nargs=argparse.REMAINDER)
    config_get    = config_sub.add_parser("get",   help="Obtiene clave de config")
    config_get.add_argument("key", nargs="?")
    config_list   = config_sub.add_parser("list",  help="Lista configuración completa")  # noqa: F841
    config_reset  = config_sub.add_parser("reset", help="Restaura defaults")             # noqa: F841

    # ── llm ───────────────────────────────────────────────────────────────────
    llm_parser = sub.add_parser("llm", help="Gestiona arranque provider-aware")
    llm_parser.add_argument("--include-experimental", action="store_true", help="Incluye providers experimentales fuera del release principal")
    llm_sub   = llm_parser.add_subparsers(dest="llm_action")
    llm_list  = llm_sub.add_parser("list",  help="Lista providers instalados/configurados y disponibles")  # noqa: F841
    llm_start = llm_sub.add_parser("start", help="Inicia BAGO con provider/modelo seleccionado")
    llm_start.add_argument("--provider",          dest="llm_provider", default="",    help="Provider instalado/configurado")
    llm_start.add_argument("--model",             dest="llm_model",    default="",    help="Modelo para la sesión")
    llm_start.add_argument("--allow-unconfigured", action="store_true",               help="Permite arrancar contra provider no configurado")
    llm_start.add_argument("--persist-default",    action="store_true",               help="Guarda provider/modelo como default")
    llm_start.add_argument("--dry-run",            action="store_true",               help="Registra selección sin abrir chat")
    llm_start.add_argument("--no-monitor",         action="store_true",               help="No arrancar bago monitor en background")

    # ── engine / appdata / cmd-rl ─────────────────────────────────────────────
    engine_parser = sub.add_parser("engine", help="Estado del backend avanzado bago_true")
    engine_parser.add_argument("--true-root",   default="", help="Ruta opcional de bago_true\\.bago")
    engine_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    engine_sub    = engine_parser.add_subparsers(dest="engine_action")
    engine_status = engine_sub.add_parser("status", help="Muestra estado de bago_true")  # noqa: F841

    appdata_parser = sub.add_parser("appdata", help="Estado de instalacion AppData BAGO")
    appdata_parser.add_argument("--true-root",   default="", help="Ruta opcional de bago_true\\.bago")
    appdata_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    appdata_sub    = appdata_parser.add_subparsers(dest="appdata_action")
    appdata_status = appdata_sub.add_parser("status", help="Muestra estado de AppData BAGO")  # noqa: F841

    cmd_rl_parser = sub.add_parser("cmd-rl", help="Estado del puente AppData cmd-rl/Spiral")
    cmd_rl_parser.add_argument("--true-root",   default="", help="Ruta opcional de bago_true\\.bago")
    cmd_rl_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    cmd_rl_sub    = cmd_rl_parser.add_subparsers(dest="cmd_rl_action")
    cmd_rl_status = cmd_rl_sub.add_parser("status", help="Muestra soporte cmd-rl/Spiral")  # noqa: F841

    # ── rl ────────────────────────────────────────────────────────────────────
    rl_parser = sub.add_parser("rl", help="RL shadow bridge")
    rl_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    rl_sub    = rl_parser.add_subparsers(dest="rl_action")
    rl_status = rl_sub.add_parser("status", help="Muestra estado RL")  # noqa: F841
    rl_shadow = rl_sub.add_parser("shadow", help="Controla modo shadow")
    rl_shadow.add_argument("shadow_action", nargs="?", choices=("on", "off", "status"), default="status")
    rl_train     = rl_sub.add_parser("train", help="Entrena politicas RL opcionales")
    rl_train_sub = rl_train.add_subparsers(dest="train_action")
    rl_train_bc  = rl_train_sub.add_parser("bc", help="Entrena Behavioral Cloning desde transiciones disponibles")
    rl_train_bc.add_argument("--n-actions",  type=int, default=4)
    rl_train_bc.add_argument("--n-features", type=int, default=4)
    rl_eval = rl_sub.add_parser("eval", help="Evalua politicas RL opcionales")
    rl_eval.add_argument("--n-features", type=int, default=4)

    # ── serve / evidence / cpp-runtime ───────────────────────────────────────
    serve_parser = sub.add_parser("serve", help="Inicia servidor API HTTP")
    serve_parser.add_argument("--host",    default="127.0.0.1", help="Host de escucha (default: 127.0.0.1). Usar 0.0.0.0 requiere --token.")
    serve_parser.add_argument("--port",    type=int, default=8080, help="Puerto (default: 8080)")
    serve_parser.add_argument("--token",   default="", help="Token de autenticación API")
    serve_parser.add_argument("--ui-dist", default="", help="Directorio dist de la UI React (si se omite, intenta ui-react\\dist)")

    evidence_parser = sub.add_parser("evidence", help="Genera bundle de evidencias verificables")
    evidence_parser.add_argument("--mode",      choices=("simulated", "real"), default="simulated", help="Modo de evidencia")
    evidence_parser.add_argument("--objective", default="community-knowledge", help="Objetivo demostrable")
    evidence_parser.add_argument("--output",    help="Directorio de salida del bundle")
    evidence_parser.add_argument("--overwrite", action="store_true", help="Sobrescribe el directorio de salida")
    evidence_parser.add_argument("--test",      action="store_true", help="Ejecuta la prueba interna del generador")

    runtime_parser = sub.add_parser("cpp-runtime", help="Inicia host de referencia para cpp-local")
    runtime_parser.add_argument("--host",          default="127.0.0.1",       help="Host del runtime")
    runtime_parser.add_argument("--port",          type=int, default=8765,    help="Puerto del runtime")
    runtime_parser.add_argument("--runtime-model", default="bago-cpp:default", help="Modelo expuesto por el runtime")
    runtime_parser.add_argument("--test",          action="store_true",        help="Ejecuta la prueba interna del host")

    # ── monitor ───────────────────────────────────────────────────────────────
    monitor_parser = sub.add_parser("monitor", help="Monitor HTML en tiempo real de procesos BAGO")
    monitor_parser.add_argument("--root",    default="",            help="Raíz del proyecto a monitorizar (default: cwd)")
    monitor_parser.add_argument("--port",    type=int, default=7890, help="Puerto HTTP del monitor (default: 7890)")
    monitor_parser.add_argument("--refresh", type=int, default=5,   help="Segundos entre auto-refresh (default: 5)")
    monitor_sub      = monitor_parser.add_subparsers(dest="monitor_cmd")
    monitor_serve    = monitor_sub.add_parser("serve",    help="Sirve el monitor en http://127.0.0.1:PORT/ (default)")  # noqa: F841
    monitor_generate = monitor_sub.add_parser("generate", help="Genera monitor.html estático en .bago/monitor.html")   # noqa: F841

    # ── orchestrate ───────────────────────────────────────────────────────────
    orc_parser = sub.add_parser("orchestrate", help="Orchestrator v4 — Flujo Operativo (Regla Fundamental)")
    orc_parser.add_argument("--root", default="",          help="Raíz del proyecto (default: cwd)")
    orc_parser.add_argument("--json", dest="as_json", action="store_true", help="Output JSON")
    orc_sub    = orc_parser.add_subparsers(dest="orc_cmd")
    orc_list   = orc_sub.add_parser("list",    help="Lista Task Briefs")
    orc_list.add_argument("--status", default="", help="Filtrar por estado (open/assigned/closed)")
    orc_create = orc_sub.add_parser("create",  help="Crea un Task Brief")
    orc_create.add_argument("--task",     required=True, help="Descripción de la tarea")
    orc_create.add_argument("--domain",   default="",    help="Dominio (Backend/Frontend/Producto/Contenido/Deployment)")
    orc_create.add_argument("--priority", default="",    help="Prioridad (P0/P1/P2/Post-MVP)")
    orc_assign = orc_sub.add_parser("assign",  help="Asigna brief a un especialista")
    orc_assign.add_argument("brief_id")
    orc_assign.add_argument("--agent", required=True, help="Agente especialista")
    orc_handoff = orc_sub.add_parser("handoff", help="Genera Handoff formal entre dominios")
    orc_handoff.add_argument("brief_id")
    orc_handoff.add_argument("--from",    dest="from_domain", required=True, help="Dominio origen")
    orc_handoff.add_argument("--to",      dest="to_domain",   required=True, help="Dominio destino")
    orc_handoff.add_argument("--summary", default="",                        help="Resumen del trabajo realizado")
    orc_review = orc_sub.add_parser("review", help="Revisión del Orchestrator (Fase 5)")
    orc_review.add_argument("brief_id")
    orc_review.add_argument("--result", default="approved",
                            choices=["approved", "requires_changes", "reencaminar"],
                            help="Resultado de la revisión")
    orc_close = orc_sub.add_parser("close", help="Cierra un Task Brief (Fase 6)")
    orc_close.add_argument("brief_id")
    orc_close.add_argument("--force", action="store_true", help="Cierra sin revisión previa")
    orc_show  = orc_sub.add_parser("show",  help="Muestra detalle de un brief")
    orc_show.add_argument("brief_id")

    # ── issues (alias operativo para orchestrate) ────────────────────────────
    issues_parser = sub.add_parser("issues", help="Flujo rápido de issues (list/take/close)")
    issues_parser.add_argument("--root", default="", help="Raíz del proyecto (default: cwd)")
    issues_parser.add_argument("--json", dest="as_json", action="store_true", help="Output JSON")
    issues_sub = issues_parser.add_subparsers(dest="issues_cmd")
    issues_list = issues_sub.add_parser("list", help="Lista issues")
    issues_list.add_argument("--status", default="", help="Filtrar por estado")
    issues_take = issues_sub.add_parser("take", help="Toma una issue (asignar agente)")
    issues_take.add_argument("brief_id")
    issues_take.add_argument("--agent", default="codex", help="Agente especialista")
    issues_close = issues_sub.add_parser("close", help="Cierra una issue")
    issues_close.add_argument("brief_id")
    issues_close.add_argument("--force", action="store_true", help="Cierra sin revisión previa")

    # ── scan ──────────────────────────────────────────────────────────────────
    scan_parser = sub.add_parser(
        "scan",
        help="Herramientas de analisis portables "
             "(secrets, deps, todos, tokens, dead, names, sincerity, net, metrics, infra, heal, security, doctor, commit, git, all)",
    )
    scan_parser.add_argument("--root", default="", help="Directorio raiz a escanear (default: cwd)")
    scan_sub = scan_parser.add_subparsers(dest="scan_cmd")

    scan_secrets  = scan_sub.add_parser("secrets",  help="Detecta secretos hardcodeados")
    scan_secrets.add_argument("--severity", default="warning", choices=["error", "warning", "info"])
    scan_secrets.add_argument("--json", dest="as_json", action="store_true")

    scan_deps = scan_sub.add_parser("deps", help="Audita dependencias Python")
    scan_deps.add_argument("--format",    default="text", choices=["text", "md", "json"])
    scan_deps.add_argument("--pip-audit", dest="pip_audit", action="store_true")

    scan_todos = scan_sub.add_parser("todos", help="Lista TODOs, FIXMEs y HACKs")
    scan_todos.add_argument("--fixme", dest="fixme_only", action="store_true")
    scan_todos.add_argument("--count", action="store_true")
    scan_todos.add_argument("--json",  dest="as_json", action="store_true")

    scan_tokens = scan_sub.add_parser("tokens", help="Detecta tokens de API expuestos")
    scan_tokens.add_argument("--fix",  action="store_true", help="Instrucciones de rotacion")
    scan_tokens.add_argument("--json", dest="as_json", action="store_true")

    scan_dead  = scan_sub.add_parser("dead",  help="Detecta codigo muerto (Python)")
    scan_dead.add_argument("--json", dest="as_json", action="store_true")

    scan_names = scan_sub.add_parser("names", help="Valida convenciones de nombres (PEP 8)")
    scan_names.add_argument("--json", dest="as_json", action="store_true")

    scan_all = scan_sub.add_parser("all", help="Ejecuta todos los scans y muestra resumen")  # noqa: F841

    scan_sincerity = scan_sub.add_parser("sincerity", help="Detecta marketing vacio en la documentacion")
    scan_sincerity.add_argument("--strict", action="store_true")
    scan_sincerity.add_argument("--path",   default="")
    scan_sincerity.add_argument("--json",   dest="as_json", action="store_true")

    scan_net = scan_sub.add_parser("net", help="Escanea adaptadores de red y dispositivos locales")
    scan_net.add_argument("--scan",     dest="scan_net", action="store_true")
    scan_net.add_argument("--adapters", action="store_true")
    scan_net.add_argument("--json",     dest="as_json", action="store_true")

    scan_metrics = scan_sub.add_parser("metrics", help="Metricas de codigo: LOC, archivos, tipos")
    scan_metrics.add_argument("--ext",  default="")
    scan_metrics.add_argument("--json", dest="as_json", action="store_true")

    scan_infra = scan_sub.add_parser("infra", help="Escanea servicios locales LLM (Ollama, LM Studio, APIs)")
    scan_infra.add_argument("--quick",    action="store_true")
    scan_infra.add_argument("--all",      dest="all_ports", action="store_true")
    scan_infra.add_argument("--json",     dest="as_json",   action="store_true")

    scan_heal = scan_sub.add_parser("heal", help="Sistema inmune: detecta y repara inconsistencias")
    scan_heal.add_argument("--fix",     action="store_true")
    scan_heal.add_argument("--dry-run", dest="dry_run", action="store_true")
    scan_heal.add_argument("--json",    dest="as_json", action="store_true")

    scan_security = scan_sub.add_parser("security", help="Auditoria de seguridad: tokens, permisos, configs")
    scan_security.add_argument("--fix",  action="store_true")
    scan_security.add_argument("--json", dest="as_json", action="store_true")

    scan_doctor = scan_sub.add_parser("doctor", help="Diagnostico de integridad del proyecto")
    scan_doctor.add_argument("--fix",   action="store_true")
    scan_doctor.add_argument("--quiet", action="store_true")
    scan_doctor.add_argument("--json",  dest="as_json", action="store_true")

    scan_commit = scan_sub.add_parser("commit", help="Pre-commit check rapido")
    scan_commit.add_argument("--all",    dest="all_files", action="store_true")
    scan_commit.add_argument("--strict", action="store_true")
    scan_commit.add_argument("--json",   dest="as_json", action="store_true")

    scan_git = scan_sub.add_parser("git", help="Snapshot del contexto git")
    scan_git.add_argument("--brief", action="store_true")
    scan_git.add_argument("--log",   type=int, default=10)
    scan_git.add_argument("--json",  dest="as_json", action="store_true")

    # ── canary / backup / project ─────────────────────────────────────────────
    canary_parser = sub.add_parser("canary", help="Honeytokens — trampas de deteccion de intrusos")
    canary_parser.add_argument("--root", default="")
    canary_sub    = canary_parser.add_subparsers(dest="canary_cmd")
    canary_deploy = canary_sub.add_parser("deploy")
    canary_deploy.add_argument("--type", default="aws_keys",
                               choices=["aws_keys","openai_api","github_pat","telegram_bot","google_api","all"])
    canary_check = canary_sub.add_parser("check")  # noqa: F841
    canary_list  = canary_sub.add_parser("list")   # noqa: F841
    canary_purge = canary_sub.add_parser("purge")  # noqa: F841

    backup_parser = sub.add_parser("backup", help="Backups del proyecto con rotacion")
    backup_parser.add_argument("--root", default="")
    backup_sub    = backup_parser.add_subparsers(dest="backup_cmd")
    backup_create = backup_sub.add_parser("create")
    backup_create.add_argument("--max", type=int, default=10)
    backup_list   = backup_sub.add_parser("list")  # noqa: F841
    backup_restore = backup_sub.add_parser("restore")
    backup_restore.add_argument("--index", type=int, default=1)

    project_parser = sub.add_parser("project", help="Gestiona la estructura portable .bago del proyecto")
    project_parser.add_argument("--root", default="")
    project_sub    = project_parser.add_subparsers(dest="project_cmd")
    project_init   = project_sub.add_parser("init",   help="Inicializa la estructura .bago")         # noqa: F841
    project_status = project_sub.add_parser("status", help="Muestra el estado actual")               # noqa: F841
    project_link   = project_sub.add_parser("link",   help="Crea el enlace portable del proyecto")   # noqa: F841

    # ── preflight / toolsmith / agent ─────────────────────────────────────────
    preflight_parser = sub.add_parser("preflight", help="Ejecuta checks de preflight portables")
    preflight_parser.add_argument("--root", default="")
    preflight_parser.add_argument("--cmd",  default="")

    toolsmith_parser = sub.add_parser("toolsmith", help="Gestiona toolboxes de agentes")
    toolsmith_parser.add_argument("--root", default="")
    toolsmith_parser.add_argument("--json", dest="toolsmith_json", action="store_true")
    toolsmith_sub     = toolsmith_parser.add_subparsers(dest="toolsmith_cmd")
    toolsmith_catalog = toolsmith_sub.add_parser("catalog", help="Muestra el catalogo")              # noqa: F841
    toolsmith_assign  = toolsmith_sub.add_parser("assign",  help="Asigna herramientas a un agente")
    toolsmith_assign.add_argument("--task",  required=True)
    toolsmith_assign.add_argument("--agent", dest="agent_name", default="")
    toolsmith_assign.add_argument("--sprint", default="backlog")
    toolsmith_sprint = toolsmith_sub.add_parser("sprint", help="Crea toolboxes para un sprint")
    toolsmith_sprint.add_argument("sprint_id")
    toolsmith_sprint.add_argument("--tasks", default="")
    toolsmith_missing = toolsmith_sub.add_parser("missing", help="Lista herramientas faltantes")     # noqa: F841
    toolsmith_create  = toolsmith_sub.add_parser("create",  help="Crea un nuevo tool stub")
    toolsmith_create.add_argument("tool_name")
    toolsmith_create.add_argument("--desc",     default="")
    toolsmith_create.add_argument("--category", default="general")
    toolsmith_listen = toolsmith_sub.add_parser("listen", help="Escucha eventos del bus neural")
    toolsmith_listen.add_argument("--limit", type=int, default=1)

    issues_parser = sub.add_parser("issues-gh", help="Gestiona issues del repositorio")
    issues_parser.add_argument("--root", default="", help="Raíz del proyecto (default: cwd)")
    issues_parser.add_argument("--dry-run", action="store_true", help="No aplica cambios en GitHub")
    issues_sub = issues_parser.add_subparsers(dest="issues_cmd")
    issues_take_gh = issues_sub.add_parser("take", help="Toma la siguiente issue abierta")
    issues_take_gh.add_argument("repo", nargs="?", default="", help="Repositorio owner/name")
    issues_take_gh.add_argument("--agent", default="", help="Agente/usuario a asignar")

    agent_parser = sub.add_parser("agent", help="Gestiona spiral agents")
    agent_parser.add_argument("--root", default="")
    agent_sub   = agent_parser.add_subparsers(dest="agent_cmd")
    agent_spawn = agent_sub.add_parser("spawn", help="Crea un agente")
    agent_spawn.add_argument("agent_id")
    agent_spawn.add_argument("--phase",  type=int, default=0)
    agent_spawn.add_argument("--skills", default="")
    agent_list   = agent_sub.add_parser("list",   help="Lista agentes")                              # noqa: F841
    agent_run    = agent_sub.add_parser("run",    help="Ejecuta un agente")
    agent_run.add_argument("agent_id")
    agent_kill   = agent_sub.add_parser("kill",   help="Desactiva un agente")
    agent_kill.add_argument("agent_id")
    agent_status = agent_sub.add_parser("status", help="Muestra consonancia entre agentes")          # noqa: F841

    # ── guard ─────────────────────────────────────────────────────────────────
    guard_parser = sub.add_parser("guard", help="Guardián de deuda técnica — previene patrones antes de commitear")
    guard_parser.add_argument("--root", default="", help="Raíz del proyecto (default: cwd)")
    guard_sub = guard_parser.add_subparsers(dest="guard_cmd")
    guard_sub.add_parser("install",   help="Instala hook git pre-commit")
    guard_sub.add_parser("uninstall", help="Elimina hook git pre-commit")
    guard_sub.add_parser("status",    help="Muestra estado del hook y reglas activas")
    guard_check = guard_sub.add_parser("check", help="Verifica archivos staged (o todos con --all)")
    guard_check.add_argument("--all", dest="all_files", action="store_true",
                             help="Verificar todos los .py, no sólo staged")
    guard_config = guard_sub.add_parser("config", help="Gestiona reglas activas")
    guard_config_sub = guard_config.add_subparsers(dest="config_action")
    guard_config_sub.add_parser("show",  help="Muestra configuración actual")
    guard_config_sub.add_parser("reset", help="Restaura configuración a defaults")
    guard_enable = guard_config_sub.add_parser("enable",  help="Activa una regla (D01…D10)")
    guard_enable.add_argument("rule_code")
    guard_disable = guard_config_sub.add_parser("disable", help="Desactiva una regla (D01…D10)")
    guard_disable.add_argument("rule_code")
    guard_setaction = guard_config_sub.add_parser("set-action", help="Cambia acción: block o warn")
    guard_setaction.add_argument("rule_code")
    guard_setaction.add_argument("action_value")

    # ── route / inventory ─────────────────────────────────────────────────────
    route_parser = sub.add_parser("route", help="Gestión de presets de routing y contrato activo")
    route_sp = route_parser.add_subparsers(dest="route_cmd", required=False)
    route_status = route_sp.add_parser("status", help="Muestra el preset activo y el contrato")
    route_status.add_argument("--user-bago", default=None)
    route_status.add_argument("--repo", default=None)
    route_status.add_argument("--json", action="store_true")
    route_status.add_argument("--tolerant", action="store_true")
    route_validate = route_sp.add_parser("validate", help="Valida el preset activo o uno nombrado")
    route_validate.add_argument("--preset", default=None)
    route_validate.add_argument("--user-bago", default=None)
    route_validate.add_argument("--repo", default=None)
    route_validate.add_argument("--json", action="store_true")
    route_activate = route_sp.add_parser("activate", help="Activa un preset y reescribe routing_runtime.json")
    route_activate.add_argument("--preset", required=True)
    route_activate.add_argument("--user-bago", default=None)
    route_activate.add_argument("--repo", default=None)
    # Compatibilidad con flags antiguos (--root, --task, etc.) — se ignoran silenciosamente
    for legacy in ("--root", "--task", "--history", "--limit", "--no-classifier"):
        route_parser.add_argument(legacy, nargs="?", default=None)

    inv_parser = sub.add_parser("inventory", help="Cataloga capacidades del proyecto")
    inv_parser.add_argument("--root",   default="")
    inv_parser.add_argument("--format", default="text", choices=["text", "md", "json"])

    # ── list-installs (gestor de instalaciones para el landing) ────────────
    installs_parser = sub.add_parser("list-installs", help="Escanea el sistema e imprime JSON con todas las instalaciones BAGO (para el gestor de la landing)")
    installs_parser.add_argument("--plain",        action="store_true", help="JSON compacto en una línea (fácil de pegar en la web)")
    installs_parser.add_argument("--active-only",  action="store_true", help="Solo listar instalaciones que existen")

    # ── node (control centralizado de instalaciones/piezas/conectores) ─────
    node_parser = sub.add_parser("node", help="Control centralizado: registry, policy, evidence, modos")
    node_sub = node_parser.add_subparsers(dest="node_cmd", help="Subcomandos node")
    for nc in ("status", "validate", "pieces", "connectors", "matrix", "export", "tui"):
        node_sub.add_parser(nc, help=f"bago node {nc}")

    return parser
