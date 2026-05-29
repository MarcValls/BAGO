"""creation_mode.plugin — Interfaz para integración con BAGO.

Expone entrypoints que BAGO puede llamar sin saber nada de argparse.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .engine import render_once, run_interactive


def bago_entrypoint(**kwargs) -> int:
    """Entrypoint genérico para BAGO launcher."""
    tab = kwargs.get("tab", "cambios")
    layer = kwargs.get("layer", "")
    sublayer = kwargs.get("sublayer", "")
    once = kwargs.get("once", False)
    if once:
        render_once(tab, layer, sublayer)
        return 0
    return run_interactive(tab, layer, sublayer)


def bago_create_once(tab: str = "cambios", layer: str = "", sublayer: str = "") -> None:
    """Render único para plugins que solo necesitan pintar."""
    render_once(tab, layer, sublayer)



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
