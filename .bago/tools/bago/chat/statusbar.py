"""bago.chat.statusbar — barra de estado superior/inferior y prompt indicator."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
import shutil as _shutil
import time as _time
from pathlib import Path

try:
    if os.environ.get("BAGO_NO_PROMPT_TOOLKIT", "0") == "1":
        raise ModuleNotFoundError("prompt_toolkit disabled by BAGO_NO_PROMPT_TOOLKIT=1")
    from prompt_toolkit.formatted_text import FormattedText
except ModuleNotFoundError:
    def FormattedText(parts):
        return parts

from ..constants import BAGO_DIR
from ..cwd import get_user_cwd

# ── Ruta del repo para la barra de estado ────────────────────────────────────
_FW_ROOT = str(BAGO_DIR.parent)

# Frames de la avispa ASCII (alterna cada ~0.5s)
_BEE_FRAMES = ["╱◉╲ ", "─◉─ ", "╲◉╱ ", "─◉─ "]


def _bee_tick() -> str:
    return _BEE_FRAMES[int(_time.monotonic() * 2) % len(_BEE_FRAMES)]


def _topbar_prompt(route_mode: str) -> FormattedText:
    """Barra superior: avispa animada + ◆ BAGO + ruta + cwd."""
    cols = _shutil.get_terminal_size((80, 24)).columns
    cwd  = get_user_cwd()
    bee  = _bee_tick()
    badge = f"{bee}◆ BAGO"
    sep   = "  │  "
    left  = f" {badge}{sep}FW: {_FW_ROOT}"
    left_w = len(left)
    is_system32 = str(cwd).lower().endswith("\\windows\\system32")
    ws_name = "sin workspace" if is_system32 else cwd.name
    right_full  = f"WS: {ws_name}  ·  {cwd}  "
    right_short = f"WS: {ws_name}  "
    right = right_full if left_w + len(right_full) + 2 <= cols else right_short
    pad = max(1, cols - left_w - len(right))
    bar = (left + " " * pad + right)[:cols]
    return FormattedText([
        ("class:statusbar", bar),
        ("", "\n"),
        ("class:prompt", f"[BAGO|{route_mode}] > "),
    ])


def _bottom_bar(session=None) -> list:
    cols = _shutil.get_terminal_size((80, 24)).columns
    line = [("class:statusbar", "─" * cols)]
    if not session or not getattr(session, "timeline_visible", False):
        return line

    rows = []
    timeline = []
    try:
        timeline = session.timeline_view(limit=6, width=max(48, cols - 4))
    except Exception:
        timeline = ["(timeline unavailable)"]

    rows.extend([
        ("class:statusbar", "\n"),
        ("class:timeline.title", "Timeline"),
        ("class:timeline.meta", "  (Ctrl+T para ocultar)"),
        ("class:statusbar", "\n"),
    ])
    for row in timeline:
        rows.append(("class:timeline.event", f"  {row}"))
        rows.append(("class:statusbar", "\n"))
    return line + rows


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

    if getattr(session, "timeline_visible", False):
        indicator += " TL"

    if getattr(session, "local_lock", False):
        indicator = "LOCAL" + indicator.replace("AUTO", "").replace("MANUAL", "")

    return indicator
