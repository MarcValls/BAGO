#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_reopen.py — Reanuda sesión desde el último cierre sin reconstruir contexto manualmente.

Lee el SESSION_CLOSE más reciente y presenta la información mínima necesaria
para retomar el trabajo: última tarea completada, tarea pendiente (si existe),
salud del sistema y siguiente acción recomendada.

Uso:
  bago reopen            # muestra contexto de reanudación
  bago reopen --restore  # restaura la última tarea en pending_w2_task.json
  bago reopen --test     # autotest

# REOPEN_FROM_CONTINUITY_IMPLEMENTED
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT         = Path(__file__).resolve().parents[2]
STATE_DIR    = ROOT / ".bago" / "state"
SESSIONS_DIR = STATE_DIR / "sessions"
TASK_FILE    = STATE_DIR / "pending_w2_task.json"
IDEAS_FILE   = STATE_DIR / "implemented_ideas.json"
GS_FILE      = STATE_DIR / "global_state.json"

# ANSI helpers
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"

def _c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}"


def _find_latest_close() -> Path | None:
    """Returns the most recent SESSION_CLOSE_*.md path, or None."""
    if not SESSIONS_DIR.exists():
        return None
    files = sorted(SESSIONS_DIR.glob("SESSION_CLOSE_*.md"), reverse=True)
    return files[0] if files else None


def _parse_close(path: Path) -> dict:
    """Extracts fields from SESSION_CLOSE markdown table."""
    result: dict = {"timestamp": "", "idea": "", "workflow": "", "objetivo": "", "alcance": "", "metrica": ""}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return result

    # Header timestamp
    m = re.search(r"Cierre de sesión — (.+)", text)
    if m:
        result["timestamp"] = m.group(1).strip()

    # Table rows: | Campo | Valor |
    for row_re, key in [
        (r"\|\s*Idea\s*\|\s*(.+?)\s*\|", "idea"),
        (r"\|\s*Workflow\s*\|\s*(.+?)\s*\|", "workflow"),
        (r"\|\s*Objetivo\s*\|\s*(.+?)\s*\|", "objetivo"),
        (r"\|\s*Alcance\s*\|\s*(.+?)\s*\|", "alcance"),
        (r"\|\s*Métrica\s*\|\s*(.+?)\s*\|", "metrica"),
    ]:
        m = re.search(row_re, text)
        if m:
            result[key] = m.group(1).strip()

    return result


def _load_pending_task() -> dict | None:
    if not TASK_FILE.exists():
        return None
    try:
        d = json.loads(TASK_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def _load_health() -> tuple[int, str]:
    """Returns (health_pct, health_label)."""
    try:
        d = json.loads(GS_FILE.read_text(encoding="utf-8"))
        pct = d.get("guardian_findings", {}).get("health_pct", 0)
        label = d.get("last_validation", {}).get("health", f"{pct}/100")
        return int(pct), str(label)
    except Exception:
        return 0, "?"


def _count_implemented() -> int:
    try:
        d = json.loads(IDEAS_FILE.read_text(encoding="utf-8"))
        return len(d.get("ideas_completed", []))
    except Exception:
        return 0


def _health_icon(pct: int) -> str:
    if pct >= 80:
        return "🟢"
    if pct >= 50:
        return "🟡"
    return "🔴"


def main() -> int:
    args = sys.argv[1:]
    restore = "--restore" in args

    close_path = _find_latest_close()
    task       = _load_pending_task()
    pct, hlabel = _load_health()
    implemented = _count_implemented()

    print()
    print(_c(BOLD + CYAN, "╔══ BAGO REOPEN — Continuidad de sesión ══════════════════════╗"))

    if close_path is None:
        print(_c(CYAN, "║") + "  Sin cierres de sesión previos encontrados.                 " + _c(CYAN, "║"))
        print(_c(BOLD + CYAN, "╚════════════════════════════════════════════════════════════╝"))
        print()
        print("  → Inicia con: " + _c(CYAN, "bago session"))
        return 0

    close_data = _parse_close(close_path)
    filename   = close_path.name

    print(_c(CYAN, "╠") + _c(DIM, "──────────────────────────────────────────────────────────") + _c(CYAN, "╣"))
    print(_c(CYAN, "║") + f"  {_c(BOLD, 'Último cierre:')}  {_c(DIM, close_data['timestamp'])}")
    print(_c(CYAN, "║") + f"  {_c(BOLD, 'Archivo:')}        {_c(DIM, filename)}")
    print(_c(CYAN, "╠") + _c(DIM, "──────────────────────────────────────────────────────────") + _c(CYAN, "╣"))
    print(_c(CYAN, "║") + f"  {_c(BOLD, 'Tarea completada:')}")
    print(_c(CYAN, "║") + f"    Idea:      {close_data['idea']}")
    print(_c(CYAN, "║") + f"    Workflow:  {_c(DIM, close_data['workflow'])}")
    print(_c(CYAN, "║") + f"    Objetivo:  {close_data['objetivo'][:60]}{'…' if len(close_data['objetivo']) > 60 else ''}")
    print(_c(CYAN, "║") + f"    Métrica:   {_c(DIM, close_data['metrica'][:60])}")
    print(_c(CYAN, "╠") + _c(DIM, "──────────────────────────────────────────────────────────") + _c(CYAN, "╣"))

    # Health block
    icon = _health_icon(pct)
    print(_c(CYAN, "║") + f"  {_c(BOLD, 'Salud del sistema:')}  {icon}  {_c(GREEN, hlabel)}   ·  {implemented} ideas implementadas")

    print(_c(CYAN, "╠") + _c(DIM, "──────────────────────────────────────────────────────────") + _c(CYAN, "╣"))

    # Pending task block
    if task and task.get("status") not in ("done", None) and task.get("idea_title"):
        status = task.get("status", "?")
        title  = task.get("idea_title", "—")
        obj    = task.get("objetivo", "—")
        print(_c(CYAN, "║") + f"  {_c(BOLD + YELLOW, 'Tarea pendiente W2:')}  {_c(YELLOW, title)}  [{status}]")
        print(_c(CYAN, "║") + f"    Objetivo: {obj[:60]}{'…' if len(obj) > 60 else ''}")
        print(_c(CYAN, "║"))
        print(_c(CYAN, "║") + f"  → Continúa con: " + _c(CYAN, "bago task") + "   o cierra con: " + _c(CYAN, "bago task --done"))
    else:
        print(_c(CYAN, "║") + f"  {_c(BOLD, 'Sin tarea pendiente.')}  Listo para iniciar nueva idea.")
        print(_c(CYAN, "║"))
        print(_c(CYAN, "║") + f"  → Próxima idea: " + _c(CYAN, "bago next") + "  o  " + _c(CYAN, "bago ideas"))

    print(_c(BOLD + CYAN, "╚════════════════════════════════════════════════════════════╝"))
    print()

    if restore:
        _do_restore(close_data)

    return 0


def _do_restore(close_data: dict) -> None:
    """Writes last close data back to pending_w2_task.json for quick restoration."""
    if TASK_FILE.exists():
        current = json.loads(TASK_FILE.read_text(encoding="utf-8"))
        if current.get("status") not in ("done", "clear", None):
            print(_c(YELLOW, "  ⚠ Tarea activa en curso — restauración cancelada."))
            print(_c(DIM, "    Usa: bago task --done  para cerrarla primero."))
            return

    ts = datetime.now(timezone.utc).isoformat()
    task_data = {
        "idea_title": close_data.get("idea", "—"),
        "workflow": close_data.get("workflow", "W2"),
        "objetivo": close_data.get("objetivo", "—"),
        "alcance": close_data.get("alcance", "—"),
        "metric": close_data.get("metrica", "—"),
        "status": "in_progress",
        "restored_from": close_data.get("timestamp", "—"),
        "created_at": ts,
        "updated_at": ts,
    }
    TASK_FILE.write_text(json.dumps(task_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(_c(GREEN, "  ✓ Tarea restaurada desde cierre anterior."))
    print(_c(DIM,   f"    Archivo: {TASK_FILE.name}"))
    print(_c(DIM,   "    Consulta: bago task"))


def _self_test() -> None:
    """Autotest — verifica parsing de SESSION_CLOSE y rutas de main()."""
    import tempfile
    from pathlib import Path as _P

    # Test 1: _parse_close on synthetic markdown
    md = """# Cierre de sesión — 2026-05-05T10:00:00+00:00

## Tarea completada

| Campo | Valor |
|-------|-------|
| Idea | #7 — Test idea |
| Workflow | W2_TEST |
| Objetivo | Verificar parseado |
| Alcance | Solo test |
| Métrica | pasa |
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(md)
        tmp_path = _P(f.name)

    try:
        parsed = _parse_close(tmp_path)
        assert parsed["idea"] == "#7 — Test idea", f"idea: {parsed['idea']!r}"
        assert parsed["workflow"] == "W2_TEST", f"workflow: {parsed['workflow']!r}"
        assert parsed["objetivo"] == "Verificar parseado", f"obj: {parsed['objetivo']!r}"
        assert "2026-05-05" in parsed["timestamp"], f"ts: {parsed['timestamp']!r}"
    finally:
        tmp_path.unlink(missing_ok=True)

    # Test 2: _find_latest_close returns None when no sessions dir
    global SESSIONS_DIR
    _orig = SESSIONS_DIR
    SESSIONS_DIR = Path(tempfile.gettempdir()) / "bago_test_empty_sessions_xyz"
    try:
        result = _find_latest_close()
        assert result is None, "expected None for missing dir"
    finally:
        SESSIONS_DIR = _orig

    # Test 3: health icon thresholds
    assert _health_icon(100) == "🟢"
    assert _health_icon(60) == "🟡"
    assert _health_icon(30) == "🔴"

    print("  3/3 tests pasaron")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        raise SystemExit(0)
    raise SystemExit(main())
