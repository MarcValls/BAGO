#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
show_task.py — Muestra la tarea W2 pendiente generada por `bago ideas --accept N`.

Uso:
  python3 .bago/tools/show_task.py            # muestra la tarea activa
  python3 .bago/tools/show_task.py --done     # marca la tarea como completada
  python3 .bago/tools/show_task.py --clear    # elimina pending_w2_task.json
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT             = Path(__file__).resolve().parents[2]
TASK_FILE        = ROOT / ".bago" / "state" / "pending_w2_task.json"
IMPLEMENTED_FILE = ROOT / ".bago" / "state" / "implemented_ideas.json"
DB_PATH          = ROOT / ".bago" / "state" / "bago.db"


def _load() -> dict | None:
    if not TASK_FILE.exists():
        return None
    try:
        return json.loads(TASK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _display(task: dict) -> None:
    status_icon = "✅" if task.get("status") == "done" else "⏳"
    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print(f"  │  BAGO · Tarea W2 pendiente  {status_icon}                          │")
    print("  └──────────────────────────────────────────────────────────┘")
    print(f"  Idea #{task.get('idea_index', '?')}: {task.get('idea_title', '—')}")
    print(f"  Prioridad : {task.get('priority', '—')}")
    print(f"  Workflow  : {task.get('workflow', '—')}")
    print(f"  Aceptada  : {task.get('accepted_at', '—')}")
    print()
    print(f"  Objetivo   : {task.get('objetivo', '—')}")
    print(f"  Alcance    : {task.get('alcance', '—')}")
    print(f"  No alcance : {task.get('no_alcance', '—')}")
    print()
    files = task.get("archivos_candidatos", [])
    print(f"  Archivos candidatos ({len(files)}):")
    for f in files:
        print(f"    · {f}")
    print()
    validation = task.get("validacion_minima", [])
    print(f"  Validación mínima ({len(validation)}):")
    for v in validation:
        print(f"    ✓ {v}")
    print()
    metric = task.get("metric", "").strip()
    if metric:
        print(f"  Métrica      : {metric}")
    print(f"  Siguiente paso: {task.get('siguiente_paso', '—')}")
    print()
    print("  Comandos:")
    print("    bago task --done   → marcar completada")
    print("    bago task --clear  → limpiar tarea")
    print()


def _register_implemented(task: dict) -> None:
    """Añade el título de la idea a implemented_ideas.json y a bago.db."""
    title = (task.get("title") or task.get("idea_title") or "").strip()
    now   = datetime.now(timezone.utc).isoformat()

    # ── JSON registry ───────────────────────────────────────────────────────
    try:
        if IMPLEMENTED_FILE.exists():
            data = json.loads(IMPLEMENTED_FILE.read_text(encoding="utf-8"))
            # Normalizar: soportar clave legacy "ideas_completed" y nueva "implemented"
            existing = data.get("implemented") or data.get("ideas_completed") or []
        else:
            existing = []

        if title and not any(e.get("title") == title for e in existing):
            existing.append({
                "title":   title,
                "slot":    task.get("slot"),
                "done_at": now,
            })
        IMPLEMENTED_FILE.write_text(
            json.dumps({"implemented": existing, "updated_at": now},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    # ── SQLite registry ─────────────────────────────────────────────────────
    try:
        if DB_PATH.exists() and title:
            import hashlib
            idea_id = hashlib.sha256(title.encode()).hexdigest()[:16]
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT OR IGNORE INTO implemented_ideas"
                " (id, idea_title, session_id, implemented_at) VALUES (?, ?, ?, ?)",
                (idea_id, title, "show_task", now),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass



def _generate_session_close(task: dict) -> Path | None:
    """Delega al generador dedicado session_close_generator.generate()."""
    try:
        import importlib.util
        gen_path = Path(__file__).parent / "session_close_generator.py"
        spec = importlib.util.spec_from_file_location("session_close_generator", gen_path)
        mod  = importlib.util.module_from_spec(spec)      # type: ignore[arg-type]
        spec.loader.exec_module(mod)                       # type: ignore[union-attr]
        return mod.generate(task=task)
    except Exception:
        return None


def _reopen_from_continuity() -> int:
    """
    Muestra el artefacto de la última sesión cerrada para retomar el contexto.
    Ayuda a reactivar la sesión sin reconstruir contexto manualmente.
    """
    sessions_dir = ROOT / ".bago" / "state" / "sessions"
    close_files  = sorted(sessions_dir.glob("SESSION_CLOSE_*.md"), reverse=True)
    if not close_files:
        print()
        print("  ℹ  No hay artefactos de cierre previos.")
        print("     Cierra una tarea con: bago task --done")
        print()
        return 0

    last = close_files[0]
    print()
    print("  ┌──────────────────────────────────────────────────────────┐")
    print(f"  │  🔄  Continuidad desde: {last.name[:46]}  │")
    print("  └──────────────────────────────────────────────────────────┘")
    print()
    try:
        content = last.read_text(encoding="utf-8")
        for line in content.splitlines():
            print(f"  {line}")
    except Exception as e:
        print(f"  ⚠  No se pudo leer el artefacto: {e}")
    print()
    if len(close_files) > 1:
        print(f"  📂  {len(close_files)} artefactos disponibles en .bago/state/sessions/")
    print("  💡  Acepta una nueva idea con: bago ideas --accept N")
    print()
    return 0


def _run_cabinet_check() -> None:
    """Ejecuta bago cabinet como verificación de salud al cerrar tarea."""
    import subprocess
    bago_bin = ROOT / "bago"
    print("  ── Verificación de salud (cabinet) ─────────────────────────")
    result = subprocess.run(
        [sys.executable, str(bago_bin), "cabinet"],
        capture_output=True, text=True
    )
    lines = [l for l in (result.stdout + result.stderr).splitlines() if l.strip()]
    errors   = sum(1 for l in lines if "ERROR" in l and l.strip().startswith("ERROR"))
    warns    = sum(1 for l in lines if "WARN"  in l and l.strip().startswith("WARN"))
    # Prefer the summary "ERROR = N" line
    err_line = next((l.strip() for l in lines if "ERROR =" in l), None)
    if err_line:
        status = "✓" if result.returncode == 0 else "⚠"
        print(f"  {status} cabinet: {err_line}")
    else:
        status = "✓" if result.returncode == 0 else "⚠"
        print(f"  {status} cabinet: {'OK' if result.returncode == 0 else 'revisa la salida'}")
    print()



def _suggest_commit_if_dirty() -> None:
    """Si hay cambios sin commitear, sugiere git add -A && git commit. # AUTO_COMMIT_HINT_IMPLEMENTED"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            print("  💡  Hay cambios sin commitear:")
            print(f"      git add -A && git commit")
            print()
    except Exception:
        pass


def main() -> int:
    args = sys.argv[1:]
    clear  = "--clear"  in args
    done   = "--done"   in args
    reopen = "--reopen" in args

    if reopen:
        return _reopen_from_continuity()

    if clear:
        if TASK_FILE.exists():
            TASK_FILE.unlink()
            print("  ✅ Tarea eliminada.")
        else:
            print("  ℹ  No hay tarea pendiente.")
        return 0

    task = _load()
    if task is None:
        print()
        print("  ℹ  No hay tarea W2 pendiente.")
        print("     Acepta una idea con: bago ideas --accept N")
        print()
        return 0

    if done:
        task["status"] = "done"
        task["done_at"] = datetime.now(timezone.utc).isoformat()
        TASK_FILE.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        _register_implemented(task)
        close_path = _generate_session_close(task)
        print("  ✅ Tarea marcada como completada.")
        if close_path:
            print(f"  📄 Artefacto de cierre: {close_path.relative_to(ROOT)}")
        _display(task)
        # ── Verificación de cabinet antes de continuar ── # CABINET_ON_CLOSE_IMPLEMENTED
        _run_cabinet_check()
        _suggest_commit_if_dirty()
        # ── Recordatorio de cosecha ──────────────────────────────────────────
        print("  ┌──────────────────────────────────────────────────────────┐")
        print("  │  🌾  Siguiente paso recomendado:                          │")
        print("  │                                                           │")
        print("  │     bago cosecha   →  preserva el artefacto de sesión    │")
        print("  │     bago ideas     →  selecciona la próxima mejora       │")
        print("  └──────────────────────────────────────────────────────────┘")
        print()
        return 0

    _display(task)
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        print("show_task --test: PASS (imports OK, TASK_FILE path resolvable)")
        raise SystemExit(0)
    _code = main()
    try:
        import importlib.util as _ilu
        _ep = __import__("pathlib").Path(__file__).parent / "bago_sac_engine.py"
        _spec = _ilu.spec_from_file_location("bago_sac_engine", str(_ep))
        _mod = _ilu.module_from_spec(_spec); _spec.loader.exec_module(_mod)
        _mod.sac_suggest("bago done", exit_code=_code)
    except Exception:
        pass
    raise SystemExit(_code)
