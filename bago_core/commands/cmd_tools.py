#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BAGO_ROOT = Path(__file__).resolve().parents[2]

for _path in (
    BAGO_ROOT / "bago_core",
    BAGO_ROOT / ".bago" / "core",
    BAGO_ROOT / ".bago" / "chat",
    BAGO_ROOT / ".bago" / "providers",
    BAGO_ROOT / ".bago" / "api",
    BAGO_ROOT / ".bago" / "tools",
):
    _path_s = str(_path)
    if _path_s not in sys.path:
        sys.path.insert(0, _path_s)

def _load_tool_module(module_name: str, file_name: str):
    import importlib.util

    tool_path = BAGO_ROOT / ".bago" / "tools" / file_name
    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar la herramienta: {tool_path}")
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec so dataclasses can resolve __module__
    sys.modules[module_name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return mod

def cmd_project(args: argparse.Namespace) -> int:
    mod = _load_tool_module("project_memory", "project_memory.py")
    action = getattr(args, "project_cmd", None) or "status"
    root = getattr(args, "root", "") or None
    if action == "init":
        return mod.cmd_init(root)
    if action == "status":
        return mod.cmd_status(root)
    if action == "link":
        return mod.cmd_link(root)
    if action == "analyze":
        return mod.cmd_analyze(root)
    print("Uso: bago project <init|status|link|analyze> [--root DIR]")
    return 1

def cmd_preflight(args: argparse.Namespace) -> int:
    mod = _load_tool_module("preflight_engine", "preflight_engine.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    cmd = getattr(args, "cmd", "") or ""
    if root:
        argv += ["--root", root]
    if cmd:
        argv += ["--cmd", cmd]
    return mod.main(argv)

def cmd_toolsmith(args: argparse.Namespace) -> int:
    mod = _load_tool_module("toolsmith", "toolsmith.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    if getattr(args, "toolsmith_json", False):
        argv.append("--json")
    subcmd = getattr(args, "toolsmith_cmd", None)
    if subcmd == "catalog":
        argv.append("catalog")
    elif subcmd == "assign":
        argv += ["assign", "--task", getattr(args, "task", "")]
        if getattr(args, "agent_name", ""):
            argv += ["--agent", args.agent_name]
        if getattr(args, "sprint", ""):
            argv += ["--sprint", args.sprint]
    elif subcmd == "sprint":
        argv += ["sprint", getattr(args, "sprint_id", "")]
        if getattr(args, "tasks", ""):
            argv += ["--tasks", args.tasks]
    elif subcmd == "missing":
        argv.append("missing")
    elif subcmd == "create":
        argv += ["create", getattr(args, "tool_name", "")]
        if getattr(args, "desc", ""):
            argv += ["--desc", args.desc]
        if getattr(args, "category", ""):
            argv += ["--category", args.category]
    elif subcmd == "listen":
        argv += ["listen"]
        if getattr(args, "limit", 1) != 1:
            argv += ["--limit", str(args.limit)]
    else:
        argv += ["--help"]
    return mod.main(argv)

def cmd_issues(args: argparse.Namespace) -> int:
    mod = _load_tool_module("issues_take", "issues_take.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    if getattr(args, "dry_run", False):
        argv.append("--dry-run")
    subcmd = getattr(args, "issues_cmd", None)
    if subcmd == "take":
        argv.append("take")
        agent = getattr(args, "agent", "") or ""
        if agent:
            argv += ["--agent", agent]
        repo = getattr(args, "repo", "") or ""
        if repo:
            argv.append(repo)
    else:
        argv += ["--help"]
    return mod.main(argv)

def cmd_agent(args: argparse.Namespace) -> int:
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    subcmd = getattr(args, "agent_cmd", None)
    if subcmd == "route":
        mod = _load_tool_module("agent_router", "agent_router.py")
        task = getattr(args, "task", "") or ""
        if task:
            argv += ["--task", task]
        if getattr(args, "history", False):
            argv.append("--history")
        if getattr(args, "limit", 10) != 10:
            argv += ["--limit", str(args.limit)]
        if getattr(args, "json", False):
            argv.append("--json")
        if getattr(args, "no_classifier", False):
            argv.append("--no-classifier")
        for word in getattr(args, "task_words", []) or []:
            argv.append(word)
        if not task and not getattr(args, "task_words", []):
            argv += ["--help"]
        return mod.main(argv)

    mod = _load_tool_module("spiral_agent", "spiral_agent.py")
    if subcmd == "spawn":
        argv += ["spawn", getattr(args, "agent_id", "")]
        if getattr(args, "phase", None) is not None:
            argv += ["--phase", str(args.phase)]
        if getattr(args, "skills", ""):
            argv += ["--skills", args.skills]
    elif subcmd in {"list", "status"}:
        argv += [subcmd]
    elif subcmd in {"run", "kill"}:
        argv += [subcmd, getattr(args, "agent_id", "")]
    else:
        argv += ["--help"]
    return mod.main(argv)

def cmd_route(args: argparse.Namespace) -> int:
    """Routing presets: status/validate/activate (sub-modulo cmd_route_v2)."""
    import importlib.util
    from pathlib import Path
    _here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("bago_route_v2", _here / "cmd_route_v2.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("no se pudo cargar cmd_route_v2")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sub = getattr(args, "route_cmd", None) or "status"
    if sub == "status":
        return mod.cmd_route_status(args)
    if sub == "validate":
        return mod.cmd_route_validate(args)
    if sub == "activate":
        return mod.cmd_route_activate(args)
    print(f"unknown subcommand: {sub}")
    return 1

def cmd_scan(args: argparse.Namespace) -> int:
    """Herramientas de analisis portables. Funcionan en cualquier proyecto."""
    tools_dir = BAGO_ROOT / ".bago" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    subcmd = getattr(args, "scan_cmd", None)
    root   = getattr(args, "root", "") or ""

    def _base_argv() -> list[str]:
        return ["--root", root] if root else []

    if subcmd == "secrets":
        import secret_scan
        argv = _base_argv()
        sev = getattr(args, "severity", "warning")
        if sev != "warning":
            argv += ["--severity", sev]
        if getattr(args, "as_json", False):
            argv.append("--json")
        return secret_scan.main(argv)

    elif subcmd == "deps":
        import dep_audit
        argv = _base_argv()
        fmt = getattr(args, "format", "text")
        if fmt != "text":
            argv += ["--format", fmt]
        if getattr(args, "pip_audit", False):
            argv.append("--pip-audit")
        return dep_audit.main(argv)

    elif subcmd == "forced":
        import forced_dependency_scan
        argv = _base_argv()
        fmt = getattr(args, "format", "text")
        if fmt != "text":
            argv += ["--format", fmt]
        return forced_dependency_scan.main(argv)

    elif subcmd == "todos":
        import todo_scan
        argv = _base_argv()
        if getattr(args, "fixme_only", False):
            argv.append("--fixme")
        if getattr(args, "count", False):
            argv.append("--count")
        if getattr(args, "as_json", False):
            argv.append("--json")
        return todo_scan.main(argv)

    elif subcmd == "tokens":
        import token_rotation_guard
        argv = _base_argv()
        if getattr(args, "fix", False):
            argv.append("--fix")
        if getattr(args, "as_json", False):
            argv.append("--json")
        return token_rotation_guard.main(argv)

    elif subcmd == "dead":
        import dead_code
        argv = [root or "./"]
        if getattr(args, "as_json", False):
            argv.append("--json")
        return dead_code.main(argv)

    elif subcmd == "names":
        import naming_check
        argv = [root or "./"]
        if getattr(args, "as_json", False):
            argv.append("--json")
        return naming_check.main(argv)

    elif subcmd == "all":
        scanners = [
            ("secrets", "secret_scan",           _base_argv()),
            ("deps",    "dep_audit",             _base_argv()),
            ("forced",  "forced_dependency_scan", _base_argv()),
            ("todos",   "todo_scan",             _base_argv() + ["--count"]),
            ("tokens",  "token_rotation_guard",  _base_argv()),
        ]
        results: dict[str, str] = {}
        has_errors = False
        for name, mod_name, argv in scanners:
            try:
                mod = __import__(mod_name)
                rc = mod.main(argv)
                results[name] = "[OK]" if rc == 0 else "[WARN]"
                if rc != 0:
                    has_errors = True
            except Exception as exc:  # noqa: BLE001
                results[name] = f"[ERROR] {exc}"
                has_errors = True
        print("\n[bago scan all] Resumen:")
        for k, v in results.items():
            print(f"  {k:10} {v}")
        return 1 if has_errors else 0

    elif subcmd == "doctor":
        import doctor
        argv = _base_argv()
        if getattr(args, 'fix', False): argv.append('--fix')
        if getattr(args, 'quiet', False): argv.append('--quiet')
        if getattr(args, 'as_json', False): argv.append('--json')
        return doctor.main(argv)
    elif subcmd == "commit":
        import commit_readiness
        argv = _base_argv()
        if getattr(args, 'all_files', False): argv.append('--all')
        if getattr(args, 'strict', False): argv.append('--strict')
        if getattr(args, 'as_json', False): argv.append('--json')
        return commit_readiness.main(argv)
    elif subcmd == "git":
        import git_context
        argv = _base_argv()
        if getattr(args, 'brief', False): argv.append('--brief')
        if getattr(args, 'as_json', False): argv.append('--json')
        n_log = getattr(args, 'log', 10)
        if n_log != 10: argv += ['--log', str(n_log)]
        return git_context.main(argv)
    elif subcmd == "sincerity":
        import sincerity_detector
        argv = _base_argv()
        if getattr(args, 'strict', False): argv.append('--strict')
        if getattr(args, 'as_json', False): argv.append('--json')
        path_arg = getattr(args, 'path', '')
        if path_arg: argv += ['--path', path_arg]
        return sincerity_detector.main(argv)
    elif subcmd == "net":
        import net_scan
        argv = []
        if getattr(args, 'scan_net', False): argv.append('--scan')
        if getattr(args, 'adapters', False): argv.append('--adapters')
        if getattr(args, 'as_json', False): argv.append('--json')
        return net_scan.main(argv)
    elif subcmd == "metrics":
        import code_metrics
        argv = _base_argv()
        if getattr(args, 'as_json', False): argv.append('--json')
        ext_arg = getattr(args, 'ext', '')
        if ext_arg: argv += ['--ext', ext_arg]
        return code_metrics.main(argv)
    elif subcmd == "infra":
        mod = _load_tool_module("bago_infra_scan", "bago_infra_scan.py")
        argv = _base_argv()
        if getattr(args, 'quick', False):
            argv.append('--quick')
        if getattr(args, 'as_json', False):
            argv.append('--json')
        if getattr(args, 'all_ports', False):
            argv.append('--all')
        return mod.main(argv)
    elif subcmd == "heal":
        import auto_heal
        argv = _base_argv()
        if getattr(args, 'fix', False): argv.append('--fix')
        if getattr(args, 'dry_run', False): argv.append('--dry-run')
        if getattr(args, 'as_json', False): argv.append('--json')
        return auto_heal.main(argv)
    elif subcmd == "security":
        import bago_security_audit
        argv = _base_argv()
        if getattr(args, 'fix', False): argv.append('--fix')
        if getattr(args, 'as_json', False): argv.append('--json')
        return bago_security_audit.main(argv)

    else:
        print("Uso: bago scan <subcomando> [--root DIR] [opciones]")
        print()
        print("  Subcomandos disponibles:")
        print("    secrets   Detecta secretos hardcodeados (API keys, passwords)")
        print("    deps      Audita dependencias Python (CVEs, versiones sin pinear)")
        print("    todos     Lista TODOs, FIXMEs y HACKs en el codigo fuente")
        print("    tokens    Detecta tokens de API expuestos")
        print("    dead      Detecta codigo muerto (imports, funciones no usadas)")
        print("    names     Valida convenciones de nombres (PEP 8)")
        print("    sincerity Detecta marketing vacio en la documentacion")
        print("    net       Escanea adaptadores de red y dispositivos locales")
        print("    metrics   Metricas de codigo: LOC, archivos, tipos")
        print("    infra     Escanea servicios locales LLM (Ollama, LM Studio, APIs)")
        print("    heal      Sistema inmune: detecta y repara inconsistencias")
        print("    security  Auditoria de seguridad: tokens, permisos, configs")
        print("    doctor    Diagnostico de integridad del proyecto")
        print("    commit    Pre-commit check rapido")
        print("    git       Snapshot del contexto git")
        print("    all       Ejecuta todos los scans")
        print()
        print("  Opciones comunes:")
        print("    --root DIR    Directorio a escanear (default: directorio actual)")
        print("    --json        Output estructurado en JSON")
        print()
        print("  Estas herramientas tambien funcionan standalone:")
        print("    python .bago/tools/secret_scan.py --root /mi/proyecto")
        return 0

def cmd_canary(args):
    tools_dir = BAGO_ROOT / ".bago" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import bago_canary
    root = getattr(args, 'root', '') or ''
    subcmd = getattr(args, 'canary_cmd', None)
    argv = ['--root', root] if root else []
    if subcmd == 'deploy':
        argv += ['deploy', '--type', getattr(args, 'type', 'aws_keys')]
    elif subcmd:
        argv.append(subcmd)
    else:
        argv.append('list')
    return bago_canary.main(argv)

def cmd_backup(args):
    tools_dir = BAGO_ROOT / ".bago" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import bago_backup_vault
    root = getattr(args, 'root', '') or ''
    subcmd = getattr(args, 'backup_cmd', None)
    argv = ['--root', root] if root else []
    if subcmd == 'create':
        argv += ['create', '--max', str(getattr(args, 'max', 10))]
    elif subcmd == 'restore':
        argv += ['restore', '--index', str(getattr(args, 'index', 1))]
    elif subcmd:
        argv.append(subcmd)
    else:
        argv.append('list')
    return bago_backup_vault.main(argv)

def cmd_inventory(args):
    tools_dir = BAGO_ROOT / ".bago" / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    import bago_inventory
    root = getattr(args, 'root', '') or ''
    argv = ['--root', root] if root else []
    fmt = getattr(args, 'format', 'text')
    if fmt != 'text':
        argv += ['--format', fmt]
    return bago_inventory.main(argv)
