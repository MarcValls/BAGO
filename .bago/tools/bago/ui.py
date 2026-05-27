"""bago.ui - compatibilidad pública de UI."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .ui_base import BAGO_VERSION, COLORS, CtrlCGuard, banner, console, pe, pi, show_response, _stdin_prompt
from .ui_dialogs import (
    _menu_action,
    _menu_confirm,
    _menu_input,
    _menu_multiselect,
    _menu_pick,
    _menu_pick_provider_model,
    _menu_pick_tabs,
    _menu_select,
    _toggle_menu,
)

__all__ = [
    "BAGO_VERSION", "COLORS", "CtrlCGuard", "banner", "console",
    "pe", "pi", "show_response",
    "_stdin_prompt",
    "_menu_action", "_menu_confirm", "_menu_input", "_menu_multiselect",
    "_menu_pick", "_menu_pick_provider_model", "_menu_pick_tabs", "_menu_select", "_toggle_menu",
]



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
