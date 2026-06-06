#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

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
    print("Uso: bago project <init|status|link> [--root DIR]")
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
    mod = _load_tool_module("spiral_agent", "spiral_agent.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    subcmd = getattr(args, "agent_cmd", None)
    if subcmd == "spawn":
        argv += ["spawn", getattr(args, "agent_id", "")]
        if getattr(args, "phase", None) is not None:
            argv += ["--phase", str(args.phase)]
        if getattr(args, "skills", ""):
            argv += ["--skills", args.skills]
        if getattr(args, "delegates_to", ""):
            argv += ["--delegates-to", args.delegates_to]
    elif subcmd in {"list", "status"}:
        argv += [subcmd]
    elif subcmd in {"run", "kill"}:
        argv += [subcmd, getattr(args, "agent_id", "")]
    elif subcmd in {"allow", "deny", "delegate"}:
        argv += [subcmd, getattr(args, "source_agent", ""), getattr(args, "target_agent", "")]
    elif subcmd == "permissions":
        argv += [subcmd, getattr(args, "agent_id", "")]
    else:
        argv += ["--help"]
    return mod.main(argv)

def cmd_release_job(args: argparse.Namespace) -> int:
    script = BAGO_ROOT / "electron" / "release-job-cli.cjs"
    if not script.exists():
        print(f"No se encontro release-job CLI: {script}", file=sys.stderr)
        return 1
    argv = [str(item) for item in (getattr(args, "release_args", None) or [])]
    completed = subprocess.run(["node", str(script), *argv], cwd=str(BAGO_ROOT))
    return int(completed.returncode)

def cmd_session(args: argparse.Namespace) -> int:
    argv = [str(item) for item in (getattr(args, "session_args", None) or [])]
    if not argv:
        argv = ["--help"]
    completed = subprocess.run(
        [sys.executable, "-m", "bago_core.session_control", "--base-path", str(getattr(args, "base_path", "") or BAGO_ROOT), *argv],
        cwd=str(BAGO_ROOT),
    )
    return int(completed.returncode)

def cmd_autonomous(args: argparse.Namespace) -> int:
    from config_manager import ConfigManager
    from bago_core.commands.cmd_chat import cmd_chat

    cm = ConfigManager(base_path=getattr(args, "base_path", "") or str(BAGO_ROOT))
    subcmd = getattr(args, "autonomous_cmd", None) or "status"
    current = bool(cm.get("features.auto_evolve_on_start", True))
    tools_on = bool(cm.get("features.auto_allow_tools", False))
    total_on = current and tools_on

    if subcmd == "status":
        print("BAGO autonomous")
        print(f"auto_evolve_on_start: {'on' if current else 'off'}")
        print(f"auto_allow_tools: {'on' if tools_on else 'off'}")
        print(f"total_autonomy: {'on' if total_on else 'off'}")
        print("start: activa la autoevolución y abre el REPL")
        print("total: activa autoevolución + auto-aprobación de herramientas")
        return 0

    if subcmd == "on":
        cm.set("features.auto_evolve_on_start", True)
        cm.set("features.auto_allow_tools", False)
        print("auto_evolve_on_start: on")
        print("auto_allow_tools: off")
        return 0

    if subcmd == "off":
        cm.set("features.auto_evolve_on_start", False)
        cm.set("features.auto_allow_tools", False)
        print("auto_evolve_on_start: off")
        print("auto_allow_tools: off")
        return 0

    if subcmd == "start":
        if not current:
            cm.set("features.auto_evolve_on_start", True)
        from bago_core.autonomous_agent import main as agent_main
        goal = getattr(args, "goal", "") or ""
        return agent_main(["--base-path", str(getattr(args, "base_path", "") or BAGO_ROOT), goal] if goal else ["--base-path", str(getattr(args, "base_path", "") or BAGO_ROOT)])

    if subcmd == "total":
        cm.set("features.auto_evolve_on_start", True)
        cm.set("features.auto_allow_tools", True)
        print("auto_evolve_on_start: on")
        print("auto_allow_tools: on")
        print("total_autonomy: on")
        from bago_core.autonomous_agent import main as agent_main
        goal = getattr(args, "goal", "") or ""
        return agent_main(["--base-path", str(getattr(args, "base_path", "") or BAGO_ROOT), goal] if goal else ["--base-path", str(getattr(args, "base_path", "") or BAGO_ROOT)])

    if subcmd == "agent":
        from bago_core.autonomous_agent import main as agent_main
        goal = getattr(args, "goal", "") or ""
        return agent_main(["--base-path", str(getattr(args, "base_path", "") or BAGO_ROOT), goal] if goal else ["--base-path", str(getattr(args, "base_path", "") or BAGO_ROOT)])

    if subcmd == "tui":
        from bago_core.tui_dashboard import main as tui_main
        return tui_main(["--base-path", str(getattr(args, "base_path", "") or BAGO_ROOT)])

    print("Uso: bago autonomous <status|on|off|start|total|agent|tui>")
    return 1

def _chain_registry_path() -> Path:
    return Path.home() / ".bago" / "manager" / "chains.json"

def _chain_empty_registry() -> dict:
    return {"version": 1, "updated_at": "", "chains": []}

def _chain_read() -> dict:
    path = _chain_registry_path()
    if not path.exists():
        payload = _chain_empty_registry()
        payload["registry_file"] = str(path)
        return payload
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = _chain_empty_registry()
    if not isinstance(payload.get("chains"), list):
        payload["chains"] = []
    payload["version"] = 1
    payload["registry_file"] = str(path)
    return payload

def _chain_write(payload: dict) -> dict:
    path = _chain_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "chains": payload.get("chains", []) if isinstance(payload.get("chains"), list) else [],
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    out["registry_file"] = str(path)
    return out

def _chain_find(payload: dict, chain_id: str) -> tuple[int, dict | None]:
    for index, chain in enumerate(payload.get("chains", [])):
        if isinstance(chain, dict) and chain.get("id") == chain_id:
            return index, chain
    return -1, None

def _chain_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

def _chain_validate_payload(payload: dict) -> list[str]:
    errors: list[str] = []
    chains = payload.get("chains", [])
    if not isinstance(chains, list):
        return ["chains must be a list"]
    seen: set[str] = set()
    for chain in chains:
        if not isinstance(chain, dict):
            errors.append("chain entry must be an object")
            continue
        chain_id = str(chain.get("id", ""))
        if not chain_id:
            errors.append("chain without id")
        if chain_id in seen:
            errors.append(f"duplicate chain id: {chain_id}")
        seen.add(chain_id)
        if chain.get("mode", "serial") not in {"serial", "parallel", "mixed", "atomic"}:
            errors.append(f"{chain_id}: invalid mode")
        stages = chain.get("stages", [])
        if not isinstance(stages, list):
            errors.append(f"{chain_id}: stages must be a list")
            continue
        for stage in stages:
            if not isinstance(stage, dict):
                errors.append(f"{chain_id}: stage must be an object")
                continue
            if stage.get("mode", "serial") not in {"serial", "parallel"}:
                errors.append(f"{chain_id}: invalid stage mode")
            if not isinstance(stage.get("steps", []), list):
                errors.append(f"{chain_id}: stage steps must be a list")
    return errors

def _print_chain(value: object, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    elif isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))

def cmd_chain(args: argparse.Namespace) -> int:
    subcmd = getattr(args, "chain_cmd", None) or "list"
    as_json = bool(getattr(args, "json", False))
    registry = _chain_read()

    if subcmd == "list":
        rows = [
            {
                "id": chain.get("id", ""),
                "name": chain.get("name", ""),
                "mode": chain.get("mode", "serial"),
                "stages": len(chain.get("stages", []) or []),
            }
            for chain in registry.get("chains", [])
            if isinstance(chain, dict)
        ]
        if as_json:
            _print_chain({"registry_file": registry.get("registry_file"), "chains": rows}, True)
        else:
            _print_chain("\n".join(f"{row['id']} {row['mode']} stages={row['stages']} name={row['name']}" for row in rows) or "no chains")
        return 0

    if subcmd == "show":
        _, chain = _chain_find(registry, getattr(args, "chain_id", ""))
        if chain is None:
            print(f"chain not found: {getattr(args, 'chain_id', '')}", file=sys.stderr)
            return 1
        _print_chain(chain, True)
        return 0

    if subcmd == "new":
        chain_id = getattr(args, "chain_id", "")
        index, _existing = _chain_find(registry, chain_id)
        if index >= 0:
            print(f"chain already exists: {chain_id}", file=sys.stderr)
            return 1
        registry.setdefault("chains", []).append({
            "id": chain_id,
            "name": getattr(args, "name", "") or chain_id,
            "mode": getattr(args, "mode", "serial"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": "",
            "stages": [],
        })
        _print_chain(_chain_write(registry), as_json)
        return 0

    if subcmd == "delete":
        chain_id = getattr(args, "chain_id", "")
        before = len(registry.get("chains", []))
        registry["chains"] = [chain for chain in registry.get("chains", []) if not (isinstance(chain, dict) and chain.get("id") == chain_id)]
        if len(registry["chains"]) == before:
            print(f"chain not found: {chain_id}", file=sys.stderr)
            return 1
        _print_chain(_chain_write(registry), as_json)
        return 0

    if subcmd == "export":
        output = getattr(args, "output", "")
        if output:
            Path(output).write_text(json.dumps(registry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            _print_chain(f"exported {output}")
        else:
            _print_chain(registry, True)
        return 0

    if subcmd == "import":
        source = Path(getattr(args, "file", ""))
        payload = json.loads(source.read_text(encoding="utf-8"))
        errors = _chain_validate_payload(payload)
        if errors:
            _print_chain({"ok": False, "errors": errors}, True)
            return 1
        _print_chain(_chain_write(payload), as_json)
        return 0

    if subcmd == "validate":
        errors = _chain_validate_payload(registry)
        result = {"ok": not errors, "errors": errors, "registry_file": registry.get("registry_file")}
        _print_chain(result if as_json else ("ok" if not errors else "\n".join(errors)), as_json)
        return 0 if not errors else 1

    if subcmd == "add-stage":
        _, chain = _chain_find(registry, getattr(args, "chain_id", ""))
        if chain is None:
            print(f"chain not found: {getattr(args, 'chain_id', '')}", file=sys.stderr)
            return 1
        chain.setdefault("stages", []).append({"id": _chain_id("stage"), "mode": getattr(args, "mode", "serial"), "steps": []})
        chain["updated_at"] = datetime.now(timezone.utc).isoformat()
        _print_chain(_chain_write(registry), as_json)
        return 0

    if subcmd == "add-step":
        _, chain = _chain_find(registry, getattr(args, "chain_id", ""))
        if chain is None:
            print(f"chain not found: {getattr(args, 'chain_id', '')}", file=sys.stderr)
            return 1
        stages = chain.setdefault("stages", [])
        stage_index = int(getattr(args, "stage", 0))
        while len(stages) <= stage_index:
            stages.append({"id": _chain_id("stage"), "mode": "serial", "steps": []})
        stages[stage_index].setdefault("steps", []).append({
            "id": _chain_id("step"),
            "type": getattr(args, "type", "tool"),
            "label": getattr(args, "label", "Nuevo nodo"),
            "value": getattr(args, "value", ""),
            "ref": getattr(args, "ref", ""),
            "enabled": not bool(getattr(args, "disabled", False)),
        })
        chain["updated_at"] = datetime.now(timezone.utc).isoformat()
        _print_chain(_chain_write(registry), as_json)
        return 0

    print("Uso: bago chain <list|show|new|delete|export|import|validate|add-stage|add-step>")
    return 1

def _manager_check_tool(name: str, command: str, tool_args: list[str]) -> dict:
    try:
        completed = subprocess.run(
            [command, *tool_args],
            cwd=str(BAGO_ROOT),
            capture_output=True,
            text=True,
            timeout=6,
            encoding="utf-8",
            errors="replace",
        )
        text = (completed.stdout or completed.stderr or "").strip().splitlines()
        return {"name": name, "ok": completed.returncode == 0, "detail": text[0] if text else ""}
    except Exception as exc:
        return {"name": name, "ok": False, "detail": str(exc)}

def _manager_probe_web_chat(port: int) -> dict:
    url = f"http://127.0.0.1:{port}/session"
    try:
        with urlopen(url, timeout=0.35) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return {"port": port, "ok": bool(payload.get("session_id")), "url": f"http://127.0.0.1:{port}/", "session": payload}
    except Exception as exc:
        return {"port": port, "ok": False, "url": f"http://127.0.0.1:{port}/", "error": str(exc)}

def cmd_manager(args: argparse.Namespace) -> int:
    subcmd = getattr(args, "manager_cmd", None) or "health"
    as_json = bool(getattr(args, "json", False))
    if subcmd == "web-chat-status":
        start = int(getattr(args, "port", 8080))
        ports = range(start, start + 12) if getattr(args, "scan", False) else [start]
        results = [_manager_probe_web_chat(port) for port in ports]
        payload = {"ok": any(item["ok"] for item in results), "results": results}
        if as_json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print("\n".join(f"{item['port']} {'ok' if item['ok'] else 'closed'} {item['url']}" for item in results))
        return 0 if payload["ok"] else 1

    release_jobs_dir = Path.home() / ".bago" / "manager" / "release-jobs" / "jobs"
    checks = [
        {
            "name": "BAGO runtime",
            "ok": (BAGO_ROOT / "bago_core" / "launcher.py").exists() and (BAGO_ROOT / ".bago" / "chat" / "repl.py").exists(),
            "detail": str(BAGO_ROOT),
        },
        _manager_check_tool("Python", sys.executable, ["--version"]),
        _manager_check_tool("PowerShell", "powershell.exe", ["-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"]),
        _manager_check_tool("Git", "git", ["--version"]),
        _manager_check_tool("Node", "node", ["--version"]),
        _manager_check_tool("Ollama", "ollama", ["--version"]),
    ]
    payload = {
        "ok": all(item["ok"] for item in checks[:5]),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "runtime_root": str(BAGO_ROOT),
        "release_jobs": len(list(release_jobs_dir.glob("*.json"))) if release_jobs_dir.exists() else 0,
        "checks": checks,
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for check in checks:
            print(f"{'ok' if check['ok'] else 'fail'} {check['name']}: {check['detail']}")
        print(f"release_jobs: {payload['release_jobs']}")
    return 0 if payload["ok"] else 1

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


def cmd_workspace(args: argparse.Namespace) -> int:
    mod = _load_tool_module("workspace_registry", "workspace_registry.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    subcmd = getattr(args, "workspace_cmd", None)
    if subcmd == "add":
        argv += ["add", "--name", getattr(args, "name", ""), "--path", getattr(args, "path", "")]
    elif subcmd == "remove":
        argv += ["remove", "--name", getattr(args, "name", "")]
    elif subcmd == "select":
        argv += ["select", "--name", getattr(args, "name", "")]
    elif subcmd == "status":
        argv.append("status")
    else:
        argv.append("list")
    return mod.main(argv)


def cmd_knowledge(args: argparse.Namespace) -> int:
    mod = _load_tool_module("knowledge_federation", "knowledge_federation.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    subcmd = getattr(args, "knowledge_cmd", None)
    if subcmd == "source-add":
        argv += [
            "source-add",
            "--name", getattr(args, "name", ""),
            "--url", getattr(args, "url", ""),
            "--format", getattr(args, "format", "auto"),
        ]
    elif subcmd == "source-remove":
        argv += ["source-remove", "--name", getattr(args, "name", "")]
    elif subcmd == "pull":
        argv += ["pull", "--name", getattr(args, "name", ""), "--limit", str(getattr(args, "limit", 100))]
    elif subcmd == "pull-all":
        argv += ["pull-all", "--limit", str(getattr(args, "limit", 100))]
    else:
        argv.append("source-list")
    return mod.main(argv)
