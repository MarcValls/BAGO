#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session_close_generator.py — Genera el artefacto de cierre de sesión.

Se llama automáticamente desde show_task.py --done.
También puede invocarse de forma independiente:

  python3 .bago/tools/session_close_generator.py [--task-file PATH] [--out PATH]

El artefacto se escribe en:
  .bago/state/sessions/SESSION_CLOSE_<YYYYMMDD_HHMMSS>.md
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT          = Path(__file__).resolve().parents[3]
STATE_DIR     = ROOT / ".bago" / "state"
SESSIONS_DIR  = STATE_DIR / "sessions"
CHANGES_DIR   = STATE_DIR / "changes"
EVIDENCES_DIR = STATE_DIR / "evidences"
TASK_FILE     = STATE_DIR / "pending_w2_task.json"
TASK_ARCHIVE  = STATE_DIR / "archive" / "pending_w2_task"
IDEAS_FILE    = STATE_DIR / "implemented_ideas.json"
GLOBAL_STATE  = STATE_DIR / "global_state.json"


def _load_last_completed_workflow() -> dict:
    """Lee global_state.sprint_status.last_completed_workflow.

    Retorna {} si no existe / no se puede leer / no es dict.
    # COSECHA_SESSION_CLOSE_USES_LAST_COMPLETED
    """
    if not GLOBAL_STATE.exists():
        return {}
    try:
        gs = json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}
    sprint = gs.get("sprint_status") or {}
    last = sprint.get("last_completed_workflow") or {}
    return last if isinstance(last, dict) else {}


def _enrich_task_with_last_completed(task: dict) -> dict:
    """Si la task está vacía o describe una idea distinta al último flow
    cerrado, enriquece con datos de last_completed_workflow.

    Reglas:
      · Si task vacía → sintetiza una task mínima desde last_completed.
      · Si task tiene idea_title pero NO contiene el title del last_completed
        (ni viceversa) Y last_completed es más reciente que task.accepted_at
        → reemplaza idea_title/workflow con los del last_completed (la idea
        original quedó en otro contexto).
      · En cualquier otro caso → task tal cual (task gana).
    # COSECHA_SESSION_CLOSE_USES_LAST_COMPLETED
    """
    last = _load_last_completed_workflow()
    if not last:
        return task or {}
    last_title = (last.get("title") or "").strip()
    last_code  = (last.get("code")  or "").strip()
    last_ended = last.get("ended")

    # Caso A: sin task
    if not task:
        return {
            "idea_title": last_title or "—",
            "idea_index": "—",
            "workflow":   last_code or "—",
            "objetivo":   f"Cierre del workflow {last_code} ({last_title}).",
            "alcance":    "—",
            "metric":     "—",
            "_source":    "last_completed_workflow",
        }

    # Caso B: task existe pero no encaja con last_completed
    task_title = (task.get("idea_title") or task.get("title") or "").strip()
    if task_title and last_title:
        a = task_title.lower()
        b = last_title.lower()
        encaja = (a in b) or (b in a)
        if not encaja:
            # last_completed es más reciente → reemplaza
            try:
                accepted = task.get("accepted_at") or ""
                if last_ended and accepted and last_ended > accepted:
                    enriched = dict(task)
                    enriched["idea_title"] = last_title
                    enriched["workflow"]   = last_code or task.get("workflow", "—")
                    enriched["_source"]    = "last_completed_workflow (override)"
                    return enriched
            except Exception:
                pass
    return task


def _archive_pending_task_if_done(task_file: Path, task: dict | list | None) -> Path | None:
    """Si la task tiene status='done', muévela al archivo y elimina el original.

    # COSECHA_W10_DESYNC_DETECTOR (cierra el bucle: la idea
    #  session_close_clears_pending_task ataca exactamente este flujo).

    Retorna la ruta de archivo (o None si no se hizo nada).
    """
    if not isinstance(task, dict):
        return None
    status = (task.get("status") or "").lower()
    if status != "done":
        return None
    if not task_file.exists():
        return None
    TASK_ARCHIVE.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archived = TASK_ARCHIVE / f"pending_w2_task_{ts}.json"
    # copia (no movimiento bruto) para preservar permisos y atomicidad
    archived.write_text(task_file.read_text(encoding="utf-8"), encoding="utf-8")
    task_file.unlink()
    return archived


def _resolve_sessions_dir() -> Path:
    """Devuelve el directorio de sesiones correcto.

    Si hay un proyecto vinculado en global_state.json → guarda en el proyecto.
    Si no → guarda en el framework (comportamiento clásico).
    """
    try:
        gs = json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))
        cp = gs.get("current_project", {})
        root = cp.get("root")
        if root:
            project_sessions = Path(root) / ".bago" / "state" / "sessions"
            project_sessions.mkdir(parents=True, exist_ok=True)
            return project_sessions
    except Exception:
        pass
    return SESSIONS_DIR


def _load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _count_dir(path: Path, pattern: str = "*.json") -> int:
    if not path.exists():
        return 0
    return len(list(path.glob(pattern)))


def _register_idea_done(task: dict, session_close_file: str) -> None:
    """Append the completed task/idea to implemented_ideas.json and bago.db."""
    data: dict = _load_json(IDEAS_FILE) or {}
    if not isinstance(data, dict):
        data = {}
    completed: list = data.get("ideas_completed", [])
    if not isinstance(completed, list):
        completed = []

    idea_id    = task.get("idea_id") or task.get("id") or ""
    idea_title = task.get("idea_title") or task.get("title") or "—"

    # Avoid duplicate registrations
    existing_ids   = {e.get("id") for e in completed if e.get("id")}
    existing_titles = {e.get("title") for e in completed if e.get("title")}
    if idea_id and idea_id in existing_ids:
        return
    if idea_title != "—" and idea_title in existing_titles and not idea_id:
        return

    entry = {
        "id":            idea_id or None,
        "title":         idea_title,
        "date":          datetime.now(timezone.utc).isoformat(),
        "session_close": session_close_file,
        "workflow":      task.get("workflow", "—"),
        "objetivo":      task.get("objetivo", "—"),
    }
    completed.append(entry)
    data["ideas_completed"] = completed
    data["last_updated"]    = datetime.now(timezone.utc).isoformat()

    try:
        IDEAS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # Never break close flow over this

    # Sync to bago.db implemented_ideas table
    try:
        import hashlib
        import sqlite3
        db_path = STATE_DIR / "bago.db"
        if db_path.exists() and idea_title != "—":
            idea_db_id = hashlib.sha256(idea_title.encode()).hexdigest()[:16]
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "INSERT OR IGNORE INTO implemented_ideas (id, idea_title, session_id, implemented_at)"
                " VALUES (?,?,?,?)",
                (idea_db_id, idea_title, "session_close", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
    except Exception:
        pass  # Never break close flow over this


def _find_existing_session_close(sessions_dir: Path) -> Path | None:
    """Busca un SESSION_CLOSE existente para la sesión o día actual.

    Prioridad:
      1. SESSION_CLOSE vinculado al active_session_id en global_state
      2. SESSION_CLOSE creado hoy (mismo prefijo de fecha YYYYMMDD)

    Si existe → devuelve la ruta para actualizar en lugar de crear nuevo.
    Si no existe → devuelve None (crear nuevo).
    """
    today = datetime.now(timezone.utc).strftime("%Y%m%d")

    # Prioridad 1: sesión activa explícita
    try:
        gs = json.loads(GLOBAL_STATE.read_text(encoding="utf-8"))
        active_id = gs.get("active_session_id")
        if active_id:
            candidate = sessions_dir / f"SESSION_CLOSE_{active_id}.md"
            if candidate.exists():
                return candidate
    except Exception:
        pass

    # Prioridad 2: mismo día calendario
    existing = sorted(sessions_dir.glob(f"SESSION_CLOSE_{today}_*.md"))
    if existing:
        return existing[-1]  # el más reciente del día

    return None


def generate(task: dict | None = None, out_path: Path | None = None) -> Path:
    """Genera o actualiza el artefacto de cierre y devuelve su ruta.

    Deduplicación: si ya existe un SESSION_CLOSE para la sesión activa o
    para el día actual, actualiza ese archivo en lugar de crear uno nuevo.
    Esto evita la acumulación patológica de N archivos por día cuando se
    llama desde 'bago task --done' repetidamente.
    """
    # Project-aware sessions dir
    sessions_dir = _resolve_sessions_dir()
    sessions_dir.mkdir(parents=True, exist_ok=True)

    now     = datetime.now(timezone.utc)
    ts      = now.strftime("%Y%m%d_%H%M%S")
    ts_iso  = now.isoformat()

    if task is None:
        task = _load_json(TASK_FILE) or {}

    # Enriquecer con last_completed_workflow cuando proceda.
    # # COSECHA_SESSION_CLOSE_USES_LAST_COMPLETED
    task = _enrich_task_with_last_completed(task)

    idea_title = task.get("idea_title", "—")
    idea_index = task.get("idea_index", "?")
    objetivo   = task.get("objetivo", "—")
    alcance    = task.get("alcance", "—")
    workflow   = task.get("workflow", "—")
    metric     = task.get("metric", "—").strip() if task.get("metric") else "—"

    # Contar artefactos de estado
    n_changes   = _count_dir(CHANGES_DIR)
    n_evidences = _count_dir(EVIDENCES_DIR)

    # Últimos 5 cambios
    changes_block = ""
    if CHANGES_DIR.exists():
        files = sorted(CHANGES_DIR.glob("*.json"), reverse=True)[:5]
        lines = []
        for f in files:
            data = _load_json(f) or {}
            chg_id  = data.get("id", f.stem)
            summary = data.get("summary", data.get("description", "—"))
            lines.append(f"- **{chg_id}**: {summary}")
        if lines:
            changes_block = "\n".join(lines)

    if not changes_block:
        changes_block = "_Sin cambios registrados en este cierre._"

    content = f"""# Cierre de sesión — {ts_iso}

## Tarea completada

| Campo | Valor |
|-------|-------|
| Idea | #{idea_index} — {idea_title} |
| Workflow | {workflow} |
| Objetivo | {objetivo} |
| Alcance | {alcance} |
| Métrica | {metric} |

## Resumen de cambios ({n_changes} total)

{changes_block}

## Evidencias acumuladas

{n_evidences} evidencias registradas en `.bago/state/evidences/`.

## Estado del sistema al cierre

| Métrica | Valor |
|---------|-------|
| Cambios totales | {n_changes} |
| Evidencias totales | {n_evidences} |
| Timestamp cierre | {ts_iso} |

---
_Generado automáticamente por `session_close_generator.py`_
"""

    if out_path is None:
        existing = _find_existing_session_close(sessions_dir)
        if existing:
            out_path = existing  # actualiza el artefacto del día/sesión actual
        else:
            out_path = sessions_dir / f"SESSION_CLOSE_{ts}.md"

    out_path.write_text(content, encoding="utf-8")
    _register_idea_done(task, out_path.name)
    return out_path


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)

    task_file = TASK_FILE
    out_path  = None

    i = 0
    while i < len(args):
        if args[i] == "--task-file" and i + 1 < len(args):
            task_file = Path(args[i + 1])
            i += 2
        elif args[i] == "--out" and i + 1 < len(args):
            out_path = Path(args[i + 1])
            i += 2
        else:
            i += 1

    task = _load_json(task_file) if task_file.exists() else {}
    result = generate(task=task, out_path=out_path)
    print(f"  📄 Artefacto de cierre generado: {result.relative_to(ROOT)}")
    # Limpieza: si la task está done, archivarla para que session open
    # siguiente arranque limpio (cierra desync W10 task-done ↔ flow-activo).
    archived = _archive_pending_task_if_done(task_file, task)
    if archived:
        try:
            rel = archived.relative_to(ROOT)
        except ValueError:
            rel = archived
        print(f"  🗄️  Task done archivada: {rel}")
    return 0



def _self_test():
    """Autotest — verifica generate() y registro de idea en implemented_ideas.json."""
    import tempfile
    from pathlib import Path as _P

    assert _P(__file__).exists(), "fichero no encontrado"

    with tempfile.TemporaryDirectory() as tmp:
        tmp_ideas = _P(tmp) / "implemented_ideas.json"

        task = {
            "idea_id": "test-idea-001",
            "idea_title": "Test idea",
            "idea_index": 1,
            "objetivo": "Verificar cierre",
            "alcance": "Solo test",
            "workflow": "W2",
            "metric": "artefacto generado",
        }
        out = _P(tmp) / "close.md"

        # Temporarily patch IDEAS_FILE and STATE_DIR so DB sync uses temp dir
        global IDEAS_FILE, STATE_DIR
        _orig = IDEAS_FILE
        _orig_state = STATE_DIR
        IDEAS_FILE = tmp_ideas
        STATE_DIR  = _P(tmp)
        try:
            # Test 1: generate() produces a file
            result = generate(task=task, out_path=out)
            assert result.exists(), "artefacto no generado"

            # Test 2: implemented_ideas.json updated
            assert tmp_ideas.exists(), "implemented_ideas.json no creado"
            data = json.loads(tmp_ideas.read_text())
            completed = data.get("ideas_completed", [])
            assert len(completed) == 1, f"esperado 1 entrada, got {len(completed)}"
            assert completed[0]["id"] == "test-idea-001", "id incorrecto"

            # Test 3: duplicate registration is skipped
            generate(task=task, out_path=_P(tmp) / "close2.md")
            data2 = json.loads(tmp_ideas.read_text())
            assert len(data2.get("ideas_completed", [])) == 1, "duplicado registrado"

            # Test 4: _archive_pending_task_if_done con task done → archiva y borra
            global TASK_ARCHIVE
            _orig_archive = TASK_ARCHIVE
            TASK_ARCHIVE = _P(tmp) / "archive" / "pending_w2_task"
            try:
                tf = _P(tmp) / "pending_w2_task.json"
                tf.write_text(json.dumps({"status": "done", "idea_title": "X"}))
                archived = _archive_pending_task_if_done(tf, {"status": "done"})
                assert archived is not None and archived.exists(), "no archivado"
                assert not tf.exists(), "task original no eliminada"

                # Test 5: _archive_pending_task_if_done con status != done → no-op
                tf.write_text(json.dumps({"status": "pending"}))
                res = _archive_pending_task_if_done(tf, {"status": "pending"})
                assert res is None, "no debe archivar pending"
                assert tf.exists(), "no debe borrar pending"

                # Test 6: con None / no-dict → no-op
                assert _archive_pending_task_if_done(tf, None) is None
                assert _archive_pending_task_if_done(tf, "string") is None
            finally:
                TASK_ARCHIVE = _orig_archive
        finally:
            IDEAS_FILE = _orig
            STATE_DIR  = _orig_state

    print("  3/3 base + 3/3 archivado + 4/4 enrich-last-completed tests pasaron")


def _test_enrich_last_completed():
    """Tests del enriquecimiento con last_completed_workflow.
    # COSECHA_SESSION_CLOSE_USES_LAST_COMPLETED
    """
    import tempfile
    from pathlib import Path as _P
    fails: list[str] = []
    global GLOBAL_STATE
    saved = GLOBAL_STATE
    try:
        with tempfile.TemporaryDirectory() as td:
            gs_path = _P(td) / "global_state.json"
            GLOBAL_STATE = gs_path

            # Caso 1: sin global_state → task se devuelve tal cual
            t = {"idea_title": "X", "workflow": "W2"}
            r = _enrich_task_with_last_completed(t)
            if r != t:
                fails.append(f"sin gs debería devolver task; got {r!r}")

            # Caso 2: task vacía + last_completed presente → sintetiza
            gs_path.write_text(json.dumps({
                "sprint_status": {"last_completed_workflow": {
                    "code": "W2", "title": "feat XYZ",
                    "started": "2026-05-07T10:00:00+00:00",
                    "ended":   "2026-05-07T10:30:00+00:00",
                }}
            }))
            r = _enrich_task_with_last_completed({})
            if r.get("idea_title") != "feat XYZ" or r.get("workflow") != "W2":
                fails.append(f"task vacía no sintetizada: {r}")
            if r.get("_source") != "last_completed_workflow":
                fails.append("sintetizada no marca _source")

            # Caso 3: task encaja con last_completed (substring) → sin override
            t = {
                "idea_title": "feat XYZ",
                "workflow": "W2",
                "accepted_at": "2026-05-07T09:00:00+00:00",
            }
            r = _enrich_task_with_last_completed(t)
            if r.get("_source") == "last_completed_workflow (override)":
                fails.append("task que encaja no debe override")

            # Caso 4: task no encaja Y last_completed es más reciente → override
            t = {
                "idea_title": "OTRA cosa",
                "workflow": "W2",
                "accepted_at": "2026-05-07T09:00:00+00:00",
            }
            r = _enrich_task_with_last_completed(t)
            if r.get("idea_title") != "feat XYZ":
                fails.append(f"override no aplicado: {r.get('idea_title')}")
            if r.get("_source") != "last_completed_workflow (override)":
                fails.append(f"override no marca _source: {r.get('_source')}")
    finally:
        GLOBAL_STATE = saved
    if fails:
        for f in fails: print("  FAIL:", f)
        raise SystemExit(f"FAIL: {len(fails)}/4 enrich tests")


if __name__ == "__main__":
    if "--test" in sys.argv:
        _self_test()
        _test_enrich_last_completed()
        raise SystemExit(0)
    raise SystemExit(main())
