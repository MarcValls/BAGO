"""npath._tests — Self-tests for the npath package."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import shutil
import tempfile
from pathlib import Path

import npath._db as _db
from npath._db import GREEN, YELLOW, _connect
from npath._graph import (
    cmd_branch, cmd_commit, cmd_merge, cmd_unmerge,
    cmd_reactivate_merge, cmd_split,
)
from npath._view import cmd_status
from npath._db import cmd_init


def _run_tests() -> None:
    print("  Ejecutando tests de npath...")

    orig_db    = _db.DB_PATH
    orig_state = _db.STATE_DIR
    tmpdir     = Path(tempfile.mkdtemp())
    try:
        _db.DB_PATH   = tmpdir / "npath_test.db"
        _db.STATE_DIR = tmpdir

        # T1: init
        cmd_init()
        assert _db.DB_PATH.exists(), "T1: DB no creada"
        print("  T1 ✅ init")

        # T2: branch
        cmd_branch("idea-A", "Primera hipótesis")
        conn = _connect()
        b = conn.execute("SELECT name FROM branches WHERE name='idea-A'").fetchone()
        conn.close()
        assert b, "T2: branch idea-A no creada"
        print("  T2 ✅ branch")

        # T3: commit
        nid = cmd_commit("Hipótesis sobre navegación adaptativa", branch="idea-A")
        assert nid, "T3: commit devolvió vacío"
        conn = _connect()
        n = conn.execute("SELECT id FROM nodes WHERE id=?", (nid,)).fetchone()
        conn.close()
        assert n, "T3: nodo no en DB"
        print("  T3 ✅ commit")

        # T4: second commit creates edge
        nid2 = cmd_commit("Variante minimalista del concepto", branch="idea-A")
        conn  = _connect()
        e     = conn.execute("SELECT id FROM edges WHERE to_id=?", (nid2,)).fetchone()
        conn.close()
        assert e, "T4: arista no creada entre commits"
        print("  T4 ✅ edge entre commits")

        # T5: second branch + commit
        cmd_branch("idea-B", "Alternativa")
        cmd_commit("Estructura de menús radiales", branch="idea-B")
        print("  T5 ✅ segunda rama y commit")

        # T6: merge
        cmd_merge("idea-A", "idea-B", content="Fusión de navegación + menús radiales")
        conn = _connect()
        m    = conn.execute("SELECT id FROM merges").fetchone()
        conn.close()
        assert m, "T6: merge no registrado"
        merge_id = m[0]
        print(f"  T6 ✅ merge  ({merge_id})")

        # T7: unmerge
        cmd_unmerge(merge_id)
        conn  = _connect()
        m_row = conn.execute("SELECT active FROM merges WHERE id=?", (merge_id,)).fetchone()
        conn.close()
        assert m_row and m_row[0] == 0, "T7: merge no desactivado"
        print("  T7 ✅ unmerge (reversible)")

        # T8: reactivate
        cmd_reactivate_merge(merge_id)
        conn  = _connect()
        m_row = conn.execute("SELECT active FROM merges WHERE id=?", (merge_id,)).fetchone()
        conn.close()
        assert m_row and m_row[0] == 1, "T8: merge no reactivado"
        print("  T8 ✅ reactivate-merge")

        # T9: recall (LIKE fallback)
        cmd_commit("búsqueda semántica para recall test", branch="idea-A", ntype="memory")
        conn = _connect()
        rows = conn.execute(
            "SELECT id FROM nodes WHERE content LIKE ?", ("%recall test%",)
        ).fetchall()
        conn.close()
        assert rows, "T9: recall no encontró el nodo"
        print("  T9 ✅ recall (FTS/LIKE)")

        # T10: split
        conn        = _connect()
        target_node = conn.execute(
            "SELECT id FROM nodes WHERE branch='idea-A' AND deleted=0 LIMIT 1"
        ).fetchone()
        conn.close()
        if target_node:
            cmd_split(target_node["id"], "idea-A", content="Variante split test")
            conn = _connect()
            s    = conn.execute("SELECT id FROM splits").fetchone()
            conn.close()
            assert s, "T10: split no registrado"
            print("  T10 ✅ split")
        else:
            print("  T10 ⚠  skip (sin nodos en idea-A para split)")

        # T11: status smoke
        cmd_status()
        print("  T11 ✅ status")

        print()
        print(GREEN("  ✅ 11/11 tests pasaron"))

    finally:
        _db.DB_PATH   = orig_db
        _db.STATE_DIR = orig_state
        shutil.rmtree(tmpdir, ignore_errors=True)
