"""creation_mode.config — Rutas, colores y constantes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── Dependencias rich ─────────────────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.rule import Rule
    from rich.align import Align
    from rich.live import Live
    from rich import box as rbox
except ImportError as _exc:
    raise SystemExit(f"ERROR: pip install rich  ({_exc})") from _exc

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style
    from prompt_toolkit.formatted_text import HTML
    _HAS_PROMPT_TOOLKIT = True
except ImportError:
    PromptSession = None
    Style = None
    HTML = None
    _HAS_PROMPT_TOOLKIT = False

# ── Rutas ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parents[2]
BAGO_ROOT  = ROOT / ".bago"
STATE      = BAGO_ROOT / "state"
TOOLS_DIR  = BAGO_ROOT / "tools"
DB         = STATE / "bago.db"

console = Console()

# ── Paleta de colores (dark theme como VS Code) ───────────────────────────────
C_BG         = "grey11"
C_BORDER     = "grey30"
C_HEADER     = "bold white"
C_ITEM       = "grey82"
C_ITEM_DIM   = "grey50"
C_ACCENT     = "dodger_blue1"
C_GREEN      = "spring_green3"
C_YELLOW     = "yellow3"
C_RED        = "red3"
C_INPUT_BG   = "grey15"
