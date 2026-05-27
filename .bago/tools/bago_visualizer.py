#!/usr/bin/env python3
"""
bago_visualizer.py — BAGO Timeline & Metrics Visualizer

Recolecta datos de todo el ecosistema BAGO y genera:
  1. timeline_data.json — JSON unificado con sesiones, métricas, artefactos, análisis
  2. bago_visualizer.html — Visor web estilo Pi (oscuro, timeline, métricas, artefactos)

Uso:
  python3 bago_visualizer.py --refresh     # regenera datos + HTML
  python3 bago_visualizer.py --serve       # sirve en localhost:8766
  python3 bago_visualizer.py --refresh --serve

Integración automática:
  Se invoca post-harvest (cosecha) y post-session-close para mantener timeline actualizado.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import http.server
import socketserver
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter, defaultdict

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".bago" / "state"
TOOLS = ROOT / ".bago" / "tools"
OUT_JSON = STATE / "timeline_data.json"
OUT_HTML = STATE / "bago_visualizer.html"
HTML_TEMPLATE = TOOLS / "bago_visualizer.html"

# ═══════════════════════════════════════════════════════════════════════════════
# RECOLECTOR DE DATOS
# ═══════════════════════════════════════════════════════════════════════════════

def _slurp_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def _slurp_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                lines.append(json.loads(line))
            except Exception:
                pass
    return lines

def _parse_iso(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return None

def _format_duration(ms: float) -> str:
    if ms >= 1000:
        return f"{ms/1000:.1f}s"
    return f"{int(ms)}ms"

def _load_sessions() -> list[dict]:
    sessions: list[dict] = []
    sess_dir = STATE / "sessions"
    if not sess_dir.exists():
        return sessions
    for p in sorted(sess_dir.glob("SES-*.json"), reverse=True):
        data = _slurp_json(p)
        if data:
            sessions.append({
                "id": data.get("session_id", p.stem),
                "type": data.get("task_type", "unknown"),
                "workflow": data.get("selected_workflow", ""),
                "status": data.get("status", "unknown"),
                "goal": data.get("user_goal", "")[:200],
                "next_step": data.get("next_step", ""),
                "artifacts": data.get("artifacts", []),
                "decisions": data.get("decisions", []),
                "health": data.get("health_at_harvest", {}),
                "created": data.get("created_at", ""),
                "updated": data.get("updated_at", ""),
                "timestamp": data.get("created_at", ""),
                "source_file": str(p.relative_to(ROOT)),
            })
    # Also load session close markdowns as events
    for p in sorted(sess_dir.glob("SESSION_CLOSE_*.md"), reverse=True):
        created = _parse_session_close_date(p.stem)
        sessions.append({
            "id": p.stem,
            "type": "session_close",
            "workflow": "",
            "status": "closed",
            "goal": "",
            "next_step": "",
            "artifacts": [str(p.relative_to(ROOT))],
            "decisions": [],
            "health": {},
            "created": created.isoformat() if created else "",
            "updated": created.isoformat() if created else "",
            "timestamp": created.isoformat() if created else "",
            "source_file": str(p.relative_to(ROOT)),
        })
    return sessions

def _parse_session_close_date(stem: str) -> datetime | None:
    """SESSION_CLOSE_20260527_084509 → 2026-05-27T08:45:09"""
    try:
        parts = stem.replace("SESSION_CLOSE_", "").split("_")
        if len(parts) >= 2:
            d = parts[0]  # 20260527
            t = parts[1]  # 084509
            return datetime.strptime(f"{d}{t}", "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None

def _load_changes() -> list[dict]:
    changes: list[dict] = []
    chg_dir = STATE / "changes"
    if not chg_dir.exists():
        return changes
    for p in sorted(chg_dir.glob("BAGO-CHG-*.json"), reverse=True):
        data = _slurp_json(p)
        if data:
            changes.append({
                "id": data.get("id", p.stem),
                "title": data.get("title", ""),
                "status": data.get("status", ""),
                "priority": data.get("priority", ""),
                "timestamp": data.get("created_at", ""),
                "source_file": str(p.relative_to(ROOT)),
            })
    return changes

def _load_evidences() -> list[dict]:
    evs: list[dict] = []
    ev_dir = STATE / "evidences"
    if not ev_dir.exists():
        return evs
    for p in sorted(ev_dir.glob("BAGO-EVD-*.json"), reverse=True):
        data = _slurp_json(p)
        if data:
            evs.append({
                "id": data.get("id", p.stem),
                "type": data.get("type", ""),
                "status": data.get("status", ""),
                "metric": data.get("metric", ""),
                "timestamp": data.get("created_at", ""),
                "source_file": str(p.relative_to(ROOT)),
            })
    return evs

def _load_health_metrics() -> dict:
    data = _slurp_json(STATE / "health.json")
    if not data:
        return {}
    return data

def _load_global_state() -> dict:
    data = _slurp_json(STATE / "global_state.json")
    if not data:
        return {}
    return {
        "version": data.get("bago_version", ""),
        "mode": data.get("mode", ""),
        "status": data.get("status", ""),
        "inventory": data.get("inventory", {}),
        "last_completed": {
            "session": data.get("last_completed_session_id", ""),
            "task": data.get("last_completed_task_type", ""),
            "workflow": data.get("last_completed_workflow", ""),
            "change": data.get("last_completed_change_id", ""),
            "evidence": data.get("last_completed_evidence_id", ""),
        },
        "sprint": data.get("sprint_status", {}),
    }

def _load_shell_log() -> list[dict]:
    entries = _slurp_jsonl(STATE / "shell_autonomous_log.jsonl")
    # Keep last 200, deduplicate consecutive identical commands
    seen: set = set()
    result: list[dict] = []
    for e in reversed(entries):
        key = e.get("command", "") + e.get("timestamp", "")
        if key not in seen:
            seen.add(key)
            result.append({
                "command": e.get("command", ""),
                "canonical": e.get("canonical", ""),
                "category": e.get("category", ""),
                "exit_code": e.get("exit_code", -1),
                "authorized": e.get("authorized", False),
                "needs_auth": e.get("needs_auth", False),
                "dry_run": e.get("dry_run", False),
                "duration_ms": e.get("duration_ms", 0.0),
                "timestamp": e.get("timestamp", ""),
            })
    result.reverse()
    return result[-200:]

def _load_learnings() -> list[dict]:
    lines = _slurp_jsonl(STATE / "auto_learnings.jsonl")
    return [{"text": l.get("text", ""), "timestamp": l.get("timestamp", "")} for l in lines[-50:]]

def _load_implemented_ideas() -> list[dict]:
    data = _slurp_json(STATE / "implemented_ideas.json")
    if not data:
        return []
    return data.get("implemented", [])[-20:]

def _compute_metrics(sessions: list[dict], changes: list[dict], evidences: list[dict], shell_log: list[dict]) -> dict:
    now = datetime.now(timezone.utc)
    total_sessions = len(sessions)
    total_changes = len(changes)
    total_evidences = len(evidences)

    # Activity by day
    by_day: dict[str, int] = Counter()
    for s in sessions:
        dt = _parse_iso(s.get("timestamp", ""))
        if dt:
            by_day[dt.strftime("%Y-%m-%d")] += 1
    for c in changes:
        dt = _parse_iso(c.get("timestamp", ""))
        if dt:
            by_day[dt.strftime("%Y-%m-%d")] += 1
    for e in evidences:
        dt = _parse_iso(e.get("timestamp", ""))
        if dt:
            by_day[dt.strftime("%Y-%m-%d")] += 1

    # Activity last 7 days
    last7 = {}
    for i in range(7):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        last7[d] = by_day.get(d, 0)

    # Shell stats
    shell_categories = Counter(e.get("category", "unknown") for e in shell_log)
    shell_dangerous = sum(1 for e in shell_log if e.get("needs_auth"))
    shell_blocked = sum(1 for e in shell_log if e.get("needs_auth") and not e.get("authorized"))

    # Session types
    session_types = Counter(s.get("type", "unknown") for s in sessions)

    # Health trend (simplified: count of health score mentions)
    health_scores: list[dict] = []
    for s in sessions:
        h = s.get("health", {})
        if h.get("score") is not None:
            dt = _parse_iso(s.get("timestamp", ""))
            health_scores.append({
                "date": dt.strftime("%Y-%m-%d") if dt else "",
                "score": h.get("score", 0),
                "icon": h.get("icon", ""),
            })

    return {
        "summary": {
            "total_sessions": total_sessions,
            "total_changes": total_changes,
            "total_evidences": total_evidences,
            "total_shell_commands": len(shell_log),
            "shell_dangerous_attempts": shell_dangerous,
            "shell_blocked_commands": shell_blocked,
        },
        "activity_by_day": dict(sorted(by_day.items())),
        "activity_last_7_days": last7,
        "session_types": dict(session_types),
        "shell_categories": dict(shell_categories),
        "health_scores": health_scores[-30:],
    }

def refresh() -> dict:
    """Regenera timeline_data.json a partir de todas las fuentes de BAGO."""
    print("  🔄 Recolectando datos de BAGO...")

    sessions = _load_sessions()
    changes = _load_changes()
    evidences = _load_evidences()
    health = _load_health_metrics()
    global_state = _load_global_state()
    shell_log = _load_shell_log()
    learnings = _load_learnings()
    ideas = _load_implemented_ideas()
    metrics = _compute_metrics(sessions, changes, evidences, shell_log)

    # Build unified timeline (all events sorted by time)
    timeline_events: list[dict] = []
    for s in sessions:
        dt = _parse_iso(s.get("timestamp", ""))
        timeline_events.append({
            "time": s.get("timestamp", ""),
            "sort_key": dt.timestamp() if dt else 0,
            "type": "session",
            "subtype": s.get("type", ""),
            "id": s["id"],
            "title": s.get("goal", "")[:120] or s["id"],
            "status": s.get("status", ""),
            "health_icon": s.get("health", {}).get("icon", ""),
            "health_score": s.get("health", {}).get("score"),
            "artifacts_count": len(s.get("artifacts", [])),
            "source": s.get("source_file", ""),
        })
    for c in changes:
        dt = _parse_iso(c.get("timestamp", ""))
        timeline_events.append({
            "time": c.get("timestamp", ""),
            "sort_key": dt.timestamp() if dt else 0,
            "type": "change",
            "subtype": c.get("status", ""),
            "id": c["id"],
            "title": c.get("title", ""),
            "status": c.get("status", ""),
            "priority": c.get("priority", ""),
            "source": c.get("source_file", ""),
        })
    for e in evidences:
        dt = _parse_iso(e.get("timestamp", ""))
        timeline_events.append({
            "time": e.get("timestamp", ""),
            "sort_key": dt.timestamp() if dt else 0,
            "type": "evidence",
            "subtype": e.get("type", ""),
            "id": e["id"],
            "title": e.get("metric", "")[:120] or e["id"],
            "status": e.get("status", ""),
            "source": e.get("source_file", ""),
        })
    for cmd in shell_log[-100:]:
        dt = _parse_iso(cmd.get("timestamp", ""))
        timeline_events.append({
            "time": cmd.get("timestamp", ""),
            "sort_key": dt.timestamp() if dt else 0,
            "type": "shell_command",
            "subtype": cmd.get("category", ""),
            "id": cmd.get("canonical", ""),
            "title": cmd.get("command", ""),
            "status": "blocked" if cmd.get("needs_auth") and not cmd.get("authorized") else ("dry" if cmd.get("dry_run") else ("ok" if cmd.get("exit_code") == 0 else "error")),
            "duration_ms": cmd.get("duration_ms", 0),
            "source": "shell_autonomous_log.jsonl",
        })

    timeline_events.sort(key=lambda x: (-x["sort_key"], x["type"]))

    payload = {
        "meta": {
            "generated": datetime.now(timezone.utc).isoformat(),
            "version": global_state.get("version", "3.5.0"),
            "generator": "bago_visualizer.py",
            "data_sources": [
                "state/sessions/*.json",
                "state/sessions/SESSION_CLOSE_*.md",
                "state/changes/BAGO-CHG-*.json",
                "state/evidences/BAGO-EVD-*.json",
                "state/health.json",
                "state/global_state.json",
                "state/shell_autonomous_log.jsonl",
                "state/auto_learnings.jsonl",
                "state/implemented_ideas.json",
            ],
        },
        "global": global_state,
        "health": health,
        "metrics": metrics,
        "timeline": timeline_events,
        "sessions": sessions[:50],
        "changes": changes[:50],
        "evidences": evidences[:50],
        "shell_log": shell_log,
        "learnings": learnings,
        "ideas": ideas,
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if HTML_TEMPLATE.exists():
        shutil.copy2(str(HTML_TEMPLATE), str(OUT_HTML))
    print(f"  ✅ timeline_data.json → {len(timeline_events)} eventos, {len(sessions)} sesiones")
    print(f"  ✅ Cambios: {len(changes)} | Evidencias: {len(evidences)} | Shell: {len(shell_log)} comandos")
    return payload


# ═══════════════════════════════════════════════════════════════════════════════
# SERVIDOR HTTP LOCAL
# ═══════════════════════════════════════════════════════════════════════════════

class _Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATE), **kwargs)

    def log_message(self, format, *args):
        pass  # silent


def serve(port: int = 8766) -> None:
    if not OUT_JSON.exists():
        print(f"  ⚠️  {OUT_JSON.name} no existe. Ejecuta --refresh primero.")
        return
    print(f"  🌐 Servidor en http://localhost:{port}/bago_visualizer.html")
    print(f"  📊 Datos en: http://localhost:{port}/timeline_data.json")
    print(f"  ⏹  Ctrl+C para detener")
    try:
        with socketserver.TCPServer(("", port), _Handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  ⏹  Servidor detenido.")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    do_refresh = False
    do_serve = False
    port = 8766

    for arg in sys.argv[1:]:
        if arg in ("--refresh", "-r"):
            do_refresh = True
        elif arg in ("--serve", "-s"):
            do_serve = True
        elif arg.startswith("--port="):
            port = int(arg.split("=", 1)[1])

    # Default: refresh if data stale (> 5 min) or missing
    if not OUT_JSON.exists():
        do_refresh = True
    else:
        mtime = OUT_JSON.stat().st_mtime
        if datetime.now().timestamp() - mtime > 300:
            do_refresh = True

    if do_refresh:
        refresh()

    if do_serve or not do_refresh:
        serve(port)

    return 0


def _self_test():
    payload = refresh()
    assert "timeline" in payload
    assert "metrics" in payload
    print("  1/1 tests pasaron")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
