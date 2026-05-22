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


def _run_preflight(cmd: str, skip: bool = False) -> None:
    """Enforce preflight policy for cmd via preflight_engine. Fail-closed for core/dangerous commands."""
    pfe_path = TOOLS / "preflight_engine.py"
    if not pfe_path.exists():
        # Engine missing — fail-closed for core and dangerous, warning for others
        mod = _load_registry_mod()
        if mod:
            entry = getattr(mod, "REGISTRY", {}).get(cmd)
            stability = getattr(entry, "stability", "experimental") if entry else "experimental"
            if stability in ("core", "dangerous"):
                print(
                    f"❌ preflight_engine.py missing — cannot run '{cmd}' (stability={stability}).\n"
                    f"   Reinstall BAGO or restore .bago/tools/preflight_engine.py",
                    file=sys.stderr,
                )
                sys.exit(1)
            else:
                print(f"  ⚠  preflight_engine.py missing — skipping preflight for '{cmd}'", file=sys.stderr)
        return
    spec = importlib.util.spec_from_file_location("_bago_pfe", str(pfe_path))
    if spec is None:
        return
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        mod.enforce(cmd, skip_preflight=skip)
    except SystemExit:
        raise
    except Exception as exc:
        mod = _load_registry_mod()
        stability = "experimental"
        if mod:
            entry = getattr(mod, "REGISTRY", {}).get(cmd)
            stability = getattr(entry, "stability", "experimental") if entry else "experimental"
        if stability in ("core", "dangerous"):
            print(
                f"❌ preflight_engine crashed for '{cmd}' (stability={stability}): {exc}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"  ⚠  preflight_engine error: {exc}", file=sys.stderr)


def _get_cmd_risk(cmd: str) -> str:
    """Return risk level for cmd from tool_registry. Defaults to 'safe'."""
    mod = _load_registry_mod()
    if mod:
        entry = getattr(mod, "REGISTRY", {}).get(cmd)
        if entry:
            return getattr(entry, "risk", "safe")
    return "safe"


def _requires_registry_safety(cmd: str) -> bool:
    """True when a command must not bypass registry preflight/risk handling."""
    mod = _load_registry_mod()
    if not mod:
        return False
    entry = getattr(mod, "REGISTRY", {}).get(cmd)
    if not entry:
        return False
    return (
        getattr(entry, "risk", "safe") in ("mutating", "dangerous")
        or getattr(entry, "stability", "core") == "dangerous"
    )


def _check_risk(cmd: str, args: list) -> None:
    """Enforce risk model for cmd. Dangerous commands require --yes or --unsafe.

    --dry-run is only a safe bypass if the command declares supports_dry_run=True in the registry.
    Dangerous commands without an explicit flag exit with a clear error.
    """
    risk = _get_cmd_risk(cmd)
    if risk != "dangerous":
        return

    if "--yes" in args or "--unsafe" in args:
        return

    if "--dry-run" in args:
        mod = _load_registry_mod()
        if mod:
            entry = getattr(mod, "REGISTRY", {}).get(cmd)
            if getattr(entry, "supports_dry_run", False):
                return
        print(
            f"\n⚠️  Comando peligroso: bago {cmd}\n"
            f"   --dry-run no está implementado para este comando.\n"
            f"   Para confirmar, añade: --yes\n"
            f"   Para modo sin restricciones: --unsafe  (úsalo solo si sabes lo que haces)\n",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"\n⚠️  Comando peligroso: bago {cmd}\n"
        f"   Este comando puede modificar estado, datos o configuración de forma irreversible.\n"
        f"   Para confirmar, añade: --yes\n"
        f"   Para modo sin restricciones: --unsafe  (úsalo solo si sabes lo que haces)\n"
        f"   Para vista previa sin ejecución: --dry-run  (si está soportado)\n",
        file=sys.stderr,
    )
    sys.exit(1)


def _start_session(cmd: str, args: list) -> object:
    """Start a session logger. Returns logger or None on failure."""
    sl_path = TOOLS / "session_logger.py"
    if not sl_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("_bago_session_logger", str(sl_path))
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        module = _get_module_for_cmd(cmd)
        return mod.SessionLogger(cmd, args, module)
    except Exception:
        return None


def _load_telemetry() -> object:
    """Load bago_telemetry module. Returns module or None on failure."""
    tel_path = TOOLS / "bago_telemetry.py"
    if not tel_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("_bago_telemetry", str(tel_path))
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _run_self_test(cmd: str, args: list) -> None:
    """Run a module's _self_test() without passing through the dangerous guard.

    Safe bypass: --self-test only calls the module's internal _self_test()
    function directly. It does NOT execute the command's real logic.
    Any module that exposes a _self_test() function can be tested this way.
    """
    # Resolve module from registry
    mod_path: "Path | None" = None
    reg = _load_registry_mod()
    if reg:
        entry = getattr(reg, "REGISTRY", {}).get(cmd)
        if entry:
            module_name = getattr(entry, "module", None)
            if module_name:
                mod_path = _find_tool(module_name)

    if mod_path is None:
        print(f"  ✗ No se encontró el módulo para '{cmd}'", file=sys.stderr)
        sys.exit(1)

    spec = importlib.util.spec_from_file_location(f"_bago_selftest_{cmd}", str(mod_path))
    if spec is None:
        print(f"  ✗ No se pudo cargar el módulo para '{cmd}'", file=sys.stderr)
        sys.exit(1)
    selftest_mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(selftest_mod)
    except Exception as exc:
        print(f"  ✗ Error al cargar el módulo '{cmd}': {exc}", file=sys.stderr)
        sys.exit(1)

    self_test_fn = getattr(selftest_mod, "_self_test", None)
    if self_test_fn is None:
        print(
            f"  ⚠️  El módulo '{cmd}' no expone _self_test().\n"
            f"     Añade una función `def _self_test(): ...` en el módulo para habilitar este modo.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"  🔬 Running self-test for '{cmd}' (safe mode, no real execution)...")
    try:
        result = self_test_fn()
        if result is not None:
            print(result)
        print(f"  ✅ Self-test OK para '{cmd}'")
    except Exception as exc:
        print(f"  ✗ Self-test FAILED para '{cmd}': {exc}", file=sys.stderr)
        sys.exit(1)
