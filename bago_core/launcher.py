#!/usr/bin/env python3
"""
launcher.py — BAGO Launcher

Punto de entrada principal para BAGO CLI.
Encarga:
1. Parsear argumentos
2. Detectar comando (chat, validate, config, help)
3. Delegar al módulo correspondiente
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Insert .bago paths
BAGO_ROOT = Path(__file__).resolve().parents[1]
_repo_root = str(BAGO_ROOT)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "core"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "chat"))
sys.path.insert(0, str(BAGO_ROOT / ".bago" / "providers"))

_CREATED_VERSION = "4.0.0"

# Lee la versión desde el índice central (versions.json)
from version import CURRENT as _BAGO_VERSION  # noqa: E402
from bago_core.commands.cmd_chat import _load_install_config, cmd_chat, cmd_llm  # noqa: E402
from bago_core.commands.cmd_content import cmd_claim, cmd_config, cmd_evidence, cmd_serve  # noqa: E402
from bago_core.commands.cmd_lifecycle import cmd_install, cmd_uninstall  # noqa: E402
from bago_core.commands.cmd_system import (  # noqa: E402
    cmd_appdata,
    cmd_cmd_rl,
    cmd_cpp_runtime,
    cmd_engine,
    cmd_rl,
    cmd_validate,
)
from bago_core.commands.cmd_tools import (  # noqa: E402
    cmd_agent,
    cmd_backup,
    cmd_canary,
    cmd_inventory,
    cmd_preflight,
    cmd_project,
    cmd_route,
    cmd_scan,
    cmd_toolsmith,
)
from bago_core.commands.cmd_tools import _load_tool_module as _load_tool_module  # noqa: F401,E402


def cmd_monitor(args: argparse.Namespace) -> int:
    """Monitor HTML en tiempo real de procesos BAGO internos."""
    mod = _load_tool_module("process_monitor", "process_monitor.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    port = getattr(args, "port", 7890)
    refresh = getattr(args, "refresh", 5)
    subcmd = getattr(args, "monitor_cmd", None) or "serve"
    if root:
        argv += ["--root", root]
    argv += ["--port", str(port), "--refresh", str(refresh)]
    argv.append(subcmd)
    return mod.main(argv)


def cmd_orchestrate(args: argparse.Namespace) -> int:
    """Orchestrator v4 — Flujo Operativo (Regla Fundamental)."""
    mod = _load_tool_module("orchestrator_v4", "orchestrator_v4.py")
    subcmd = getattr(args, "orc_cmd", None)
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    if getattr(args, "as_json", False):
        argv.append("--json")
    if subcmd == "create":
        argv += ["create", "--task", getattr(args, "task", "")]
        domain = getattr(args, "domain", "")
        priority = getattr(args, "priority", "")
        if domain:
            argv += ["--domain", domain]
        if priority:
            argv += ["--priority", priority]
    elif subcmd == "assign":
        argv += ["assign", getattr(args, "brief_id", ""), "--agent", getattr(args, "agent", "")]
    elif subcmd == "handoff":
        argv += ["handoff", getattr(args, "brief_id", ""),
                 "--from", getattr(args, "from_domain", ""),
                 "--to", getattr(args, "to_domain", ""),
                 "--summary", getattr(args, "summary", "")]
    elif subcmd == "review":
        argv += ["review", getattr(args, "brief_id", "")]
        result_arg = getattr(args, "result", "")
        if result_arg:
            argv += ["--result", result_arg]
    elif subcmd == "close":
        argv += ["close", getattr(args, "brief_id", "")]
        if getattr(args, "force", False):
            argv.append("--force")
    elif subcmd == "show":
        argv += ["show", getattr(args, "brief_id", "")]
    elif subcmd == "list" or subcmd is None:
        argv.append("list")
        status_filter = getattr(args, "status", "")
        if status_filter:
            argv += ["--status", status_filter]
    else:
        argv += ["--help"]
    return mod.main(argv)

def _read_release_label(root: Path) -> str:
    for candidate in (root / "release_version.txt", root / ".bago" / "release_version.txt"):
        if candidate.exists():
            try:
                value = candidate.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if value:
                return value
    cfg = _load_install_config(root)
    for key in ("release_version", "version", "tag"):
        value = cfg.get(key)
        if value:
            return str(value)
    return "latest release"

RELEASE_LABEL = _read_release_label(BAGO_ROOT)

def main(argv: list[str] | None = None) -> int:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".bago" / "core"))
    from config_manager import ConfigManager

    install_root = Path(__file__).resolve().parents[1]
    install_config = _load_install_config(install_root)

    # Leer defaults desde config.json si existe
    base = str(install_root) if install_config else os.getcwd()
    try:
        cm_defaults = ConfigManager(base_path=base)
        default_provider = install_config.get("runtime", {}).get("default_provider") or cm_defaults.default_provider
        default_model = install_config.get("runtime", {}).get("default_model") or cm_defaults.default_model
    except Exception:
        default_provider = "ollama-local"
        default_model = "llama3.2:3b"

    parser = argparse.ArgumentParser(prog="bago", description=f"BAGO {_BAGO_VERSION} — Session-First AI Chat")
    parser.add_argument("--provider", default=default_provider, help="Provider por defecto")
    parser.add_argument("--model", default=default_model, help="Modelo por defecto")
    parser.add_argument("--base-path", default=base, help="Directorio base del proyecto")
    sub = parser.add_subparsers(dest="command", help="Comandos disponibles")

    sub.add_parser("chat", help="Inicia el REPL de chat")
    sub.add_parser("launch", help="Alias de chat: inicia BAGO")
    sub.add_parser("start", help="Inicia BAGO y autoevoluciona (alias de chat con auto-aprendizaje al arrancar)")
    sub.add_parser("validate", help="Gate real de validación: security, contratos, culpas, claims, providers")

    install_parser = sub.add_parser("install", help="Instala/repara BAGO desde la copia local, sin descarga")
    install_parser.add_argument("--source-root", default="", help="Raiz local desde la que instalar")
    install_parser.add_argument("--package-zip", default="", help="ZIP local desde el que instalar")
    install_parser.add_argument("--install-dir", default="C:\\Program Files\\BAGO", help="Destino de instalacion")
    install_parser.add_argument("--mode", choices=("Express", "Advanced"), default="", help="Modo de asistente")
    install_parser.add_argument("--repair-only", action="store_true", help="Solo repara registro PATH/comando")
    install_parser.add_argument("--skip-tests", action="store_true", help="Omite tests internos del instalador")
    install_parser.add_argument("--no-path-update", action="store_true", help="No modifica PATH")
    install_parser.add_argument("--dry-run", action="store_true", help="Muestra lo que haria sin ejecutar")

    uninstall_parser = sub.add_parser("uninstall", help="Desinstala BAGO de la ruta indicada")
    uninstall_parser.add_argument("--install-dir", default="C:\\Program Files\\BAGO", help="Destino a desinstalar")
    uninstall_parser.add_argument("--backup-root", default="", help="Carpeta para el ZIP de backup")
    uninstall_parser.add_argument("--user-state-dir", default="", help="Carpeta de estado a preservar o purgar")
    uninstall_parser.add_argument("--purge-state", action="store_true", help="Borra tambien el estado de usuario")
    uninstall_parser.add_argument("--dry-run", action="store_true", help="Muestra lo que haria sin ejecutar")
    uninstall_parser.add_argument("--no-elevate", action="store_true", help=argparse.SUPPRESS)
    uninstall_parser.add_argument("--elevated-child", action="store_true", help=argparse.SUPPRESS)

    claim_parser = sub.add_parser("claim", help="Claim Evidence Ledger — afirmaciones trazables")
    claim_sub = claim_parser.add_subparsers(dest="claim_action")
    claim_add = claim_sub.add_parser("add", help="Añade un claim trazable")
    claim_add.add_argument("--claim",     dest="claim_text", required=True)
    claim_add.add_argument("--basis",     required=True)
    claim_add.add_argument("--command",   default="")
    claim_add.add_argument("--artifacts", default="")
    claim_add.add_argument("--limits",    default="")
    claim_add.add_argument("--status",    dest="status_val", default="open")
    claim_add.add_argument("--stdout",    dest="stdout_val", default="")
    claim_add.add_argument("--notes",     default="")
    claim_list = claim_sub.add_parser("list", help="Lista claims")
    claim_list.add_argument("--status",   dest="filter_status", default="")
    claim_verify = claim_sub.add_parser("verify", help="Verifica artefactos de un claim")
    claim_verify.add_argument("claim_id")
    claim_sub.add_parser("report", help="Resumen del ledger")

    config_parser = sub.add_parser("config", help="Gestiona configuración")
    config_sub = config_parser.add_subparsers(dest="config_cmd", help="Subcomandos de config")
    config_set_parser = config_sub.add_parser("set", help="Establece clave de config")
    config_set_parser.add_argument("key", nargs="?")
    config_set_parser.add_argument("value", nargs=argparse.REMAINDER)
    config_get_parser = config_sub.add_parser("get", help="Obtiene clave de config")
    config_get_parser.add_argument("key", nargs="?")
    config_sub.add_parser("list", help="Lista configuración completa")
    config_sub.add_parser("reset", help="Restaura defaults")

    llm_parser = sub.add_parser("llm", help="Gestiona arranque provider-aware")
    llm_parser.add_argument("--include-experimental", action="store_true", help="Incluye providers experimentales fuera del release principal")
    llm_sub = llm_parser.add_subparsers(dest="llm_action")
    llm_sub.add_parser("list", help="Lista providers instalados/configurados y disponibles")
    llm_start = llm_sub.add_parser("start", help="Inicia BAGO con provider/modelo seleccionado")
    llm_start.add_argument("--provider", dest="llm_provider", default="", help="Provider instalado/configurado")
    llm_start.add_argument("--model", dest="llm_model", default="", help="Modelo para la sesión")
    llm_start.add_argument("--allow-unconfigured", action="store_true", help="Permite arrancar contra provider no configurado")
    llm_start.add_argument("--persist-default", action="store_true", help="Guarda provider/modelo como default")
    llm_start.add_argument("--dry-run", action="store_true", help="Registra selección sin abrir chat")

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
    serve_parser.add_argument("--token", default="", help="Token de autenticación API")
    serve_parser.add_argument("--ui-dist", default="", help="Directorio dist de la UI React (si se omite, intenta ui-react\\dist)")

    evidence_parser = sub.add_parser("evidence", help="Genera bundle de evidencias verificables")
    evidence_parser.add_argument("--mode", choices=("simulated", "real"), default="simulated", help="Modo de evidencia")
    evidence_parser.add_argument("--objective", default="community-knowledge", help="Objetivo demostrable")
    evidence_parser.add_argument("--output", help="Directorio de salida del bundle")
    evidence_parser.add_argument("--overwrite", action="store_true", help="Sobrescribe el directorio de salida")
    evidence_parser.add_argument("--test", action="store_true", help="Ejecuta la prueba interna del generador")

    runtime_parser = sub.add_parser("cpp-runtime", help="Inicia host de referencia para cpp-local")
    runtime_parser.add_argument("--host", default="127.0.0.1", help="Host del runtime")
    runtime_parser.add_argument("--port", type=int, default=8765, help="Puerto del runtime")
    runtime_parser.add_argument("--runtime-model", default="bago-cpp:default", help="Modelo expuesto por el runtime")
    runtime_parser.add_argument("--test", action="store_true", help="Ejecuta la prueba interna del host")

    monitor_parser = sub.add_parser("monitor", help="Monitor HTML en tiempo real de procesos BAGO")
    monitor_parser.add_argument("--root", default="", help="Raíz del proyecto a monitorizar (default: cwd)")
    monitor_parser.add_argument("--port", type=int, default=7890, help="Puerto HTTP del monitor (default: 7890)")
    monitor_parser.add_argument("--refresh", type=int, default=5, help="Segundos entre auto-refresh (default: 5)")
    monitor_sub = monitor_parser.add_subparsers(dest="monitor_cmd")
    monitor_sub.add_parser("serve", help="Sirve el monitor en http://127.0.0.1:PORT/ (default)")
    monitor_sub.add_parser("generate", help="Genera monitor.html estático en .bago/monitor.html")

    orc_parser = sub.add_parser("orchestrate", help="Orchestrator v4 — Flujo Operativo (Regla Fundamental)")
    orc_parser.add_argument("--root", default="", help="Raíz del proyecto (default: cwd)")
    orc_parser.add_argument("--json", dest="as_json", action="store_true", help="Output JSON")
    orc_sub = orc_parser.add_subparsers(dest="orc_cmd")
    orc_list = orc_sub.add_parser("list", help="Lista Task Briefs")
    orc_list.add_argument("--status", default="", help="Filtrar por estado (open/assigned/closed)")
    orc_create = orc_sub.add_parser("create", help="Crea un Task Brief")
    orc_create.add_argument("--task", required=True, help="Descripción de la tarea")
    orc_create.add_argument("--domain", default="", help="Dominio (Backend/Frontend/Producto/Contenido/Deployment)")
    orc_create.add_argument("--priority", default="", help="Prioridad (P0/P1/P2/Post-MVP)")
    orc_assign = orc_sub.add_parser("assign", help="Asigna brief a un especialista")
    orc_assign.add_argument("brief_id", help="ID del brief")
    orc_assign.add_argument("--agent", required=True, help="Agente especialista")
    orc_handoff = orc_sub.add_parser("handoff", help="Genera Handoff formal entre dominios")
    orc_handoff.add_argument("brief_id", help="ID del brief")
    orc_handoff.add_argument("--from", dest="from_domain", required=True, help="Dominio origen")
    orc_handoff.add_argument("--to", dest="to_domain", required=True, help="Dominio destino")
    orc_handoff.add_argument("--summary", default="", help="Resumen del trabajo realizado")
    orc_review = orc_sub.add_parser("review", help="Revisión del Orchestrator (Fase 5)")
    orc_review.add_argument("brief_id", help="ID del brief")
    orc_review.add_argument("--result", default="approved", choices=["approved", "requires_changes", "reencaminar"],
                            help="Resultado de la revisión")
    orc_close = orc_sub.add_parser("close", help="Cierra un Task Brief (Fase 6)")
    orc_close.add_argument("brief_id", help="ID del brief")
    orc_close.add_argument("--force", action="store_true", help="Cierra sin revisión previa")
    orc_show = orc_sub.add_parser("show", help="Muestra detalle de un brief")
    orc_show.add_argument("brief_id", help="ID del brief")

    scan_parser = sub.add_parser("scan", help="Herramientas de analisis portables (secrets, deps, todos, tokens, dead, names, sincerity, net, metrics, infra, heal, security, doctor, commit, git, all)")
    scan_parser.add_argument("--root", default="", help="Directorio raiz a escanear (default: cwd)")
    scan_sub = scan_parser.add_subparsers(dest="scan_cmd")

    scan_secrets = scan_sub.add_parser("secrets", help="Detecta secretos hardcodeados")
    scan_secrets.add_argument("--severity", default="warning", choices=["error", "warning", "info"])
    scan_secrets.add_argument("--json", dest="as_json", action="store_true")

    scan_deps = scan_sub.add_parser("deps", help="Audita dependencias Python")
    scan_deps.add_argument("--format", default="text", choices=["text", "md", "json"])
    scan_deps.add_argument("--pip-audit", dest="pip_audit", action="store_true")

    scan_todos = scan_sub.add_parser("todos", help="Lista TODOs, FIXMEs y HACKs")
    scan_todos.add_argument("--fixme", dest="fixme_only", action="store_true")
    scan_todos.add_argument("--count", action="store_true")
    scan_todos.add_argument("--json", dest="as_json", action="store_true")

    scan_tokens = scan_sub.add_parser("tokens", help="Detecta tokens de API expuestos")
    scan_tokens.add_argument("--fix", action="store_true", help="Instrucciones de rotacion")
    scan_tokens.add_argument("--json", dest="as_json", action="store_true")

    scan_dead = scan_sub.add_parser("dead", help="Detecta codigo muerto (Python)")
    scan_dead.add_argument("--json", dest="as_json", action="store_true")

    scan_names = scan_sub.add_parser("names", help="Valida convenciones de nombres (PEP 8)")
    scan_names.add_argument("--json", dest="as_json", action="store_true")

    scan_sub.add_parser("all", help="Ejecuta todos los scans y muestra resumen")

    scan_sincerity = scan_sub.add_parser("sincerity", help="Detecta marketing vacio en la documentacion")
    scan_sincerity.add_argument("--strict", action="store_true")
    scan_sincerity.add_argument("--path", default="")
    scan_sincerity.add_argument("--json", dest="as_json", action="store_true")

    scan_net = scan_sub.add_parser("net", help="Escanea adaptadores de red y dispositivos locales")
    scan_net.add_argument("--scan", dest="scan_net", action="store_true")
    scan_net.add_argument("--adapters", action="store_true")
    scan_net.add_argument("--json", dest="as_json", action="store_true")

    scan_metrics = scan_sub.add_parser("metrics", help="Metricas de codigo: LOC, archivos, tipos")
    scan_metrics.add_argument("--ext", default="")
    scan_metrics.add_argument("--json", dest="as_json", action="store_true")

    scan_infra = scan_sub.add_parser("infra", help="Escanea servicios locales LLM (Ollama, LM Studio, APIs)")
    scan_infra.add_argument("--quick", action="store_true")
    scan_infra.add_argument("--all", dest="all_ports", action="store_true")
    scan_infra.add_argument("--json", dest="as_json", action="store_true")

    scan_heal = scan_sub.add_parser("heal", help="Sistema inmune: detecta y repara inconsistencias")
    scan_heal.add_argument("--fix", action="store_true")
    scan_heal.add_argument("--dry-run", dest="dry_run", action="store_true")
    scan_heal.add_argument("--json", dest="as_json", action="store_true")

    scan_security = scan_sub.add_parser("security", help="Auditoria de seguridad: tokens, permisos, configs")
    scan_security.add_argument("--fix", action="store_true")
    scan_security.add_argument("--json", dest="as_json", action="store_true")

    scan_doctor = scan_sub.add_parser("doctor", help="Diagnostico de integridad del proyecto")
    scan_doctor.add_argument("--fix", action="store_true")
    scan_doctor.add_argument("--quiet", action="store_true")
    scan_doctor.add_argument("--json", dest="as_json", action="store_true")

    scan_commit = scan_sub.add_parser("commit", help="Pre-commit check rapido")
    scan_commit.add_argument("--all", dest="all_files", action="store_true")
    scan_commit.add_argument("--strict", action="store_true")
    scan_commit.add_argument("--json", dest="as_json", action="store_true")

    scan_git = scan_sub.add_parser("git", help="Snapshot del contexto git")
    scan_git.add_argument("--brief", action="store_true")
    scan_git.add_argument("--log", type=int, default=10)
    scan_git.add_argument("--json", dest="as_json", action="store_true")

    canary_parser = sub.add_parser("canary", help="Honeytokens - trampas de deteccion de intrusos")
    canary_parser.add_argument("--root", default="")
    canary_sub = canary_parser.add_subparsers(dest="canary_cmd")
    canary_deploy = canary_sub.add_parser("deploy")
    canary_deploy.add_argument("--type", default="aws_keys", choices=["aws_keys","openai_api","github_pat","telegram_bot","google_api","all"])
    canary_sub.add_parser("check")
    canary_sub.add_parser("list")
    canary_sub.add_parser("purge")

    backup_parser = sub.add_parser("backup", help="Backups del proyecto con rotacion")
    backup_parser.add_argument("--root", default="")
    backup_sub = backup_parser.add_subparsers(dest="backup_cmd")
    bc = backup_sub.add_parser("create")
    bc.add_argument("--max", type=int, default=10)
    backup_sub.add_parser("list")
    br = backup_sub.add_parser("restore")
    br.add_argument("--index", type=int, default=1)

    project_parser = sub.add_parser("project", help="Gestiona la estructura portable .bago del proyecto")
    project_parser.add_argument("--root", default="")
    project_sub = project_parser.add_subparsers(dest="project_cmd")
    project_sub.add_parser("init", help="Inicializa la estructura .bago")
    project_sub.add_parser("status", help="Muestra el estado actual")
    project_sub.add_parser("link", help="Crea el enlace portable del proyecto")

    preflight_parser = sub.add_parser("preflight", help="Ejecuta checks de preflight portables")
    preflight_parser.add_argument("--root", default="")
    preflight_parser.add_argument("--cmd", default="")

    toolsmith_parser = sub.add_parser("toolsmith", help="Gestiona toolboxes de agentes")
    toolsmith_parser.add_argument("--root", default="")
    toolsmith_parser.add_argument("--json", dest="toolsmith_json", action="store_true")
    toolsmith_sub = toolsmith_parser.add_subparsers(dest="toolsmith_cmd")
    toolsmith_sub.add_parser("catalog", help="Muestra el catalogo")
    toolsmith_assign = toolsmith_sub.add_parser("assign", help="Asigna herramientas a un agente")
    toolsmith_assign.add_argument("--task", required=True)
    toolsmith_assign.add_argument("--agent", dest="agent_name", default="")
    toolsmith_assign.add_argument("--sprint", default="backlog")
    toolsmith_sprint = toolsmith_sub.add_parser("sprint", help="Crea toolboxes para un sprint")
    toolsmith_sprint.add_argument("sprint_id")
    toolsmith_sprint.add_argument("--tasks", default="")
    toolsmith_sub.add_parser("missing", help="Lista herramientas faltantes")
    toolsmith_create = toolsmith_sub.add_parser("create", help="Crea un nuevo tool stub")
    toolsmith_create.add_argument("tool_name")
    toolsmith_create.add_argument("--desc", default="")
    toolsmith_create.add_argument("--category", default="general")
    toolsmith_listen = toolsmith_sub.add_parser("listen", help="Escucha eventos del bus neural")
    toolsmith_listen.add_argument("--limit", type=int, default=1)

    agent_parser = sub.add_parser("agent", help="Gestiona spiral agents")
    agent_parser.add_argument("--root", default="")
    agent_sub = agent_parser.add_subparsers(dest="agent_cmd")
    agent_spawn = agent_sub.add_parser("spawn", help="Crea un agente")
    agent_spawn.add_argument("agent_id")
    agent_spawn.add_argument("--phase", type=int, default=0)
    agent_spawn.add_argument("--skills", default="")
    agent_sub.add_parser("list", help="Lista agentes")
    agent_run = agent_sub.add_parser("run", help="Ejecuta un agente")
    agent_run.add_argument("agent_id")
    agent_kill = agent_sub.add_parser("kill", help="Desactiva un agente")
    agent_kill.add_argument("agent_id")
    agent_sub.add_parser("status", help="Muestra consonancia entre agentes")

    route_parser = sub.add_parser("route", help="Ruta tareas al mejor agente AI")
    route_parser.add_argument("--root", default="")
    route_parser.add_argument("--task", default="")
    route_parser.add_argument("--json", dest="route_json", action="store_true")
    route_parser.add_argument("--history", action="store_true")
    route_parser.add_argument("--limit", type=int, default=10)
    route_parser.add_argument("--no-classifier", action="store_true")

    inv_parser = sub.add_parser("inventory", help="Cataloga capacidades del proyecto")
    inv_parser.add_argument("--root", default="")
    inv_parser.add_argument("--format", default="text", choices=["text","md","json"])

    args = parser.parse_args(argv)

    if args.command in ("chat", "launch", "start") or args.command is None:
        return cmd_chat(args)
    elif args.command == "validate":
        return cmd_validate(args)
    elif args.command == "install":
        return cmd_install(args)
    elif args.command == "uninstall":
        return cmd_uninstall(args)
    elif args.command == "claim":
        return cmd_claim(args)
    elif args.command == "config":
        return cmd_config(args)
    elif args.command == "llm":
        return cmd_llm(args)
    elif args.command == "engine":
        return cmd_engine(args)
    elif args.command == "appdata":
        return cmd_appdata(args)
    elif args.command == "cmd-rl":
        return cmd_cmd_rl(args)
    elif args.command == "rl":
        return cmd_rl(args)
    elif args.command == "serve":
        return cmd_serve(args)
    elif args.command == "evidence":
        return cmd_evidence(args)
    elif args.command == "cpp-runtime":
        return cmd_cpp_runtime(args)
    elif args.command == "scan":
        return cmd_scan(args)
    elif args.command == "canary":
        return cmd_canary(args)
    elif args.command == "backup":
        return cmd_backup(args)
    elif args.command == "project":
        return cmd_project(args)
    elif args.command == "preflight":
        return cmd_preflight(args)
    elif args.command == "toolsmith":
        return cmd_toolsmith(args)
    elif args.command == "agent":
        return cmd_agent(args)
    elif args.command == "route":
        return cmd_route(args)
    elif args.command == "inventory":
        return cmd_inventory(args)
    elif args.command == "monitor":
        return cmd_monitor(args)
    elif args.command == "orchestrate":
        return cmd_orchestrate(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        # Quick smoke test
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cfg = {"runtime": {"default_provider": "codex", "default_model": "gpt-5.4-mini"}}
            (Path(td) / "install_config.json").write_text(json.dumps(cfg), encoding="utf-8")
            assert _load_install_config(Path(td))["runtime"]["default_provider"] == "codex"
            assert main(["--base-path", td, "config", "set", "providers.cpp-local.enabled", "true"]) == 0
            assert main(["--base-path", td, "config", "get", "providers.cpp-local.enabled"]) == 0
            assert main(["--base-path", td, "llm", "list"]) == 0
            assert main(["--base-path", td, "llm", "start", "--provider", "ollama-local", "--model", "llama3.2:3b", "--dry-run"]) == 0
            assert (Path(td) / ".bago" / "state" / "llm_start.json").exists()
            assert main(["--base-path", td, "llm", "start", "--provider", "cpp-local", "--dry-run"]) == 1
            assert main(["--base-path", td, "engine", "status"]) == 0
            assert main(["--base-path", td, "appdata", "status"]) == 0
            assert main(["--base-path", td, "cmd-rl", "status"]) == 0
            assert main(["--base-path", td, "rl", "status"]) == 0
            assert main(["--base-path", td, "rl", "shadow", "off"]) == 0
            assert main(["--base-path", td, "rl", "shadow", "on"]) == 0
            assert main(["--base-path", td, "rl", "train", "bc"]) == 0
            assert main(["--base-path", td, "rl", "eval"]) == 0
            assert main(["--base-path", td, "evidence", "--test"]) == 0
            assert main(["--base-path", td, "install", "--dry-run"]) == 0
            tmp_install = Path(td) / "fake-install"
            tmp_install.mkdir()
            (tmp_install / "keep.txt").write_text("x", encoding="utf-8")
            assert main(["--base-path", td, "uninstall", "--install-dir", str(tmp_install), "--dry-run"]) == 0
        print("launcher.py --test: ALL PASS")
        raise SystemExit(0)
    raise SystemExit(main())
