"""bago_core.launcher._config — Loading config, registry, commands."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from bago_core.launcher._paths import TOOLS, BAGO_ROOT, CORE

def load_bp() -> dict:
    bp_path = BAGO_ROOT / "state" / "bago.db"
    if not bp_path.exists():
        return {}
    try:
        import sqlite3
        conn = sqlite3.connect(str(bp_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT key, value FROM kv WHERE key IN ('current_bp', 'current_sprint', 'current_workflow')")
        result = {row["key"]: row["value"] for row in cur.fetchall()}
        conn.close()
        return result
    except Exception:
        return {}

def load_dispatcher() -> dict | None:
    disp_path = BAGO_ROOT / "state" / "bago.db"
    try:
        import sqlite3
        conn = sqlite3.connect(str(disp_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT value FROM kv WHERE key = 'dispatcher'")
        row = cur.fetchone()
        conn.close()
        if row:
            return json.loads(row["value"])
    except Exception:
        pass
    return None

def load_context() -> dict | None:
    ctx_path = BAGO_ROOT / "state" / "bago.db"
    try:
        import sqlite3
        conn = sqlite3.connect(str(ctx_path))
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT value FROM kv WHERE key = 'context'")
        row = cur.fetchone()
        conn.close()
        if row:
            return json.loads(row["value"])
    except Exception:
        pass
    return None

def load_registry_mod():
    reg_path = TOOLS / "_registry_entries.py"
    if not reg_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_registry_entries", str(reg_path))
        mod = importlib.util.module_from_spec(spec)
        if str(TOOLS) not in sys.path:
            sys.path.insert(0, str(TOOLS))
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None

def build_commands() -> dict:
    reg = load_registry_mod()
    if reg and hasattr(reg, "REGISTRY"):
        return {k: v.script for k, v in reg.REGISTRY.items() if hasattr(v, "script")}
    return {}

def build_deprecated_map() -> dict[str, str]:
    reg = load_registry_mod()
    if reg and hasattr(reg, "REGISTRY"):
        return {k: v.redirect for k, v in reg.REGISTRY.items()
                if hasattr(v, "redirect") and v.redirect}
    return {}

def get_module_for_cmd(cmd: str) -> str:
    reg = load_registry_mod()
    if reg and hasattr(reg, "REGISTRY"):
        entry = reg.REGISTRY.get(cmd)
        if entry and hasattr(entry, "module"):
            return entry.module
    return ""

# Lazy-loaded singletons (computed on first access)
COMMANDS: dict = {}
DEPRECATED_MAP: dict[str, str] = {}

def _ensure_loaded():
    global COMMANDS, DEPRECATED_MAP
    if not COMMANDS:
        COMMANDS = build_commands()
        DEPRECATED_MAP = build_deprecated_map()
