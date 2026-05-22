"""creation_mode.data — Loaders de estado, tareas, proyectos, issues."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import STATE, DB, TOOLS_DIR


def load_global_state() -> dict:
    try:
        return json.loads((STATE / "global_state.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_recent_sessions(n: int = 8) -> list[dict]:
    hist_file = STATE / "execution_history.jsonl"
    sessions: list[dict] = []
    if hist_file.exists():
        try:
            lines = hist_file.read_text(encoding="utf-8").strip().splitlines()
            seen: set[str] = set()
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                    key = entry.get("task", "")[:40]
                    if key and key not in seen:
                        seen.add(key)
                        sessions.append(entry)
                        if len(sessions) >= n:
                            break
                except Exception:
                    pass
        except Exception:
            pass
    return sessions


def load_agents() -> list[str]:
    reg = STATE / "agents_registry.json"
    if not reg.exists():
        return []
    try:
        data = json.loads(reg.read_text(encoding="utf-8"))
        return [k for k in data if not k.startswith("_")]
    except Exception:
        return []


def load_tools_count() -> int:
    try:
        return len(list((TOOLS_DIR).glob("*.py")))
    except Exception:
        return 0


def load_active_task() -> dict | None:
    task_file = STATE / "pending_w2_task.json"
    if not task_file.exists():
        return None
    try:
        return json.loads(task_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_project() -> dict:
    rc = STATE / "repo_context.json"
    if not rc.exists():
        return {}
    try:
        return json.loads(rc.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_projects() -> list[dict]:
    rp = STATE / "recent_projects.json"
    if not rp.exists():
        return []
    try:
        data = json.loads(rp.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_issues() -> list[dict]:
    issues: list[dict] = []
    if DB.exists():
        try:
            con = sqlite3.connect(str(DB), timeout=1)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                """SELECT id, title, status, priority, source FROM issues
                   WHERE status IN ('open','in-progress','bago-in-progress')
                   ORDER BY priority DESC, created_at DESC LIMIT 15"""
            ).fetchall()
            for r in rows:
                issues.append(dict(r))
            con.close()
        except Exception:
            pass
    if not issues:
        issues_file = STATE / "issues.json"
        if issues_file.exists():
            try:
                data = json.loads(issues_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    issues = [i for i in data if i.get("status") in ("open", "in-progress", "bago-in-progress")][:15]
            except Exception:
                pass
    return issues


def load_layer_config() -> dict:
    cfg = STATE / "creation_studio.json"
    if not cfg.exists():
        return {}
    try:
        return json.loads(cfg.read_text(encoding="utf-8"))
    except Exception:
        return {}
