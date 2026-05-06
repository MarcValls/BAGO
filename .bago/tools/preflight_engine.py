#!/usr/bin/env python3
"""preflight_engine.py — Fail-closed preflight enforcement (PR-03 Kernel Lockdown).

Enforces preflight_policy from tool_registry:

  "required"  → if preflight missing or fails: BLOCK (never execute)
  "optional"  → if preflight fails: WARNING shown, execution continues
  "none"      → skip all preflight (only for internal/safe commands)

Policy source: ToolEntry.preflight_policy from REGISTRY.
Never fail-open for commands with preflight_policy="required".
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).parent


def _load_mod(path: Path, name: str):
    """Load a Python module from path without polluting sys.path."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    # Must register in sys.modules BEFORE exec_module so @dataclass can resolve
    # cls.__module__ back to the live module (Python 3.11+ requirement).
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod
    except Exception:
        sys.modules.pop(name, None)
        return None


def _get_policy(cmd: str) -> str:
    """Return preflight_policy for cmd from tool_registry. Defaults to 'optional'."""
    reg_path = TOOLS_DIR / "tool_registry.py"
    if not reg_path.exists():
        return "optional"
    mod = _load_mod(reg_path, "_bago_pfe_registry")
    if mod is None:
        return "optional"
    entry = getattr(mod, "REGISTRY", {}).get(cmd)
    if entry is None:
        return "optional"
    return getattr(entry, "preflight_policy", "optional")


def _run_checks(cmd: str) -> bool:
    """Run preflight checks from preflight.py for cmd. Returns True on pass."""
    pf_path = TOOLS_DIR / "preflight.py"
    if not pf_path.exists():
        return False  # missing preflight — caller decides what to do

    mod = _load_mod(pf_path, "_bago_pfe_preflight")
    if mod is None:
        return False  # crashed loading — caller decides

    try:
        return mod.run_from_registry(cmd, exit_on_fail=False)
    except Exception:
        return False


def enforce(cmd: str, skip_preflight: bool = False) -> None:
    """Enforce preflight policy for cmd. May call sys.exit(1) if fail-closed.

    Args:
        cmd: The BAGO command being dispatched.
        skip_preflight: If True, skip checks (only honoured when policy != "required").

    Behaviour:
        policy="required"  → run checks; if missing/fail → sys.exit(1) with clear error
        policy="optional"  → run checks; if fail → print warning, continue
        policy="none"      → skip all checks silently
    """
    policy = _get_policy(cmd)

    if policy == "none":
        return

    if skip_preflight:
        if policy == "required":
            # --skip-preflight is NOT honoured for required commands
            print(
                f"❌ --skip-preflight no está permitido para '{cmd}' (preflight_policy=required).",
                file=sys.stderr,
            )
            print("   Ejecuta: python3 bago doctor", file=sys.stderr)
            sys.exit(1)
        # policy="optional" — honour skip
        return

    pf_path = TOOLS_DIR / "preflight.py"
    if not pf_path.exists():
        if policy == "required":
            print(
                f"\n❌ Preflight failed closed.\n"
                f"   Command: bago {cmd}\n"
                f"   Reason:  preflight.py no encontrado.\n"
                f"   Usa:     python3 bago doctor",
                file=sys.stderr,
            )
            sys.exit(1)
        # optional: warn but continue
        print(f"  ⚠  preflight.py no encontrado para '{cmd}' — continuando.", file=sys.stderr)
        return

    ok = _run_checks(cmd)

    if ok:
        return

    if policy == "required":
        print(
            f"\n❌ Preflight failed closed.\n"
            f"   Command: bago {cmd}\n"
            f"   Reason:  preflight checks fallaron (ver arriba).\n"
            f"   Usa:     python3 bago doctor",
            file=sys.stderr,
        )
        sys.exit(1)

    # optional: checks failed but we continue (warning already printed by preflight.py)
    print(f"  ⚠  Preflight warnings para '{cmd}' — continuando de todos modos.", file=sys.stderr)
