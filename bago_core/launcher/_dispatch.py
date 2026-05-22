from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from bago_core.launcher._paths import (
    BAGO_ROOT, BAGO_CORE_DIR, TOOLS, CORE,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, default_user_home,
)
from bago_core.launcher._config import (
    load_bp, load_dispatcher, load_context, load_registry_mod,
    build_commands, build_deprecated_map, get_module_for_cmd,
    COMMANDS, DEPRECATED_MAP,
)


def _dispatch(cmd: str, rest: list, preflight_only: bool = False, skip_preflight: bool = False) -> None:
    """Dispatch a registered command with preflight + session logging + exit propagation."""
    # 0. Deprecation hint (non-blocking)
    if cmd in _DEPRECATED_MAP:
        see = _DEPRECATED_MAP[cmd]
        hint = f"  ⚠️  '{cmd}' está deprecated → usa: {see}"
        print(f"\033[33m{hint}\033[0m" if _USE_COLOR else hint)
        sys.stdout.flush()

    # 0b. Experimental perimeter warning (non-blocking, suppressible with BAGO_LABS=1)
    if os.environ.get("BAGO_LABS", "0") != "1":
        reg = _load_registry_mod()
        if reg:
            entry = getattr(reg, "REGISTRY", {}).get(cmd)
            stability = getattr(entry, "stability", "core") if entry else "core"
            if stability == "experimental":
                warn = (
                    f"  ⚗️  [experimental] 'bago {cmd}' no forma parte del contrato estable.\n"
                    f"      Puede cambiar o desaparecer sin aviso. "
                    f"Suprime este aviso con BAGO_LABS=1."
                )
                print(f"\033[33m{warn}\033[0m" if _USE_COLOR else warn)
                sys.stdout.flush()

    # 1. Preflight (fail-closed via preflight_engine for core commands)
    _run_preflight(cmd, skip=skip_preflight)
    if preflight_only:
        print(f"  ✅ Preflight OK para '{cmd}'")
        return

    # 1b. Risk model: dangerous commands require --yes or --unsafe
    # Exception: --self-test flag invokes the module's _self_test() directly,
    # bypassing the dangerous guard (read-only capability check, no state mutation).
    if "--self-test" in rest:
        _run_self_test(cmd, rest)
        return
    _check_risk(cmd, rest)

    # 2. Start session log + telemetry
    session = _start_session(cmd, rest)
    _tel = _load_telemetry()

    # 2b. Dispatcher: resolve agent + inject BAGO_AGENT into subprocess env (opt-in)
    _dispatch_ctx   = None
    _dispatch_disp  = None
    _dispatch_entry = None
    dispatch_env: dict = {}
    if _DISPATCH_ENABLED:
        reg = _load_registry_mod()
        if reg and hasattr(reg, "REGISTRY"):
            _dispatch_entry = reg.REGISTRY.get(cmd)
        _dispatch_ctx  = _load_context()
        _dispatch_disp = _load_dispatcher()
        if _dispatch_disp and _dispatch_entry is not None and _dispatch_ctx is not None:
            try:
                dispatch_env = _dispatch_disp.prepare_dispatch(
                    _dispatch_ctx, cmd, _dispatch_entry
                )
            except Exception:
                dispatch_env = {}

    # 3. Execute
    _user_cwd = os.getcwd()
    run_env = {**os.environ, "BAGO_USER_CWD": _user_cwd, **dispatch_env}
    _t0 = time.monotonic()
    _load_bp().dispatch_header(cmd)
    try:
        result = subprocess.run(
            COMMANDS[cmd] + rest,
            cwd=str(BAGO_ROOT.parent),
            env=run_env,
        )
    except KeyboardInterrupt:
        import sys as _sys
        print("\n\033[2m⚡ Interrumpido.\033[0m", file=_sys.stderr)
        _sys.exit(130)
    _duration = time.monotonic() - _t0

    # 3b. Dispatcher: finalize (emit dispatch:after event, flush)
    if _DISPATCH_ENABLED and _dispatch_disp and _dispatch_entry is not None and _dispatch_ctx is not None:
        _agent_name = getattr(_dispatch_entry, "agent", "") or "ORGANIZADOR"
        try:
            _dispatch_disp.finalize_dispatch(_dispatch_ctx, cmd, _agent_name, result.returncode)
        except Exception:
            pass

    # 4. Log result (session logger + telemetry)
    if _tel:
        _tel.track_command(cmd, args=rest, duration_s=_duration, exit_code=result.returncode)
    if session:
        if result.returncode == 0:
            session.success()
        else:
            session.failure(exit_code=result.returncode)

    # 5. Propagate exit code (was previously swallowed)
    if result.returncode != 0:
        sys.exit(result.returncode)


def _cmd_session_last(args: list) -> None:
    """Show last N sessions via session_logger.py."""
    sl_path = TOOLS / "session_logger.py"
    if not sl_path.exists():
        print("  session_logger.py no encontrado en", TOOLS)
        return
    n = int(args[0]) if args and args[0].isdigit() else 5
    subprocess.run([sys.executable, str(sl_path), "--last", str(n)],
                   cwd=str(BAGO_ROOT.parent))


def _cmd_session_history() -> None:
    """Show session history via session_logger.py."""
    sl_path = TOOLS / "session_logger.py"
    if not sl_path.exists():
        print("  session_logger.py no encontrado en", TOOLS)
        return
    subprocess.run([sys.executable, str(sl_path), "--history"],
                   cwd=str(BAGO_ROOT.parent))


def _cmd_telemetry(args: list) -> None:
    """Show local telemetry (App Insights equivalent, no cloud)."""
    if "--web" in args:
        web_path = TOOLS / "bago_telemetry_web.py"
        if not web_path.exists():
            print("  bago_telemetry_web.py no encontrado en", TOOLS)
            return
        web_extra: list[str] = []
        if "--port" in args:
            idx = args.index("--port")
            if idx + 1 < len(args):
                web_extra += ["--port", args[idx + 1]]
        if "--no-open" in args:
            web_extra.append("--no-open")
        subprocess.run([sys.executable, str(web_path)] + web_extra,
                       cwd=str(BAGO_ROOT.parent))
        return

    if "--live" in args:
        import sys as _sys
        if not _sys.stdout.isatty():
            print("⚠  No hay TTY — usa: bago telemetry --web")
            return
        live_path = TOOLS / "bago_telemetry_live.py"
        if not live_path.exists():
            print("  bago_telemetry_live.py no encontrado en", TOOLS)
            return
        rate_args = []
        if "--rate" in args:
            idx = args.index("--rate")
            if idx + 1 < len(args):
                rate_args = ["--rate", args[idx + 1]]
        subprocess.run([sys.executable, str(live_path)] + rate_args,
                       cwd=str(BAGO_ROOT.parent))
        return
    tel_path = TOOLS / "bago_telemetry.py"
    if not tel_path.exists():
        print("  bago_telemetry.py no encontrado en", TOOLS)
        return
    subprocess.run([sys.executable, str(tel_path)] + args,
                   cwd=str(BAGO_ROOT.parent))


def _cmd_registry() -> None:
    """Show tool registry listing."""
    reg_path = TOOLS / "tool_registry.py"
    if not reg_path.exists():
        print("  tool_registry.py no encontrado en", TOOLS)
        return
    subprocess.run([sys.executable, str(reg_path), "--list"],
                   cwd=str(BAGO_ROOT.parent))


def _find_tool(stem: str) -> "Path | None":
    """Locate a tool by stem: TOOLS first, then rglob fallback.
    Supports dotted module names (e.g. supervision.supervisor)."""
    direct = TOOLS / f"{stem}.py"
    if direct.exists():
        return direct
    if "." in stem:
        dotted = TOOLS / f"{stem.replace(".", os.sep)}.py"
        if dotted.exists():
            return dotted
        dotted2 = BAGO_ROOT / f"{stem.replace(".", os.sep)}.py"
        if dotted2.exists():
            return dotted2
    hits = list(BAGO_ROOT.rglob(f"{stem}.py"))
    return hits[0] if hits else None
def _cmd_neural(rest: list) -> None:
    """bago neural [start|stop|status|nodes|map] — gestiona el Neural Bus SSE."""
    neural = _find_tool("bago_neural")
    if not neural:
        print("  ❌ bago_neural.py no encontrado en", TOOLS)
        return
    subprocess.run([sys.executable, str(neural)] + rest, cwd=str(BAGO_ROOT.parent))


def _cmd_heal_paths(rest: list) -> None:
    """bago heal-paths [--watch] [--forget] — detecta y repara rutas rotas."""
    healer = _find_tool("path_healer")
    if not healer:
        print("  ❌ path_healer.py no encontrado en", TOOLS)
        return
    subprocess.run([sys.executable, str(healer)] + rest, cwd=str(BAGO_ROOT.parent))


def _cmd_npath_dispatch(rest: list) -> None:
    """bago npath <subcomando> ... — Neural Path versioned cognitive graph."""
    # Prefer the package directory (npath/) over the legacy monolithic npath.py
    npath_pkg = TOOLS / "npath"
    if npath_pkg.is_dir() and (npath_pkg / "__main__.py").exists():
        import sys as _sys
        env = {**__import__("os").environ, "PYTHONPATH": str(TOOLS)}
        subprocess.run([_sys.executable, str(npath_pkg)] + rest,
                       cwd=str(BAGO_ROOT.parent), env=env)
        return
    npath = _find_tool("npath")
    if not npath:
        print("  ❌ npath/ package ni npath.py encontrado en", TOOLS)
        return
    import sys as _sys
    subprocess.run([_sys.executable, str(npath)] + rest, cwd=str(BAGO_ROOT.parent))
