#!/usr/bin/env python3
from __future__ import annotations

import argparse

from bago_core.install_roles import ROLES

def add_session_parsers(sub: argparse._SubParsersAction) -> None:
    def _add_chat_flags(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--no-monitor", action="store_true", help="No arrancar bago monitor en background")
        parser.add_argument(
            "--no-ollama-autostart",
            action="store_true",
            help="No arrancar ollama.exe automaticamente si el provider es ollama-local",
        )

    chat_parser = sub.add_parser("chat", help="Inicia el REPL de chat")
    _add_chat_flags(chat_parser)
    launch_parser = sub.add_parser("launch", help="Alias de chat: inicia BAGO")
    _add_chat_flags(launch_parser)
    start_parser = sub.add_parser("start", help="Inicia BAGO y autoevoluciona (alias de chat con auto-aprendizaje al arrancar)")
    _add_chat_flags(start_parser)
    exec_parser = sub.add_parser("exec", help="Ejecuta un comando slash sin abrir el REPL")
    exec_parser.add_argument("slash_command", nargs=argparse.REMAINDER, help="Comando slash a ejecutar, por ejemplo /status")
    sub.add_parser("validate", help="Gate real de validacion: security, contratos, culpas, claims, providers")
    sub.add_parser("profiles", help="Muestra el mapa de stable/des/ign y el flujo recomendado")

    context_parser = sub.add_parser("context", help="Inspecciona, mide y certifica el contexto real")
    context_sub = context_parser.add_subparsers(dest="context_cmd")
    for name, help_text in (
        ("inspect", "Muestra el contexto actual"),
        ("measure", "Mide presupuesto y herramientas"),
        ("benchmark", "Ejecuta benchmark del contexto"),
        ("certify", "Certifica el contexto actual"),
        ("history", "Muestra historial y timeline"),
        ("invalidate", "Invalida la certificacion de contexto"),
        ("calibrate", "Recalibra contexto y benchmark"),
        ("tune", "Ajuste manual bloqueado por defecto"),
    ):
        subparser = context_sub.add_parser(name, help=help_text)
        if name in ("benchmark", "calibrate"):
            subparser.add_argument("--iterations", type=int, default=3, help="Iteraciones para benchmark/calibrate")
        if name == "benchmark":
            subparser.add_argument("--cognitive", action="store_true", help="Incluye la bateria cognitiva adversarial")
        if name == "history":
            subparser.add_argument("--limit", type=int, default=10, help="Historial maximo para context history")
        if name in ("invalidate", "tune"):
            subparser.add_argument("--confirm", action="store_true", help="Autoriza invalidate/tune")
        if name == "invalidate":
            subparser.add_argument("--reason", default="", help="Motivo para invalidate")

    install_parser = sub.add_parser("install", help="Instala/repara BAGO desde la copia local, sin descarga")
    install_parser.add_argument("--source-root", default="", help="Raiz local desde la que instalar")
    install_parser.add_argument("--package-zip", default="", help="ZIP local desde el que instalar")
    install_parser.add_argument("--profile", default="", choices=("stable", "des", "ign"), help="Perfil de instalacion")
    install_parser.add_argument("--install-dir", default="", help="Destino de instalacion")
    install_parser.add_argument("--mode", choices=("Express", "Advanced"), default="", help="Modo de asistente")
    install_parser.add_argument("--repair-only", action="store_true", help="Solo repara registro PATH/comando")
    install_parser.add_argument("--skip-tests", action="store_true", help="Omite tests internos del instalador")
    install_parser.add_argument("--no-path-update", action="store_true", help="No modifica PATH")
    install_parser.add_argument("--dry-run", action="store_true", help="Muestra lo que haria sin ejecutar")

    uninstall_parser = sub.add_parser("uninstall", help="Desinstala BAGO de la ruta indicada")
    uninstall_parser.add_argument("--profile", default="", choices=("stable", "des", "ign"), help="Perfil a desinstalar")
    uninstall_parser.add_argument("--install-dir", default="", help="Destino a desinstalar")
    uninstall_parser.add_argument("--backup-root", default="", help="Carpeta para el ZIP de backup")
    uninstall_parser.add_argument("--user-state-dir", default="", help="Carpeta de estado a preservar o purgar")
    uninstall_parser.add_argument("--purge-state", action="store_true", help="Borra tambien el estado de usuario")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Muestra lo que haria sin ejecutar")
    uninstall_parser.add_argument("--no-elevate", action="store_true", help=argparse.SUPPRESS)
    uninstall_parser.add_argument("--elevated-child", action="store_true", help=argparse.SUPPRESS)

    claim_parser = sub.add_parser("claim", help="Claim Evidence Ledger -- afirmaciones trazables")
    claim_sub = claim_parser.add_subparsers(dest="claim_action")
    claim_add = claim_sub.add_parser("add", help="Anade un claim trazable")
    claim_add.add_argument("--claim", dest="claim_text", required=True)
    claim_add.add_argument("--basis", required=True)
    claim_add.add_argument("--command", default="")
    claim_add.add_argument("--artifacts", default="")
    claim_add.add_argument("--limits", default="")
    claim_add.add_argument("--status", dest="status_val", default="open")
    claim_add.add_argument("--stdout", dest="stdout_val", default="")
    claim_add.add_argument("--notes", default="")
    claim_list = claim_sub.add_parser("list", help="Lista claims")
    claim_list.add_argument("--status", dest="filter_status", default="")
    claim_verify = claim_sub.add_parser("verify", help="Verifica artefactos de un claim")
    claim_verify.add_argument("claim_id")
    claim_sub.add_parser("report", help="Resumen del ledger")

    config_parser = sub.add_parser("config", help="Gestiona configuracion")
    config_sub = config_parser.add_subparsers(dest="config_cmd", help="Subcomandos de config")
    config_set = config_sub.add_parser("set", help="Establece clave de config")
    config_set.add_argument("key", nargs="?")
    config_set.add_argument("value", nargs=argparse.REMAINDER)
    config_get = config_sub.add_parser("get", help="Obtiene clave de config")
    config_get.add_argument("key", nargs="?")
    config_sub.add_parser("list", help="Lista configuracion completa")
    config_sub.add_parser("reset", help="Restaura defaults")

    llm_parser = sub.add_parser("llm", help="Gestiona arranque provider-aware")
    llm_parser.add_argument("--include-experimental", action="store_true", help="Incluye providers experimentales fuera del release principal")
    llm_sub = llm_parser.add_subparsers(dest="llm_action")
    llm_sub.add_parser("list", help="Lista providers instalados/configurados y disponibles")
    llm_start = llm_sub.add_parser("start", help="Inicia BAGO con provider/modelo seleccionado")
    llm_start.add_argument("--provider", dest="llm_provider", default="", help="Provider instalado/configurado")
    llm_start.add_argument("--model", dest="llm_model", default="", help="Modelo para la sesion")
    llm_start.add_argument("--bridge", dest="llm_bridges", action="append", default=[], help="Provider adicional activo; repetible")
    llm_start.add_argument("--allow-unconfigured", action="store_true", help="Permite arrancar contra provider no configurado")
    llm_start.add_argument("--persist-default", action="store_true", help="Guarda provider/modelo como default")
    llm_start.add_argument("--dry-run", action="store_true", help="Registra seleccion sin abrir chat")
    llm_start.add_argument("--no-monitor", action="store_true", help="No arrancar bago monitor en background")
    llm_start.add_argument("--no-ollama-autostart", action="store_true", help="No arrancar ollama.exe automaticamente si el provider es ollama-local")

    engine_parser = sub.add_parser("engine", help="Estado del backend avanzado bago_true")
    engine_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    engine_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    engine_sub = engine_parser.add_subparsers(dest="engine_action")
    engine_sub.add_parser("status", help="Muestra estado de bago_true")

    appdata_parser = sub.add_parser("appdata", help="Estado de instalacion AppData BAGO")
    appdata_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    appdata_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    appdata_sub = appdata_parser.add_subparsers(dest="appdata_action")
    appdata_sub.add_parser("status", help="Muestra estado de AppData BAGO")

    cmd_rl_parser = sub.add_parser("cmd-rl", help="Estado del puente AppData cmd-rl/Spiral")
    cmd_rl_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    cmd_rl_parser.add_argument("--appdata-root", default="", help="Ruta opcional de AppData BAGO")
    cmd_rl_sub = cmd_rl_parser.add_subparsers(dest="cmd_rl_action")
    cmd_rl_sub.add_parser("status", help="Muestra soporte cmd-rl/Spiral")

    rl_parser = sub.add_parser("rl", help="RL shadow bridge")
    rl_parser.add_argument("--true-root", default="", help="Ruta opcional de bago_true\\.bago")
    rl_sub = rl_parser.add_subparsers(dest="rl_action")
    rl_sub.add_parser("status", help="Muestra estado RL")
    rl_shadow = rl_sub.add_parser("shadow", help="Controla modo shadow")
    rl_shadow.add_argument("shadow_action", nargs="?", choices=("on", "off", "status"), default="status")
    rl_train = rl_sub.add_parser("train", help="Entrena politicas RL opcionales")
    rl_train_sub = rl_train.add_subparsers(dest="train_action")
    rl_train_bc = rl_train_sub.add_parser("bc", help="Entrena Behavioral Cloning desde transiciones disponibles")
    rl_train_bc.add_argument("--n-actions", type=int, default=4)
    rl_train_bc.add_argument("--n-features", type=int, default=4)
    rl_eval = rl_sub.add_parser("eval", help="Evalua politicas RL opcionales")
    rl_eval.add_argument("--n-features", type=int, default=4)

    serve_parser = sub.add_parser("serve", help="Inicia servidor API HTTP")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host de escucha (default: 127.0.0.1). Usar 0.0.0.0 requiere --token.")
    serve_parser.add_argument("--port", type=int, default=8080, help="Puerto (default: 8080)")
    serve_parser.add_argument("--token", default="", help="Token de autenticacion API")
    serve_parser.add_argument("--ui-dist", default="", help="Directorio dist de la UI React (si se omite, intenta ui-react\\dist)")

    manager_parser = sub.add_parser("manager", help="Abre la UI compilada unificada en el navegador")
    manager_parser.add_argument("--host", default="127.0.0.1", help="Host para el servidor local (default: 127.0.0.1)")
    manager_parser.add_argument("--port", type=int, default=8080, help="Puerto del servidor local (default: 8080)")
    manager_parser.add_argument("--ui-dist", default="", help="Directorio dist de la UI React (si se omite, intenta ui-react\\dist)")

    api_parser = sub.add_parser("api", help="Inspeccion del bridge HTTP (sin arrancarlo)")
    api_sub = api_parser.add_subparsers(dest="api_cmd")
    api_list = api_sub.add_parser("list-routes", help="Lista las rutas que sirve el bridge BAGO")
    api_list.add_argument("--method", choices=("GET", "POST", "ALL"), default="ALL", help="Filtrar por metodo HTTP")
    api_list.add_argument("--pattern", action="store_true", help="Mostrar solo rutas con parametros (<...>)")
    api_list.add_argument("--json", dest="as_json", action="store_true", help="Salida en JSON en vez de tabla")
    api_list.add_argument("--root", default="", help="Raiz del proyecto (default: cwd)")

    evidence_parser = sub.add_parser("evidence", help="Genera bundle de evidencias verificables")
    evidence_parser.add_argument("--mode", choices=("simulated", "real"), default="simulated", help="Modo de evidencia")
    evidence_parser.add_argument("--objective", default="community-knowledge", help="Objetivo demostrable")
    evidence_parser.add_argument("--output", help="Directorio de salida del bundle")
    evidence_parser.add_argument("--overwrite", action="store_true", help="Sobrescribe el directorio de salida")
    evidence_parser.add_argument("--test", action="store_true", help="Ejecuta la prueba interna del generador")

    monitor_parser = sub.add_parser("monitor", help="Monitor HTML en tiempo real de procesos BAGO")
    monitor_parser.add_argument("--root", default="", help="Raiz del proyecto a monitorizar (default: cwd)")
    monitor_parser.add_argument("--port", type=int, default=7890, help="Puerto HTTP del monitor (default: 7890)")
    monitor_parser.add_argument("--refresh", type=int, default=5, help="Segundos entre auto-refresh (default: 5)")
    monitor_sub = monitor_parser.add_subparsers(dest="monitor_cmd")
    monitor_sub.add_parser("serve", help="Sirve el monitor en http://127.0.0.1:PORT/ (default)")
    monitor_sub.add_parser("generate", help="Genera monitor.html estatico en .bago/monitor.html")

    doctor_parser = sub.add_parser("doctor", help="Salud integral de la instalacion BAGO")
    doctor_parser.add_argument("--json", action="store_true", help="Output JSON")

def add_ops_parsers(sub: argparse._SubParsersAction) -> None:
    orc_parser = sub.add_parser("orchestrate", help="Orchestrator v4 -- Flujo Operativo (Regla Fundamental)")
    orc_parser.add_argument("--root", default="", help="Raiz del proyecto (default: cwd)")
    orc_parser.add_argument("--json", dest="as_json", action="store_true", help="Output JSON")
    orc_sub = orc_parser.add_subparsers(dest="orc_cmd")
    orc_list = orc_sub.add_parser("list", help="Lista Task Briefs")
    orc_list.add_argument("--status", default="", help="Filtrar por estado (open/assigned/closed)")
    orc_create = orc_sub.add_parser("create", help="Crea un Task Brief")
    orc_create.add_argument("--task", required=True, help="Descripcion de la tarea")
    orc_create.add_argument("--domain", default="", help="Dominio (Backend/Frontend/Producto/Contenido/Deployment)")
    orc_create.add_argument("--priority", default="", help="Prioridad (P0/P1/P2/Post-MVP)")
    orc_assign = orc_sub.add_parser("assign", help="Asigna brief a un especialista")
    orc_assign.add_argument("brief_id")
    orc_assign.add_argument("--agent", required=True, help="Agente especialista")
    orc_handoff = orc_sub.add_parser("handoff", help="Genera Handoff formal entre dominios")
    orc_handoff.add_argument("brief_id")
    orc_handoff.add_argument("--from", dest="from_domain", required=True, help="Dominio origen")
    orc_handoff.add_argument("--to", dest="to_domain", required=True, help="Dominio destino")
    orc_handoff.add_argument("--summary", default="", help="Resumen del trabajo realizado")
    orc_review = orc_sub.add_parser("review", help="Revision del Orchestrator (Fase 5)")
    orc_review.add_argument("brief_id")
    orc_review.add_argument("--result", default="approved", choices=["approved", "requires_changes", "reencaminar"], help="Resultado de la revision")
    orc_close = orc_sub.add_parser("close", help="Cierra un Task Brief (Fase 6)")
    orc_close.add_argument("brief_id")
    orc_close.add_argument("--force", action="store_true", help="Cierra sin revision previa")
    orc_show = orc_sub.add_parser("show", help="Muestra detalle de un brief")
    orc_show.add_argument("brief_id")

    issues_parser = sub.add_parser("issues", help="Flujo rapido de issues (list/take/close)")
    issues_parser.add_argument("--root", default="", help="Raiz del proyecto (default: cwd)")
    issues_parser.add_argument("--json", dest="as_json", action="store_true", help="Output JSON")
    issues_parser.add_argument("--dry-run", action="store_true", help="Previsualiza sin mutar GitHub")
    issues_sub = issues_parser.add_subparsers(dest="issues_cmd")
    issues_list = issues_sub.add_parser("list", help="Lista issues")
    issues_list.add_argument("--status", default="", help="Filtrar por estado")
    issues_take = issues_sub.add_parser("take", help="Toma una issue (asignar agente)")
    issues_take.add_argument("brief_id", nargs="?", default="")
    issues_take.add_argument("--agent", default="", help="Agente especialista")
    issues_close = issues_sub.add_parser("close", help="Cierra una issue")
    issues_close.add_argument("brief_id")
    issues_close.add_argument("--force", action="store_true", help="Cierra sin revision previa")

    scan_parser = sub.add_parser("scan", help="Herramientas de analisis portables (secrets, deps, todos, tokens, dead, names, sincerity, net, metrics, infra, heal, security, doctor, commit, git, all)")
    scan_parser.add_argument("--root", default="", help="Directorio raiz a escanear (default: cwd)")
    scan_sub = scan_parser.add_subparsers(dest="scan_cmd")
    for name, kwargs in (
        ("secrets", {"help": "Detecta secretos hardcodeados"}),
        ("deps", {"help": "Audita dependencias Python"}),
        ("forced", {"help": "Detecta dependencias forzadas y pins raros"}),
        ("todos", {"help": "Lista TODOs, FIXMEs y HACKs"}),
        ("tokens", {"help": "Detecta tokens de API expuestos"}),
        ("dead", {"help": "Detecta codigo muerto (Python)"}),
        ("names", {"help": "Valida convenciones de nombres (PEP 8)"}),
        ("all", {"help": "Ejecuta todos los scans y muestra resumen"}),
        ("sincerity", {"help": "Detecta marketing vacio en la documentacion"}),
        ("net", {"help": "Escanea adaptadores de red y dispositivos locales"}),
        ("metrics", {"help": "Metricas de codigo: LOC, archivos, tipos"}),
        ("infra", {"help": "Escanea servicios locales LLM (Ollama, LM Studio, APIs)"}),
        ("heal", {"help": "Sistema inmune: detecta y repara inconsistencias"}),
        ("security", {"help": "Auditoria de seguridad: tokens, permisos, configs"}),
        ("doctor", {"help": "Diagnostico de integridad del proyecto"}),
        ("commit", {"help": "Pre-commit check rapido"}),
        ("git", {"help": "Snapshot del contexto git"}),
    ):
        scan_cmd = scan_sub.add_parser(name, **kwargs)
        scan_cmd.add_argument("--root", default=argparse.SUPPRESS, help="Directorio raiz a escanear (default: cwd)")
    # arguments for individual scan commands are attached in build_parser for brevity.

    canary_parser = sub.add_parser("canary", help="Honeytokens -- trampas de deteccion de intrusos")
    canary_parser.add_argument("--root", default="")
    canary_sub = canary_parser.add_subparsers(dest="canary_cmd")
    canary_deploy = canary_sub.add_parser("deploy")
    canary_deploy.add_argument("--type", default="aws_keys", choices=["aws_keys", "openai_api", "github_pat", "telegram_bot", "google_api", "all"])
    canary_sub.add_parser("check")
    canary_sub.add_parser("list")
    canary_sub.add_parser("purge")

    backup_parser = sub.add_parser("backup", help="Backups del proyecto con rotacion")
    backup_parser.add_argument("--root", default="")
    backup_sub = backup_parser.add_subparsers(dest="backup_cmd")
    backup_create = backup_sub.add_parser("create")
    backup_create.add_argument("--max", type=int, default=10)
    backup_sub.add_parser("list")
    backup_restore = backup_sub.add_parser("restore")
    backup_restore.add_argument("--index", type=int, default=1)

    project_parser = sub.add_parser("project", help="Gestiona la estructura portable .bago del proyecto")
    project_parser.add_argument("--root", default="")
    project_sub = project_parser.add_subparsers(dest="project_cmd")
    project_init = project_sub.add_parser("init", help="Inicializa la estructura .bago")
    project_init.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    project_status = project_sub.add_parser("status", help="Muestra el estado actual")
    project_status.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    project_link = project_sub.add_parser("link", help="Crea el enlace portable del proyecto")
    project_link.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    project_analyze = project_sub.add_parser("analyze", help="Analiza el proyecto y sugiere próximos pasos")
    project_analyze.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")

    preflight_parser = sub.add_parser("preflight", help="Ejecuta checks de preflight portables")
    preflight_parser.add_argument("--root", default="")
    preflight_parser.add_argument("--cmd", default="")

    toolsmith_parser = sub.add_parser("toolsmith", help="Gestiona toolboxes de agentes")
    toolsmith_parser.add_argument("--root", default="")
    toolsmith_parser.add_argument("--json", dest="toolsmith_json", action="store_true")
    toolsmith_sub = toolsmith_parser.add_subparsers(dest="toolsmith_cmd")
    toolsmith_catalog = toolsmith_sub.add_parser("catalog", help="Muestra el catalogo")
    toolsmith_catalog.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    toolsmith_assign = toolsmith_sub.add_parser("assign", help="Asigna herramientas a un agente")
    toolsmith_assign.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    toolsmith_assign.add_argument("--task", required=True)
    toolsmith_assign.add_argument("--agent", dest="agent_name", default="")
    toolsmith_assign.add_argument("--sprint", default="backlog")
    toolsmith_sprint = toolsmith_sub.add_parser("sprint", help="Crea toolboxes para un sprint")
    toolsmith_sprint.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    toolsmith_sprint.add_argument("sprint_id")
    toolsmith_sprint.add_argument("--tasks", default="")
    toolsmith_missing = toolsmith_sub.add_parser("missing", help="Lista herramientas faltantes")
    toolsmith_missing.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    toolsmith_create = toolsmith_sub.add_parser("create", help="Crea un nuevo tool stub")
    toolsmith_create.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    toolsmith_create.add_argument("tool_name")
    toolsmith_create.add_argument("--desc", default="")
    toolsmith_create.add_argument("--category", default="general")
    toolsmith_listen = toolsmith_sub.add_parser("listen", help="Escucha eventos del bus neural")
    toolsmith_listen.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    toolsmith_listen.add_argument("--limit", type=int, default=1)

    issues_gh_parser = sub.add_parser("issues-gh", help="Gestiona issues del repositorio")
    issues_gh_parser.add_argument("--root", default="", help="Raiz del proyecto (default: cwd)")
    issues_gh_parser.add_argument("--dry-run", action="store_true", help="No aplica cambios en GitHub")
    issues_gh_sub = issues_gh_parser.add_subparsers(dest="issues_gh_cmd")
    issues_gh_take = issues_gh_sub.add_parser("take", help="Toma la siguiente issue abierta")
    issues_gh_take.add_argument("repo", nargs="?", default="", help="Repositorio owner/name")
    issues_gh_take.add_argument("--agent", default="", help="Agente/usuario a asignar")

    agent_parser = sub.add_parser("agent", help="Gestiona spiral agents")
    agent_parser.add_argument("--root", default="")
    agent_sub = agent_parser.add_subparsers(dest="agent_cmd")
    agent_spawn = agent_sub.add_parser("spawn", help="Crea un agente")
    agent_spawn.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    agent_spawn.add_argument("agent_id")
    agent_spawn.add_argument("--phase", type=int, default=0)
    agent_spawn.add_argument("--skills", default="")
    agent_list = agent_sub.add_parser("list", help="Lista agentes")
    agent_list.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    agent_run = agent_sub.add_parser("run", help="Ejecuta un agente")
    agent_run.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    agent_run.add_argument("agent_id")
    agent_kill = agent_sub.add_parser("kill", help="Desactiva un agente")
    agent_kill.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    agent_kill.add_argument("agent_id")
    agent_status = agent_sub.add_parser("status", help="Muestra consonancia entre agentes")
    agent_status.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    agent_route = agent_sub.add_parser("route", help="Enruta una tarea al mejor agente disponible")
    agent_route.add_argument("--root", default=argparse.SUPPRESS, help="Raiz del proyecto (default: cwd)")
    agent_route.add_argument("--task", default="", help="Texto de la tarea a enrutar")
    agent_route.add_argument("--json", action="store_true", help="Salida JSON")
    agent_route.add_argument("--history", action="store_true", help="Muestra historial de rutas")
    agent_route.add_argument("--limit", type=int, default=10, help="Limite del historial")
    agent_route.add_argument("--no-classifier", action="store_true", help="Desactiva clasificador Ollama")
    agent_route.add_argument("task_words", nargs="*", default=[], help="Texto de la tarea como palabras sueltas")

    guard_parser = sub.add_parser("guard", help="Guardian de deuda tecnica -- previene patrones antes de commitear")
    guard_parser.add_argument("--root", default="", help="Raiz del proyecto (default: cwd)")
    guard_sub = guard_parser.add_subparsers(dest="guard_cmd")
    guard_sub.add_parser("install", help="Instala hook git pre-commit")
    guard_sub.add_parser("uninstall", help="Elimina hook git pre-commit")
    guard_sub.add_parser("status", help="Muestra estado del hook y reglas activas")
    guard_check = guard_sub.add_parser("check", help="Verifica archivos staged (o todos con --all)")
    guard_check.add_argument("--all", dest="all_files", action="store_true", help="Verificar todos los .py, no solo staged")
    guard_config = guard_sub.add_parser("config", help="Gestiona reglas activas")
    guard_config_sub = guard_config.add_subparsers(dest="config_action")
    guard_config_sub.add_parser("show", help="Muestra configuracion actual")
    guard_config_sub.add_parser("reset", help="Restaura configuracion a defaults")
    guard_enable = guard_config_sub.add_parser("enable", help="Activa una regla (D01...D10)")
    guard_enable.add_argument("rule_code")
    guard_disable = guard_config_sub.add_parser("disable", help="Desactiva una regla (D01...D10)")
    guard_disable.add_argument("rule_code")
    guard_setaction = guard_config_sub.add_parser("set-action", help="Cambia accion: block o warn")
    guard_setaction.add_argument("rule_code")
    guard_setaction.add_argument("action_value")

    route_parser = sub.add_parser("route", help="Gestion de presets de routing y contrato activo")
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
    for legacy in ("--root", "--task", "--history", "--limit", "--no-classifier"):
        route_parser.add_argument(legacy, nargs="?", default=None)

    inv_parser = sub.add_parser("inventory", help="Cataloga capacidades del proyecto")
    inv_parser.add_argument("--root", default="")
    inv_parser.add_argument("--format", default="text", choices=["text", "md", "json"])

    installs_parser = sub.add_parser("list-installs", help="Escanea el sistema e imprime JSON con todas las instalaciones BAGO (para el gestor de la landing)")
    installs_parser.add_argument("--plain", action="store_true", help="JSON compacto en una linea (facil de pegar en la web)")
    installs_parser.add_argument("--active-only", action="store_true", help="Solo listar instalaciones que existen")

    roles_parser = sub.add_parser("install-role", help="Elige que copia BAGO se usa como active/dev/launch/escritor/ilustrador")
    roles_parser.add_argument("--json", action="store_true", help="Salida JSON")
    roles_sub = roles_parser.add_subparsers(dest="install_role_cmd")
    roles_show = roles_sub.add_parser("show", help="Muestra la seleccion actual")
    roles_show.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    roles_set = roles_sub.add_parser("set", help="Fija un rol a una ruta")
    roles_set.add_argument("--role", required=True, choices=ROLES)
    roles_set.add_argument("--path", required=True)
    roles_set.add_argument("--no-strict", action="store_true")
    roles_set.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    roles_clear = roles_sub.add_parser("clear", help="Borra un rol o toda la seleccion")
    roles_clear.add_argument("--role", choices=ROLES, default="")
    roles_clear.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

def add_node_parsers(sub: argparse._SubParsersAction) -> None:
    node_parser = sub.add_parser("node", help="Gestor de registry, policy, evidence y compatibilidad")
    node_parser.add_argument("--base-path", default="", help="Base path del runtime Node Control")
    node_parser.add_argument("--json", action="store_true", help="Salida JSON")
    node_sub = node_parser.add_subparsers(dest="node_cmd")
    node_status = node_sub.add_parser("status", help="Muestra el estado del registry y policy")
    node_status.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_validate = node_sub.add_parser("validate", help="Valida registry, policy, evidence y compatibilidad")
    node_validate.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_pieces = node_sub.add_parser("pieces", help="Lista piezas del PieceStore")
    node_pieces.add_argument("--type", default="")
    node_pieces.add_argument("--scope", default="")
    node_pieces.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_connectors = node_sub.add_parser("connectors", help="Lista conectores del registry")
    node_connectors.add_argument("--installation", default="")
    node_connectors.add_argument("--piece", default="")
    node_connectors.add_argument("--mode", default="")
    node_connectors.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_matrix = node_sub.add_parser("matrix", help="Muestra la matriz Installation x Piece")
    node_matrix.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_evidence = node_sub.add_parser("evidence", help="Muestra el tail real del evidence ledger")
    node_evidence.add_argument("--limit", type=int, default=25)
    node_evidence.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_preview = node_sub.add_parser("preview", help="Previsualiza una mutacion sin aplicarla")
    node_preview.add_argument("--installation", required=True)
    node_preview.add_argument("--piece", required=True)
    node_preview.add_argument("--mode", required=True, choices=("connected", "shadow", "locked", "detached", "readonly", "overlay"))
    node_preview.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_connect = node_sub.add_parser("connect", help="Conecta una installation con una piece")
    node_connect.add_argument("--installation", required=True)
    node_connect.add_argument("--piece", required=True)
    node_connect.add_argument("--mode", default="connected", choices=("connected", "shadow", "locked", "readonly", "overlay"))
    node_connect.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_disconnect = node_sub.add_parser("disconnect", help="Desconecta una installation de una piece")
    node_disconnect.add_argument("--installation", required=True)
    node_disconnect.add_argument("--piece", required=True)
    node_disconnect.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_set_mode = node_sub.add_parser("set-mode", help="Cambia el modo de un connector")
    node_set_mode.add_argument("--installation", required=True)
    node_set_mode.add_argument("--piece", required=True)
    node_set_mode.add_argument("--mode", required=True, choices=("connected", "shadow", "locked", "readonly", "overlay"))
    node_set_mode.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_export = node_sub.add_parser("export", help="Exporta el estado del registry a JSON")
    node_export.add_argument("--output", default="")
    node_export.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    node_sub.add_parser("tui", aliases=("terminal",), help="Interfaz de terminal interactiva del gestor")

    add_translator_parser(node_sub)

def add_translator_parser(node_sub: argparse._SubParsersAction) -> None:
    """Register the `bago node translator <subcmd>` subcommand group (FASE 12).

    Runtime dispatch lives in :mod:`bago_core.node_control_translator`.
    This is just the argparse surface -- keep the rule:
    * parser shape -> parsers_sections.py / parsers.py
    * render       -> node_control_render.py
    * dispatch     -> node_control_translator.py (and node_control.py for facade)
    * model/state  -> node_control_store.py / node_control_ssot.py
    * policy       -> node_control_policy.py
    * network      -> (resolver en node_control_store/_connect via SSoT)
    * interactive  -> node_control_tui.py
    """
    translator_p = node_sub.add_parser("translator", help="Gestiona piezas traductoras (BAGO IR <-> modelo)")
    translator_sub = translator_p.add_subparsers(dest="translator_command")

    t_list = translator_sub.add_parser("list", help="Lista las piezas traductoras instaladas")
    t_list.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    t_show = translator_sub.add_parser("show", help="Muestra el detalle de una pieza traductora")
    t_show.add_argument("piece_id", help="ID de la pieza traductora (ej. translator.openai.gpt-4o)")
    t_show.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    t_validate = translator_sub.add_parser("validate", help="Smoke test encode->decode roundtrip")
    t_validate.add_argument("piece_id", nargs="?", default="", help="ID de pieza o vacio para todas")
    t_validate.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    t_map = translator_sub.add_parser("map", help="Preview encode de un IR de ejemplo al dialecto de la pieza")
    t_map.add_argument("piece_id", help="ID de la pieza traductora")
    t_map.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    t_call = translator_sub.add_parser("call", help="FASE 12.8: encode -> caller -> decode con evidencia")
    t_call.add_argument("piece_id", help="ID de la pieza traductora")
    t_call.add_argument("--prompt", default="BAGO smoke test.",
                        help="Prompt del usuario a codificar (default: smoke test)")
    t_call.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    t_audit = translator_sub.add_parser("audit", help="FASE 12.8: historial de evidencia de una pieza")
    t_audit.add_argument("piece_id", help="ID de la pieza traductora")
    t_audit.add_argument("--limit", type=int, default=5, help="Numero de entradas (default 5)")
    t_audit.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
