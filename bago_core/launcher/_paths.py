"""bago_core.launcher._paths — Path discovery, constants, color helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.dont_write_bytecode = True

# Windows: force UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

_LAUNCHER_PATH = Path(__file__).resolve()
BAGO_CORE_DIR = _LAUNCHER_PATH.parent.parent  # launcher/ -> bago_core/
_USER_ACTIVE = Path.home() / ".bago" / "active" / ".bago"
_CANDIDATE_ROOTS = [
    BAGO_CORE_DIR.parent / ".bago",     # repo mode
    BAGO_CORE_DIR / ".bago",            # package mode
    _USER_ACTIVE,                        # global install
]

BAGO_ROOT: Path | None = None
for _cand in _CANDIDATE_ROOTS:
    if (_cand / "pack.json").exists() or (_cand / "tools").exists():
        BAGO_ROOT = _cand
        break
if BAGO_ROOT is None:
    BAGO_ROOT = BAGO_CORE_DIR.parent / ".bago"

TOOLS = BAGO_ROOT / "tools"
CORE  = BAGO_ROOT / "core"

_USE_COLOR = sys.stdin.isatty()

def GREEN(t): return f"\033[1;32m{t}\033[0m" if _USE_COLOR else t
def RED(t):   return f"\033[1;31m{t}\033[0m" if _USE_COLOR else t
def YELLOW(t): return f"\033[1;33m{t}\033[0m" if _USE_COLOR else t
def CYAN(t):  return f"\033[1;36m{t}\033[0m" if _USE_COLOR else t
def BOLD(t):  return f"\033[1m{t}\033[0m" if _USE_COLOR else t
def DIM(t):   return f"\033[2m{t}\033[0m" if _USE_COLOR else t

def default_user_home() -> Path:
    try:
        return Path.home()
    except Exception:
        return Path(".")
