
import json

from .constants import ORCH_FILE, ROUTING_FILE, STATE_DIR
from .ui import pe

AGENTS_FILE = STATE_DIR / "agents_registry.json"
SKILLS_FILE = STATE_DIR / "skill_registry.json"
ROUTING_FILE_P = ROUTING_FILE   # alias for backward compat — same file, one definition
_STATE_DIR = STATE_DIR

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
