#!/usr/bin/env python3
"""
launcher.py -- BAGO Launcher

Punto de entrada principal para BAGO CLI.
Encarga:
1. Parsear argumentos
2. Detectar comando (chat, validate, config, help)
3. Delegar al modulo correspondiente
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

# Insert framework paths
BAGO_ROOT = Path(__file__).resolve().parents[1]
_repo_root = str(BAGO_ROOT)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
# Prefer the source-tree version module when running from source; the package
# version module acts as the installed fallback.
from bago_core.resolver import add_piece_paths, resolve_piece_path  # noqa: E402
from bago_core.workspace_paths import workspace_root  # noqa: E402

add_piece_paths("core.package", "chat.package", "providers.package")

_CREATED_VERSION = "4.0.0"

# Lee la version desde el indice central (versions.json)
try:
    from version import CURRENT as _BAGO_VERSION  # noqa: E402
except ModuleNotFoundError:
    from bago_core.version import CURRENT as _BAGO_VERSION  # noqa: E402
from bago_core.commands.cmd_chat import _load_install_config, cmd_chat, cmd_context, cmd_exec, cmd_llm  # noqa: E402
from bago_core.commands.cmd_content import cmd_claim, cmd_config, cmd_evidence, cmd_manager, cmd_serve, cmd_api  # noqa: E402
from bago_core.commands.cmd_lifecycle import cmd_install, cmd_uninstall  # noqa: E402
from bago_core.commands.cmd_system import (  # noqa: E402
    cmd_appdata,
    cmd_cmd_rl,
    cmd_engine,
    cmd_rl,
    cmd_validate,
)
from bago_core.commands.cmd_doctor import cmd_doctor  # noqa: E402
from bago_core.commands.cmd_tools import (  # noqa: E402
    cmd_agent,
    cmd_backup,
    cmd_canary,
    cmd_inventory,
    cmd_issues as cmd_issues_next,
    cmd_preflight,
    cmd_project,
    cmd_route,
    cmd_scan,
    cmd_toolsmith,
)
from bago_core.commands.cmd_tools import _load_tool_module as _load_tool_module  # noqa: F401,E402
from bago_core.parsers import build_parser  # noqa: E402

def cmd_guard(args: argparse.Namespace) -> int:
    """Guardian de deuda tecnica -- previene patrones antes de commitear."""
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
    """Orchestrator v4 -- Flujo Operativo (Regla Fundamental)."""
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
    if getattr(args, "issues_cmd", None) == "take" and not getattr(args, "brief_id", ""):
        return cmd_issues_next(args)

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
def cmd_installs(args: argparse.Namespace) -> int:
    """Escanea el sistema e imprime JSON con todas las instalaciones BAGO.

    Disenado para la landing page (https://bago-...vercel.app): el usuario
    corre `bago list-installs` y pega el resultado en la web. Cero telemetria,
    cero red. El JSON contiene paths absolutos, versiones, presencia de
    supervisor/probe, y liveness del pid del supervisor.
    """
    from bago_core.cli_installs import main as _inst_main
    argv: list[str] = []
    if getattr(args, "plain", False):
        argv.append("--plain")
    if getattr(args, "active_only", False):
        argv.append("--active-only")
    return _inst_main(argv)

def cmd_install_role(args: argparse.Namespace) -> int:
    """Gestiona que copia BAGO se usa como active/dev/launch/escritor/ilustrador."""
    from bago_core.install_roles import main as _roles_main
    argv: list[str] = []
    subcmd = getattr(args, "install_role_cmd", None) or "show"
    argv.append(subcmd)
    if subcmd == "set":
        argv += ["--role", getattr(args, "role", ""), "--path", getattr(args, "path", "")]
        if getattr(args, "no_strict", False):
            argv.append("--no-strict")
    elif subcmd == "clear":
        role = getattr(args, "role", "") or ""
        if role:
            argv += ["--role", role]
    if getattr(args, "json", False):
        argv.append("--json")
    return _roles_main(argv)


def cmd_profiles(args: argparse.Namespace) -> int:
    """Muestra el mapa estable de active/des/ign y el flujo recomendado."""
    dev_root = workspace_root() / "dev"
    launch_root = workspace_root() / "launch"
    stable_root = _profile_root("stable")
    print("BAGO profiles")
    print("----------------------------------------")
    print(f"stable : {stable_root}")
    print(f"des    : {dev_root}")
    print(f"ign    : {launch_root}")
    print("")
    print("Flujo:")
    print("  bago install --profile des")
    print("  bago install --profile ign")
    print("  bago install --profile stable")
    print("  bago promote --from des --to ign")
    print("  bago promote --from ign --to stable")
    return 0

def cmd_node(args: argparse.Namespace) -> int:
    """Passthrough al CLI de node_control (registry, policy, evidence, modos).

    Importa dinamicamente bago_core.node_control y delega. Acepta --json
    antes o despues del subcomando. Misma superficie que `python -m bago_core.node_control`.
    """
    from bago_core import node_control as _nc
    argv: list[str] = []
    if getattr(args, "json", False):
        argv.append("--json")
    base = getattr(args, "base_path", None)
    if base:
        argv += ["--base-path", str(base)]
    sub = getattr(args, "node_cmd", None)
    if sub:
        argv.append(sub)
    # Translator is special: it has a sub-subcommand (list/show/validate/map),
    # so --json must come AFTER that sub-subcommand to be parsed correctly.
    if sub == "translator":
        sub_sub = getattr(args, "translator_command", None)
        if sub_sub:
            argv.append(sub_sub)
        # Pass through positional piece_id (if any) and --json
        piece_id = getattr(args, "piece_id", None)
        if piece_id:
            argv.append(piece_id)
        if getattr(args, "json", False):
            argv.append("--json")
        return _nc.main(argv)
    option_map = (
        ("type", "--type"),
        ("scope", "--scope"),
        ("installation", "--installation"),
        ("piece", "--piece"),
        ("mode", "--mode"),
        ("output", "--output"),
        ("limit", "--limit"),
    )
    for attr, flag in option_map:
        value = getattr(args, attr, None)
        if value not in (None, ""):
            argv.extend([flag, str(value)])
    # Other node_control subcommands accept --json after themselves.
    sub_with_json = {
        "status", "validate", "pieces", "connectors", "matrix",
        "evidence", "preview", "connect", "disconnect", "set-mode",
    }
    if sub in sub_with_json and getattr(args, "json", False):
        argv.append("--json")
    return _nc.main(argv)

def _read_release_label(root: Path) -> str:
    for candidate in (root / "release_version.txt", root / ".gabo" / "release_version.txt"):
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
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in {"des", "ign"}:
        profile = argv[0]
        profile_root = workspace_root() / ("dev" if profile == "des" else "launch")
        cli_path = profile_root / "bago_core" / "cli.py"
        runner = cli_path if cli_path.exists() else profile_root / "bago_core" / "launcher.py"
        if not runner.exists():
            print(f"[ERROR] Perfil '{profile}' no disponible en {profile_root}")
            return 1
        import subprocess
        completed = subprocess.run([sys.executable, str(runner), *argv[1:]], cwd=str(profile_root))
        return completed.returncode

    add_piece_paths("core.package")
    from config_manager import ConfigManager

    install_root = Path(__file__).resolve().parents[1]
    install_config = _load_install_config(install_root)

    # El base-path operativo es el directorio actual del usuario.
    # El install_config solo aporta defaults de provider/modelo.
    base = os.getcwd()
    try:
        cm_defaults = ConfigManager(base_path=base)
        default_provider = install_config.get("runtime", {}).get("default_provider") or cm_defaults.default_provider
        default_model = install_config.get("runtime", {}).get("default_model") or cm_defaults.default_model
    except Exception:
        default_provider = "ollama-local"
        default_model = "llama3.2:3b"

    parser = build_parser(_BAGO_VERSION, base, default_provider, default_model)
    args = parser.parse_args(argv)
    return _dispatch(args, parser)


# -- FASE 6.2 facade dispatcher -------------------------------------------------
# launcher.py is a *thin facade* (R0-R10). The dispatch table below is the only
# piece of routing logic allowed at this layer. It maps:
#     args.command    -> command implementation in bago_core.commands.cmd_*
# Keeping the table explicit (no `elif ladder`) makes it trivial to:
#   * audit (one screenful)
#   * test (covered by tests/test_launcher_dispatch.py)
#   * refactor (move a command -> update one line)
_DISPATCH_TABLE: dict[str, str] = {
    "chat":        "cmd_chat",
    "launch":      "cmd_chat",
    "start":       "cmd_chat",
    "context":     "cmd_context",
    "exec":        "cmd_exec",
    "validate":    "cmd_validate",
    "install":     "cmd_install",
    "uninstall":   "cmd_uninstall",
    "profiles":    "cmd_profiles",
    "claim":       "cmd_claim",
    "config":      "cmd_config",
    "llm":         "cmd_llm",
    "engine":      "cmd_engine",
    "appdata":     "cmd_appdata",
    "cmd-rl":      "cmd_cmd_rl",
    "rl":          "cmd_rl",
    "manager":     "cmd_manager",
    "serve":       "cmd_serve",
    "api":         "cmd_api",
    "evidence":    "cmd_evidence",
    "scan":        "cmd_scan",
    "guard":       "cmd_guard",
    "canary":      "cmd_canary",
    "backup":      "cmd_backup",
    "project":     "cmd_project",
    "preflight":   "cmd_preflight",
    "toolsmith":   "cmd_toolsmith",
    "issues":      "cmd_issues",
    "agent":       "cmd_agent",
    "route":       "cmd_route",
    "inventory":   "cmd_inventory",
    "monitor":     "cmd_monitor",
    "orchestrate": "cmd_orchestrate",
    "list-installs": "cmd_installs",
    "install-role": "cmd_install_role",
    "node":        "cmd_node",
    "doctor":      "cmd_doctor",
}


def _dispatch(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    """Route a parsed Namespace to the matching cmd_* implementation.

    `None` (no command) is treated as `chat` for backwards compatibility
    with the legacy `bago` (no args) entrypoint. Unknown commands print help.
    """
    cmd = args.command or "chat"
    impl_name = _DISPATCH_TABLE.get(cmd)
    if impl_name is None:
        parser.print_help()
        return 0
    # local lookup keeps the table readable while avoiding a per-call dict
    impl = globals().get(impl_name)
    if impl is None:
        parser.print_help()
        return 0
    return impl(args)

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        # Quick smoke test
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td) / "state"
            os.environ["BAGO_STATE_ROOT"] = str(state_root)
            cfg = {"runtime": {"default_provider": "codex", "default_model": "gpt-5.4-mini"}}
            (Path(td) / "install_config.json").write_text(json.dumps(cfg), encoding="utf-8")
            assert _load_install_config(Path(td))["runtime"]["default_provider"] == "codex"
            assert main(["--base-path", td, "llm", "list"]) == 0
            assert main(["--base-path", td, "llm", "start", "--provider", "ollama-local", "--model", "llama3.2:3b", "--dry-run"]) == 0
            assert (state_root / "llm_start.json").exists()
            assert main(["--base-path", td, "context", "inspect"]) == 0
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
            os.environ.pop("BAGO_STATE_ROOT", None)
        print("launcher.py --test: ALL PASS")
        raise SystemExit(0)
    raise SystemExit(main())
