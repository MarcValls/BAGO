"""bago.chat.statusbar — barra de estado superior/inferior y prompt indicator."""

import shutil as _shutil
import time as _time
from pathlib import Path

from prompt_toolkit.formatted_text import FormattedText

from ..constants import BAGO_DIR

# ── Ruta del repo para la barra de estado ────────────────────────────────────
_FW_ROOT = str(BAGO_DIR.parent)

# Frames de la avispa ASCII (alterna cada ~0.5s)
_BEE_FRAMES = ["╱◉╲ ", "─◉─ ", "╲◉╱ ", "─◉─ "]


def _bee_tick() -> str:
    return _BEE_FRAMES[int(_time.monotonic() * 2) % len(_BEE_FRAMES)]


def _topbar_prompt(route_mode: str) -> FormattedText:
    """Barra superior: avispa animada + ◆ BAGO + ruta + cwd."""
    cols = _shutil.get_terminal_size((80, 24)).columns
    cwd  = Path.cwd()
    bee  = _bee_tick()
    badge = f"{bee}◆ BAGO"
    sep   = "  │  "
    left  = f" {badge}{sep}{_FW_ROOT}"
    left_w = len(left)
    right_full  = f"{cwd.name}  ·  {cwd}  "
    right_short = f"{cwd.name}  "
    right = right_full if left_w + len(right_full) + 2 <= cols else right_short
    pad = max(1, cols - left_w - len(right))
    bar = (left + " " * pad + right)[:cols]
    return FormattedText([
        ("class:statusbar", bar),
        ("", "\n"),
        ("class:prompt", f"[BAGO|{route_mode}] > "),
    ])


def _bottom_bar() -> list:
    cols = _shutil.get_terminal_size((80, 24)).columns
    return [("class:statusbar", "─" * cols)]


def _prompt_indicator(session) -> str:
    """Construye el indicador de modo del prompt.

    Prioridad:
      1. Routing real ocurrido (chain/ensemble/single) → modo en MAYÚSCULAS
      2. autoroute ON → AUTO
      3. autoroute OFF → MANUAL
    Sufijo  :A  si modo autónomo activo.
    """
    last = session.last_route or {}
    last_mode = last.get("mode", "")

    if last_mode and last_mode != "manual":
        indicator = last_mode.upper()
    elif session.autoroute:
        indicator = "AUTO"
    else:
        indicator = "MANUAL"

    if session.autonomous:
        indicator += ":A"

    if session.tumba_mode:
        indicator += " 🪦"

    return indicator
