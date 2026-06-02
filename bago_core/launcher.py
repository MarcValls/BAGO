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
from bago_core.parsers import build_parser  # noqa: E402


def cmd_guard(args: argparse.Namespace) -> int:
    """Guardián de deuda técnica — previene patrones antes de commitear."""
    mod = _load_tool_module("debt_guard", "debt_guard.py")
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    subcmd = getattr(args, "guard_cmd", None) or "check"
    if subcmd == "check":
        argv.append("check")
        if getattr(args, "all_files", False):
            argv.append("--all")
    elif subcmd == "config":
        argv.append("config")
        config_action = getattr(args, "config_action", None)
        if config_action:
            argv.append(config_action)
            rule_code = getattr(args, "rule_code", None)
            if rule_code:
                argv.append(rule_code)
            action_value = getattr(args, "action_value", None)
            if action_value:
                argv.append(action_value)
    else:
        argv.append(subcmd)
    return mod.main(argv)


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


def cmd_issues(args: argparse.Namespace) -> int:
    """Alias operativo para flujo list/take/close sobre orchestrator_v4."""
    mod = _load_tool_module("orchestrator_v4", "orchestrator_v4.py")
    subcmd = getattr(args, "issues_cmd", None)
    argv: list[str] = []
    root = getattr(args, "root", "") or ""
    if root:
        argv += ["--root", root]
    if getattr(args, "as_json", False):
        argv.append("--json")
    if subcmd == "take":
        agent = (getattr(args, "agent", "codex") or "codex").strip()
        if agent.lower() == "codex":
            agent = "auto"
        argv += ["assign", getattr(args, "brief_id", ""), "--agent", agent]
    elif subcmd == "close":
        argv += ["close", getattr(args, "brief_id", "")]
        if getattr(args, "force", False):
            argv.append("--force")
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

    parser = build_parser(_BAGO_VERSION, base, default_provider, default_model)
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
    elif args.command == "guard":
        return cmd_guard(args)
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
    elif args.command == "issues":
        return cmd_issues(args)
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
            assert main(["--base-path", td, "issues", "--root", td, "list"]) == 0
            orc_mod = _load_tool_module("orchestrator_v4", "orchestrator_v4.py")
            orc_mod.configure_paths(str(Path(td)))
            issue_brief = orc_mod.create_brief(task="CLI issues command smoke test")
            assert main(["--base-path", td, "issues", "--root", td, "take", issue_brief.id, "--agent", "codex"]) == 0
            assert main(["--base-path", td, "issues", "--root", td, "close", issue_brief.id, "--force"]) == 0
        print("launcher.py --test: ALL PASS")
        raise SystemExit(0)
    raise SystemExit(main())
