"""npath._graph — Branch, commit, merge, split, activate operations."""
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

import json
from typing import Optional

from npath._db import (
    _connect, _now, _short_id, _node_id, _merge_id, _split_id,
    _get_current_branch, _set_current_branch,
    BOLD, GREEN, CYAN, YELLOW, RED, DIM,
)
from npath._bus import _neural_bus_emit


# ── Branch ─────────────────────────────────────────────────────────────────────

def cmd_branch(name: str, description: str = "") -> None:
    """Create a new cognitive trajectory branch."""
    conn = _connect()
    with conn:
        existing = conn.execute("SELECT name FROM branches WHERE name=?", (name,)).fetchone()
        if existing:
            print(YELLOW(f"⚠  La rama '{name}' ya existe."))
            _set_current_branch(conn, name)
            print(f"   Ahora en: {CYAN(name)}")
            conn.close()
            return
        conn.execute(
            "INSERT INTO branches (name, active, description, created_at) VALUES (?,1,?,?)",
            (name, description, _now()),
        )
        _set_current_branch(conn, name)
    conn.close()
    print(GREEN(f"✅ Rama creada: {BOLD(name)}"))
    if description:
        print(f"   {DIM(description)}")
    print(f"   Ahora en: {CYAN(name)}")
    _neural_bus_emit("npath.branch_created", {"branch": name, "description": description})


def cmd_branches() -> None:
    """List all branches."""
    conn = _connect()
    rows = conn.execute(
        "SELECT name, head_node, active, description, created_at FROM branches ORDER BY created_at"
    ).fetchall()
    current = _get_current_branch(conn)
    conn.close()

    if not rows:
        print("  No hay ramas. Ejecuta: bago npath init")
        return

    print()
    print(f"  {'✦':1}  {'Rama':<28}  {'Nodos':>6}  {'Descripción'}")
    print("  " + "─" * 72)
    conn2 = _connect()
    for r in rows:
        active_mark  = GREEN("●") if r["active"] else DIM("○")
        current_mark = " ◀" if r["name"] == current else ""
        count = conn2.execute(
            "SELECT COUNT(*) FROM nodes WHERE branch=? AND deleted=0", (r["name"],)
        ).fetchone()[0]
        desc = (r["description"] or "")[:40]
        print(f"  {active_mark}  {r['name']:<28}  {count:>6}  {DIM(desc)}{CYAN(current_mark)}")
    conn2.close()
    print()


# ── Commit ─────────────────────────────────────────────────────────────────────

def cmd_commit(
    content: str,
    branch: Optional[str] = None,
    ntype: str = "concept",
    weight: float = 0.5,
    metadata: Optional[dict] = None,
) -> str:
    """Add a node (commit) to a branch. Returns node id."""
    conn = _connect()
    current = branch or _get_current_branch(conn)

    existing = conn.execute("SELECT head_node FROM branches WHERE name=?", (current,)).fetchone()
    if not existing:
        print(YELLOW(f"⚠  La rama '{current}' no existe. Créala con: bago npath branch {current}"))
        conn.close()
        return ""

    nid       = _node_id(current, content)
    prev_head = existing["head_node"]
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    with conn:
        conn.execute(
            "INSERT INTO nodes (id, branch, content, type, weight, active, deleted, created_at, metadata)"
            " VALUES (?,?,?,?,?,1,0,?,?)",
            (nid, current, content, ntype, weight, _now(), meta_json),
        )
        if prev_head:
            eid = f"e_{_short_id()}"
            conn.execute(
                "INSERT INTO edges (id, from_id, to_id, relation, weight, active, created_at)"
                " VALUES (?,?,?,'follows',1.0,1,?)",
                (eid, prev_head, nid, _now()),
            )
        conn.execute("UPDATE branches SET head_node=? WHERE name=?", (nid, current))

    conn.close()
    print(GREEN(f"✅ [{current}]") + f"  {BOLD(nid)}")
    print(f"   {DIM(content[:80])}")
    print(f"   type={CYAN(ntype)}  weight={weight:.2f}")
    _neural_bus_emit("npath.node_created", {
        "node_id": nid, "branch": current,
        "content": content[:200], "type": ntype, "weight": weight,
    })
    return nid


# ── Merge ──────────────────────────────────────────────────────────────────────

def cmd_merge(
    branch1: str,
    branch2: str,
    content: Optional[str] = None,
    strategy: str = "manual",
) -> None:
    """Merge two branches into a synthesis node."""
    conn = _connect()
    b1 = conn.execute("SELECT head_node FROM branches WHERE name=?", (branch1,)).fetchone()
    b2 = conn.execute("SELECT head_node FROM branches WHERE name=?", (branch2,)).fetchone()
    if not b1:
        print(RED(f"❌ Rama '{branch1}' no encontrada."))
        conn.close(); return
    if not b2:
        print(RED(f"❌ Rama '{branch2}' no encontrada."))
        conn.close(); return

    merge_content = content or f"Merge de '{branch1}' + '{branch2}'"
    merge_branch  = f"merge-{branch1[:8]}-{branch2[:8]}"

    existing_mb = conn.execute("SELECT name FROM branches WHERE name=?", (merge_branch,)).fetchone()
    with conn:
        if not existing_mb:
            conn.execute(
                "INSERT INTO branches (name, active, description, created_at) VALUES (?,1,?,?)",
                (merge_branch, f"Fusión de {branch1} + {branch2}", _now()),
            )

    nid = _node_id(merge_branch, merge_content)
    mid = _merge_id()

    with conn:
        conn.execute(
            "INSERT INTO nodes (id, branch, content, type, weight, active, deleted, created_at, metadata)"
            " VALUES (?,?,?,'merge',0.8,1,0,?,?)",
            (nid, merge_branch, merge_content, _now(), json.dumps({
                "merged_from": [branch1, branch2],
                "strategy": strategy,
                "merge_id": mid,
            })),
        )
        for parent_id in [b1["head_node"], b2["head_node"]]:
            if parent_id:
                conn.execute(
                    "INSERT INTO edges (id, from_id, to_id, relation, weight, active, created_at)"
                    " VALUES (?,?,?,'merges',1.0,1,?)",
                    (f"e_{_short_id()}", parent_id, nid, _now()),
                )
        conn.execute("UPDATE branches SET head_node=? WHERE name=?", (nid, merge_branch))
        conn.execute(
            "INSERT INTO merges (id, sources, result_node, strategy, active, created_at)"
            " VALUES (?,?,?,?,1,?)",
            (mid, json.dumps([branch1, branch2]), nid, strategy, _now()),
        )
        _set_current_branch(conn, merge_branch)

    conn.close()
    print(GREEN(f"✅ Merge completado"))
    print(f"   {CYAN(branch1)} + {CYAN(branch2)}  →  {BOLD(merge_branch)}")
    print(f"   Nodo: {BOLD(nid)}  (merge_id: {mid})")
    print(f"   Ahora en: {CYAN(merge_branch)}")
    _neural_bus_emit("npath.merge", {
        "merge_id": mid, "sources": [branch1, branch2],
        "result_branch": merge_branch, "result_node": nid, "strategy": strategy,
    })


# ── Unmerge / Reactivate ───────────────────────────────────────────────────────

def cmd_unmerge(merge_id: str) -> None:
    """Deactivate a merge (reversible — history is preserved)."""
    conn = _connect()
    row = conn.execute("SELECT * FROM merges WHERE id=?", (merge_id,)).fetchone()
    if not row:
        print(RED(f"❌ Merge '{merge_id}' no encontrado."))
        conn.close(); return
    if not row["active"]:
        print(YELLOW(f"⚠  Merge '{merge_id}' ya está inactivo."))
        conn.close(); return
    with conn:
        conn.execute("UPDATE merges SET active=0 WHERE id=?", (merge_id,))
        conn.execute("UPDATE nodes SET active=0 WHERE id=?", (row["result_node"],))
        conn.execute("UPDATE edges SET active=0 WHERE to_id=?", (row["result_node"],))
    conn.close()
    sources = json.loads(row["sources"])
    print(GREEN(f"✅ Merge '{merge_id}' desactivado (reversible)"))
    print(f"   Ramas fuente: {', '.join(CYAN(s) for s in sources)}")
    print(f"   Para reactivar: bago npath reactivate-merge {merge_id}")


def cmd_reactivate_merge(merge_id: str) -> None:
    """Reactivate a previously deactivated merge."""
    conn = _connect()
    row = conn.execute("SELECT * FROM merges WHERE id=?", (merge_id,)).fetchone()
    if not row:
        print(RED(f"❌ Merge '{merge_id}' no encontrado."))
        conn.close(); return
    with conn:
        conn.execute("UPDATE merges SET active=1 WHERE id=?", (merge_id,))
        conn.execute("UPDATE nodes SET active=1 WHERE id=?", (row["result_node"],))
        conn.execute("UPDATE edges SET active=1 WHERE to_id=?", (row["result_node"],))
    conn.close()
    print(GREEN(f"✅ Merge '{merge_id}' reactivado"))


# ── Split ──────────────────────────────────────────────────────────────────────

def cmd_split(node_id: str, remove_branch: str, content: Optional[str] = None) -> None:
    """Create C' = C without the influence of remove_branch (C - B → C')."""
    conn = _connect()
    node = conn.execute("SELECT * FROM nodes WHERE id=? AND deleted=0", (node_id,)).fetchone()
    if not node:
        print(RED(f"❌ Nodo '{node_id}' no encontrado."))
        conn.close(); return

    removed_edges = conn.execute(
        """SELECT e.id, e.from_id FROM edges e
           JOIN nodes n ON n.id = e.from_id
           WHERE e.to_id=? AND n.branch=? AND e.active=1""",
        (node_id, remove_branch),
    ).fetchall()

    new_content = content or f"{node['content']} (sin {remove_branch})"
    new_branch  = node["branch"]
    new_id      = _node_id(new_branch, new_content)
    split_id    = _split_id()

    all_parents = conn.execute(
        "SELECT from_id FROM edges WHERE to_id=? AND active=1", (node_id,)
    ).fetchall()
    removed_ids  = {r["from_id"] for r in removed_edges}
    kept_parents = [r["from_id"] for r in all_parents if r["from_id"] not in removed_ids]

    meta = json.loads(node["metadata"])
    meta["split_from"]     = node_id
    meta["removed_branch"] = remove_branch
    meta["split_id"]       = split_id

    with conn:
        conn.execute(
            "INSERT INTO nodes (id, branch, content, type, weight, active, deleted, created_at, metadata)"
            " VALUES (?,?,?,?,?,1,0,?,?)",
            (new_id, new_branch, new_content, node["type"], node["weight"], _now(), json.dumps(meta)),
        )
        for parent_id in kept_parents:
            conn.execute(
                "INSERT INTO edges (id, from_id, to_id, relation, weight, active, created_at)"
                " VALUES (?,?,?,'splits',1.0,1,?)",
                (f"e_{_short_id()}", parent_id, new_id, _now()),
            )
        conn.execute(
            "INSERT INTO splits (id, origin_node, removed_branch, result_node, active, created_at)"
            " VALUES (?,?,?,?,1,?)",
            (split_id, node_id, remove_branch, new_id, _now()),
        )
    conn.close()
    print(GREEN(f"✅ Split creado"))
    print(f"   Original: {CYAN(node_id)}  →  Nuevo: {BOLD(new_id)}")
    print(f"   Influencia eliminada de: {YELLOW(remove_branch)}")
    print(f"   Padres conservados: {len(kept_parents)}  |  Eliminados: {len(removed_ids)}")
    _neural_bus_emit("npath.split", {
        "split_id": split_id, "origin_node": node_id,
        "removed_branch": remove_branch, "result_node": new_id,
    })


# ── Activate / Deactivate ──────────────────────────────────────────────────────

def cmd_activate(branch: str, weight: Optional[float] = None) -> None:
    """Activate a branch and optionally set its node weights."""
    conn = _connect()
    row = conn.execute("SELECT name FROM branches WHERE name=?", (branch,)).fetchone()
    if not row:
        print(RED(f"❌ Rama '{branch}' no encontrada."))
        conn.close(); return
    with conn:
        conn.execute("UPDATE branches SET active=1 WHERE name=?", (branch,))
        if weight is not None:
            conn.execute(
                "UPDATE nodes SET weight=? WHERE branch=? AND deleted=0", (weight, branch)
            )
        _set_current_branch(conn, branch)
    conn.close()
    w_msg = f"  weight={weight:.2f}" if weight is not None else ""
    print(GREEN(f"✅ Rama '{branch}' activada{w_msg}"))
    print(f"   Ahora en: {CYAN(branch)}")
    _neural_bus_emit("npath.branch_switched", {"branch": branch, "weight": weight})


def cmd_deactivate(branch: str) -> None:
    """Deactivate a branch (nodes remain, just marked inactive)."""
    conn = _connect()
    with conn:
        conn.execute("UPDATE branches SET active=0 WHERE name=?", (branch,))
    conn.close()
    print(YELLOW(f"○  Rama '{branch}' desactivada (historia preservada)"))



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
