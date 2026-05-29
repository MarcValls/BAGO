from pathlib import Path

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json

from .constants import ORCH_FILE, ROUTING_FILE, STATE_DIR, TOOLBOXES_DIR
from .ui import pe

AGENTS_FILE  = STATE_DIR / "agents_registry.json"
SKILLS_FILE  = STATE_DIR / "skill_registry.json"
ROUTING_FILE_P = ROUTING_FILE   # alias for backward compat — same file, one definition
_STATE_DIR   = STATE_DIR

__all__ = [
    "AGENTS_FILE",
    "SKILLS_FILE",
    "ORCH_FILE",
    "ROUTING_FILE_P",
    "STATE_DIR",
    "TOOLBOXES_DIR",
    "_STATE_DIR",
    "_load_json",
    "_save_json",
]

def _load_json(p):
    try:
        # utf-8-sig handles BOM produced by some Windows editors
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        pe(f"Error leyendo {p.name}: {e}"); return {}

def _save_json(p, data):
    try:
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        pe(f"Error guardando {p.name}: {e}"); return False


def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(f"{Path(__file__).name} --test: PASS (imports OK)")
    return 0
if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
