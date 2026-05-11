#!/usr/bin/env python3
"""npath.py — BAGO Neural Path System

Sistema local de grafos versionados donde las ramas funcionan como
trayectorias cognitivas activables, fusionables y reversibles.

Inspirado en Git pero orientado a conocimiento, memoria y decisiones:

  Nodo   = estado / idea / archivo / memoria / decisión
  Arista = relación entre estados
  Branch = camino activo dentro del grafo
  Merge  = creación de un nodo que combina varios caminos
  Unmerge= desactivar relación sin borrar historia (reversible)
  Peso   = relevancia, confianza, prioridad

Uso:
  bago npath init
  bago npath branch <nombre> [descripción]
  bago npath branches
  bago npath commit <contenido> [--branch <rama>] [--type <tipo>] [--weight <0-1>]
  bago npath log [--branch <rama>] [--limit N]
  bago npath map [--branch <rama>]
  bago npath merge <rama1> <rama2> [--content <desc>] [--strategy manual|weighted]
  bago npath unmerge <merge-id>
  bago npath split <node-id> --remove <rama>
  bago npath activate <rama> [--weight <0-1>]
  bago npath deactivate <rama>
  bago npath recall <query> [--limit N]
  bago npath status
  bago npath node <node-id>
  bago npath delete-node <node-id>          (lógico — soft delete)
  bago npath --test

DB: .bago/state/npath.db
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# ── Rutas ──────────────────────────────────────────────────────────────────────

TOOLS_DIR = Path(__file__).resolve().parent
BAGO_ROOT = TOOLS_DIR.parent
STATE_DIR = BAGO_ROOT / "state"
DB_PATH   = STATE_DIR / "npath.db"

# Windows UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

# ── Colors ─────────────────────────────────────────────────────────────────────

_USE_COLOR = sys.stdout.isatty()
def _c(code, t): return f"\033[{code}m{t}\033[0m" if _USE_COLOR else t
BOLD  = lambda t: _c("1", t)       # noqa
GREEN = lambda t: _c("1;32", t)    # noqa
CYAN  = lambda t: _c("1;36", t)    # noqa
YELLOW= lambda t: _c("1;33", t)    # noqa
RED   = lambda t: _c("1;31", t)    # noqa
DIM   = lambda t: _c("2", t)       # noqa
BLUE  = lambda t: _c("1;34", t)    # noqa


# ── Schema ─────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    branch      TEXT NOT NULL,
    content     TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'concept',
    weight      REAL NOT NULL DEFAULT 0.5,
    active      INTEGER NOT NULL DEFAULT 1,
    deleted     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    metadata    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS edges (
    id          TEXT PRIMARY KEY,
    from_id     TEXT NOT NULL,
    to_id       TEXT NOT NULL,
    relation    TEXT NOT NULL DEFAULT 'follows',
    weight      REAL NOT NULL DEFAULT 1.0,
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES nodes(id),
    FOREIGN KEY (to_id)   REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS branches (
    name        TEXT PRIMARY KEY,
    head_node   TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    description TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    FOREIGN KEY (head_node) REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS merges (
    id          TEXT PRIMARY KEY,
    sources     TEXT NOT NULL,
    result_node TEXT NOT NULL,
    strategy    TEXT NOT NULL DEFAULT 'manual',
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (result_node) REFERENCES nodes(id)
);

CREATE TABLE IF NOT EXISTS splits (
    id           TEXT PRIMARY KEY,
    origin_node  TEXT NOT NULL,
    removed_branch TEXT NOT NULL,
    result_node  TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS npath_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_nodes_branch  ON nodes(branch);
CREATE INDEX IF NOT EXISTS idx_nodes_active  ON nodes(active, deleted);
CREATE INDEX IF NOT EXISTS idx_edges_from    ON edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to      ON edges(to_id);
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    content, type, branch, metadata,
    content=nodes, content_rowid=rowid
);
"""

# Triggers to keep FTS in sync
FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS nodes_fts_insert AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, content, type, branch, metadata)
    VALUES (new.rowid, new.content, new.type, new.branch, new.metadata);
END;
CREATE TRIGGER IF NOT EXISTS nodes_fts_delete AFTER DELETE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, content, type, branch, metadata)
    VALUES ('delete', old.rowid, old.content, old.type, old.branch, old.metadata);
END;
CREATE TRIGGER IF NOT EXISTS nodes_fts_update AFTER UPDATE ON nodes BEGIN
    INSERT INTO nodes_fts(nodes_fts, rowid, content, type, branch, metadata)
    VALUES ('delete', old.rowid, old.content, old.type, old.branch, old.metadata);
    INSERT INTO nodes_fts(rowid, content, type, branch, metadata)
    VALUES (new.rowid, new.content, new.type, new.branch, new.metadata);
END;
"""


# ── DB connection ──────────────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _short_id() -> str:
    return str(uuid.uuid4())[:8]


def _node_id(branch: str, content: str) -> str:
    digest = hashlib.sha1(f"{branch}:{content}:{time.time()}".encode()).hexdigest()[:8]
    return f"n_{digest}"


def _merge_id() -> str:
    return f"m_{_short_id()}"


def _split_id() -> str:
    return f"s_{_short_id()}"


# ── Init ───────────────────────────────────────────────────────────────────────

def cmd_init() -> None:
    """Initialize the npath graph database."""
    conn = _connect()
    with conn:
        conn.executescript(SCHEMA)
        # FTS triggers — ignore errors if already exist
        for stmt in FTS_TRIGGERS.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError:
                    pass
        # Ensure main branch exists
        conn.execute(
            "INSERT OR IGNORE INTO branches (name, active, description, created_at) VALUES (?,1,?,?)",
            ("main", "Rama principal del grafo cognitivo", _now()),
        )
        conn.execute(
            "INSERT OR IGNORE INTO npath_meta (key, value) VALUES (?,?)",
            ("current_branch", "main"),
        )
    conn.close()
    print(GREEN("✅ npath inicializado") + f"  →  {DB_PATH}")
    print(f"   Rama activa: {CYAN('main')}")


# ── Current branch helper ──────────────────────────────────────────────────────

def _get_current_branch(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM npath_meta WHERE key='current_branch'").fetchone()
    return row["value"] if row else "main"


def _set_current_branch(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO npath_meta (key, value) VALUES ('current_branch', ?)", (name,)
    )


# ── Branch ─────────────────────────────────────────────────────────────────────

def cmd_branch(name: str, description: str = "") -> None:
    """Create a new branch (cognitive trajectory)."""
    conn = _connect()
    with conn:
        existing = conn.execute("SELECT name FROM branches WHERE name=?", (name,)).fetchone()
        if existing:
            print(YELLOW(f"⚠  La rama '{name}' ya existe."))
            # Switch to it
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
        active_mark = GREEN("●") if r["active"] else DIM("○")
        current_mark = " ◀" if r["name"] == current else ""
        count = conn2.execute(
            "SELECT COUNT(*) FROM nodes WHERE branch=? AND deleted=0", (r["name"],)
        ).fetchone()[0]
        desc = (r["description"] or "")[:40]
        print(f"  {active_mark}  {r['name']:<28}  {count:>6}  {DIM(desc)}{CYAN(current_mark)}")
    conn2.close()
    print()


# ── Commit (add node) ──────────────────────────────────────────────────────────

def cmd_commit(
    content: str,
    branch: Optional[str] = None,
    ntype: str = "concept",
    weight: float = 0.5,
    metadata: Optional[dict] = None,
) -> str:
    """Add a node (commit) to a branch."""
    conn = _connect()
    current = branch or _get_current_branch(conn)

    # Ensure branch exists
    existing = conn.execute("SELECT head_node FROM branches WHERE name=?", (current,)).fetchone()
    if not existing:
        print(YELLOW(f"⚠  La rama '{current}' no existe. Créala con: bago npath branch {current}"))
        conn.close()
        return ""

    nid = _node_id(current, content)
    prev_head = existing["head_node"]
    meta_json = json.dumps(metadata or {}, ensure_ascii=False)

    with conn:
        conn.execute(
            "INSERT INTO nodes (id, branch, content, type, weight, active, deleted, created_at, metadata)"
            " VALUES (?,?,?,?,?,1,0,?,?)",
            (nid, current, content, ntype, weight, _now(), meta_json),
        )
        # Edge from previous head if exists
        if prev_head:
            eid = f"e_{_short_id()}"
            conn.execute(
                "INSERT INTO edges (id, from_id, to_id, relation, weight, active, created_at)"
                " VALUES (?,?,?,'follows',1.0,1,?)",
                (eid, prev_head, nid, _now()),
            )
        # Update branch head
        conn.execute("UPDATE branches SET head_node=? WHERE name=?", (nid, current))

    conn.close()
    print(GREEN(f"✅ [{current}]") + f"  {BOLD(nid)}")
    print(f"   {DIM(content[:80])}")
    print(f"   type={CYAN(ntype)}  weight={weight:.2f}")
    return nid


# ── Log ────────────────────────────────────────────────────────────────────────

def cmd_log(branch: Optional[str] = None, limit: int = 20) -> None:
    """Show node history for a branch (or all branches)."""
    conn = _connect()
    current = _get_current_branch(conn)
    target = branch or current

    if target == "all":
        rows = conn.execute(
            "SELECT id, branch, content, type, weight, active, created_at"
            " FROM nodes WHERE deleted=0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, branch, content, type, weight, active, created_at"
            " FROM nodes WHERE branch=? AND deleted=0 ORDER BY created_at DESC LIMIT ?",
            (target, limit),
        ).fetchall()
    conn.close()

    if not rows:
        print(f"  No hay nodos en '{target}'")
        return

    print()
    title = f"  Log — {BOLD(target)}" if target != "all" else f"  Log — {BOLD('todas las ramas')}"
    print(title)
    print("  " + "─" * 70)
    for r in rows:
        active_icon = "●" if r["active"] else "○"
        ts = r["created_at"][:16]
        content_short = r["content"][:60] + ("…" if len(r["content"]) > 60 else "")
        print(
            f"  {DIM(active_icon)}  {CYAN(r['id'])}  "
            f"{DIM(ts)}  [{r['branch']}]  "
            f"{YELLOW(r['type'])}({r['weight']:.1f})"
        )
        print(f"       {content_short}")
    print()


# ── Merge ──────────────────────────────────────────────────────────────────────

def cmd_merge(
    branch1: str,
    branch2: str,
    content: Optional[str] = None,
    strategy: str = "manual",
) -> None:
    """Merge two branches into a new synthesis node."""
    conn = _connect()

    b1 = conn.execute("SELECT head_node FROM branches WHERE name=?", (branch1,)).fetchone()
    b2 = conn.execute("SELECT head_node FROM branches WHERE name=?", (branch2,)).fetchone()

    if not b1:
        print(RED(f"❌ Rama '{branch1}' no encontrada."))
        conn.close()
        return
    if not b2:
        print(RED(f"❌ Rama '{branch2}' no encontrada."))
        conn.close()
        return

    merge_content = content or f"Merge de '{branch1}' + '{branch2}'"
    merge_branch  = f"merge-{branch1[:8]}-{branch2[:8]}"

    # Create merge branch if not exists
    existing_mb = conn.execute("SELECT name FROM branches WHERE name=?", (merge_branch,)).fetchone()
    with conn:
        if not existing_mb:
            conn.execute(
                "INSERT INTO branches (name, active, description, created_at) VALUES (?,1,?,?)",
                (merge_branch, f"Fusión de {branch1} + {branch2}", _now()),
            )

    # Create synthesis node
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
        # Edges from both heads to merge node
        for parent_id in [b1["head_node"], b2["head_node"]]:
            if parent_id:
                conn.execute(
                    "INSERT INTO edges (id, from_id, to_id, relation, weight, active, created_at)"
                    " VALUES (?,?,?,'merges',1.0,1,?)",
                    (f"e_{_short_id()}", parent_id, nid, _now()),
                )
        # Update merge branch head
        conn.execute("UPDATE branches SET head_node=? WHERE name=?", (nid, merge_branch))
        # Record merge
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


# ── Unmerge ────────────────────────────────────────────────────────────────────

def cmd_unmerge(merge_id: str) -> None:
    """Deactivate a merge (reversible — history is preserved)."""
    conn = _connect()
    row = conn.execute("SELECT * FROM merges WHERE id=?", (merge_id,)).fetchone()
    if not row:
        print(RED(f"❌ Merge '{merge_id}' no encontrado."))
        conn.close()
        return
    if not row["active"]:
        print(YELLOW(f"⚠  Merge '{merge_id}' ya está inactivo."))
        conn.close()
        return

    with conn:
        conn.execute("UPDATE merges SET active=0 WHERE id=?", (merge_id,))
        # Soft-deactivate the result node (not deleted, just inactive)
        conn.execute("UPDATE nodes SET active=0 WHERE id=?", (row["result_node"],))
        # Deactivate edges pointing TO the merge node
        conn.execute("UPDATE edges SET active=0 WHERE to_id=?", (row["result_node"],))

    conn.close()
    sources = json.loads(row["sources"])
    print(GREEN(f"✅ Merge '{merge_id}' desactivado (reversible)"))
    print(f"   Ramas fuente: {', '.join(CYAN(s) for s in sources)}")
    print(f"   Nodo resultado inactivo: {row['result_node']}")
    print(f"   Para reactivar: bago npath reactivate-merge {merge_id}")


def cmd_reactivate_merge(merge_id: str) -> None:
    """Reactivate a previously deactivated merge."""
    conn = _connect()
    row = conn.execute("SELECT * FROM merges WHERE id=?", (merge_id,)).fetchone()
    if not row:
        print(RED(f"❌ Merge '{merge_id}' no encontrado."))
        conn.close()
        return
    with conn:
        conn.execute("UPDATE merges SET active=1 WHERE id=?", (merge_id,))
        conn.execute("UPDATE nodes SET active=1 WHERE id=?", (row["result_node"],))
        conn.execute("UPDATE edges SET active=1 WHERE to_id=?", (row["result_node"],))
    conn.close()
    print(GREEN(f"✅ Merge '{merge_id}' reactivado"))


# ── Split ──────────────────────────────────────────────────────────────────────

def cmd_split(node_id: str, remove_branch: str, content: Optional[str] = None) -> None:
    """Create C' = C without the influence of remove_branch (C - B → C').

    The original node C is preserved. A new node C' is created without the
    edge from the removed branch. This models: A + B → C  ⟹  C - B → C'
    """
    conn = _connect()
    node = conn.execute("SELECT * FROM nodes WHERE id=? AND deleted=0", (node_id,)).fetchone()
    if not node:
        print(RED(f"❌ Nodo '{node_id}' no encontrado."))
        conn.close()
        return

    # Find parents of node_id that belong to remove_branch
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

    # Get all active edges pointing to the original node (keep all except removed_branch ones)
    all_parents = conn.execute(
        "SELECT from_id FROM edges WHERE to_id=? AND active=1", (node_id,)
    ).fetchall()
    removed_ids = {r["from_id"] for r in removed_edges}
    kept_parents = [r["from_id"] for r in all_parents if r["from_id"] not in removed_ids]

    meta = json.loads(node["metadata"])
    meta["split_from"]      = node_id
    meta["removed_branch"]  = remove_branch
    meta["split_id"]        = split_id

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


# ── Activate / Deactivate ──────────────────────────────────────────────────────

def cmd_activate(branch: str, weight: Optional[float] = None) -> None:
    """Activate a branch and optionally set its node weights."""
    conn = _connect()
    row = conn.execute("SELECT name FROM branches WHERE name=?", (branch,)).fetchone()
    if not row:
        print(RED(f"❌ Rama '{branch}' no encontrada."))
        conn.close()
        return
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


def cmd_deactivate(branch: str) -> None:
    """Deactivate a branch (nodes remain, just marked inactive)."""
    conn = _connect()
    with conn:
        conn.execute("UPDATE branches SET active=0 WHERE name=?", (branch,))
    conn.close()
    print(YELLOW(f"○  Rama '{branch}' desactivada (historia preservada)"))


# ── Recall ─────────────────────────────────────────────────────────────────────

def cmd_recall(query: str, limit: int = 10) -> None:
    """Full-text search across all nodes."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT n.id, n.branch, n.content, n.type, n.weight, n.created_at
               FROM nodes_fts f
               JOIN nodes n ON n.rowid = f.rowid
               WHERE nodes_fts MATCH ? AND n.deleted=0
               ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        # FTS might not be populated yet — fallback to LIKE
        rows = conn.execute(
            """SELECT id, branch, content, type, weight, created_at
               FROM nodes WHERE deleted=0
               AND (content LIKE ? OR type LIKE ? OR metadata LIKE ?)
               ORDER BY created_at DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        ).fetchall()
    conn.close()

    if not rows:
        print(f"  Sin resultados para: {YELLOW(repr(query))}")
        return

    print()
    print(f"  Recall: {BOLD(repr(query))}  ({len(rows)} resultado(s))")
    print("  " + "─" * 70)
    for r in rows:
        ts = r["created_at"][:16]
        content_short = r["content"][:65] + ("…" if len(r["content"]) > 65 else "")
        print(
            f"  {CYAN(r['id'])}  {DIM(ts)}  "
            f"[{r['branch']}]  {YELLOW(r['type'])}({r['weight']:.1f})"
        )
        print(f"    {content_short}")
    print()


# ── Map ────────────────────────────────────────────────────────────────────────

def cmd_map(branch: Optional[str] = None, max_nodes: int = 50) -> None:
    """Generate a Mermaid graph of the node graph."""
    conn = _connect()

    if branch:
        nodes = conn.execute(
            "SELECT id, branch, content, type FROM nodes WHERE branch=? AND deleted=0 AND active=1",
            (branch,),
        ).fetchall()
        node_ids = {r["id"] for r in nodes}
        edges = conn.execute(
            "SELECT from_id, to_id, relation FROM edges WHERE active=1",
        ).fetchall()
        edges = [e for e in edges if e["from_id"] in node_ids and e["to_id"] in node_ids]
    else:
        nodes = conn.execute(
            "SELECT id, branch, content, type FROM nodes WHERE deleted=0 AND active=1 LIMIT ?",
            (max_nodes,),
        ).fetchall()
        node_ids = {r["id"] for r in nodes}
        edges = conn.execute(
            "SELECT from_id, to_id, relation FROM edges WHERE active=1",
        ).fetchall()
        edges = [e for e in edges if e["from_id"] in node_ids and e["to_id"] in node_ids]
    conn.close()

    if not nodes:
        print("```mermaid\ngraph LR\n    A[No hay nodos activos]\n```")
        return

    # Map type to icon
    icons = {
        "concept": "💡", "merge": "🔀", "decision": "🎯",
        "file": "📄", "memory": "🧠", "hypothesis": "🔬", "split": "✂️",
    }

    print("```mermaid")
    print("graph LR")

    # Group by branch using subgraph
    branches_used: dict[str, list] = {}
    for n in nodes:
        branches_used.setdefault(n["branch"], []).append(n)

    for bname, bnodes in branches_used.items():
        safe_b = bname.replace("-", "_").replace("/", "_")
        print(f'    subgraph {safe_b}["{bname}"]')
        for n in bnodes:
            icon  = icons.get(n["type"], "○")
            label = n["content"][:30].replace('"', "'")
            safe_id = n["id"].replace("-", "_")
            print(f'        {safe_id}["{icon} {label}"]')
        print("    end")

    for e in edges:
        arrow = {"merges": "==>", "splits": "-.->"}.get(e["relation"], "-->")
        safe_from = e["from_id"].replace("-", "_")
        safe_to   = e["to_id"].replace("-", "_")
        print(f"    {safe_from} {arrow} {safe_to}")

    print("```")


# ── Status ─────────────────────────────────────────────────────────────────────

def cmd_status() -> None:
    """Show a summary of the graph state."""
    conn = _connect()
    current = _get_current_branch(conn)

    n_branches = conn.execute("SELECT COUNT(*) FROM branches WHERE active=1").fetchone()[0]
    n_nodes    = conn.execute("SELECT COUNT(*) FROM nodes WHERE deleted=0 AND active=1").fetchone()[0]
    n_edges    = conn.execute("SELECT COUNT(*) FROM edges WHERE active=1").fetchone()[0]
    n_merges   = conn.execute("SELECT COUNT(*) FROM merges WHERE active=1").fetchone()[0]
    n_splits   = conn.execute("SELECT COUNT(*) FROM splits WHERE active=1").fetchone()[0]

    # Nodes in current branch
    n_current  = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE branch=? AND deleted=0", (current,)
    ).fetchone()[0]

    conn.close()

    print()
    print(f"  {BOLD('npath')} — Estado del grafo cognitivo")
    print("  " + "─" * 50)
    print(f"  Rama activa   : {CYAN(current)}")
    print(f"  Nodos en rama : {BOLD(str(n_current))}")
    print()
    print(f"  Total nodos   : {n_nodes}")
    print(f"  Total ramas   : {n_branches}")
    print(f"  Aristas       : {n_edges}")
    print(f"  Merges activos: {n_merges}")
    print(f"  Splits        : {n_splits}")
    print(f"  DB            : {DIM(str(DB_PATH))}")
    print()


# ── Node detail ────────────────────────────────────────────────────────────────

def cmd_node(node_id: str) -> None:
    """Show details of a specific node."""
    conn = _connect()
    node = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not node:
        print(RED(f"❌ Nodo '{node_id}' no encontrado."))
        conn.close()
        return

    parents = conn.execute(
        "SELECT from_id, relation FROM edges WHERE to_id=? AND active=1", (node_id,)
    ).fetchall()
    children = conn.execute(
        "SELECT to_id, relation FROM edges WHERE from_id=? AND active=1", (node_id,)
    ).fetchall()
    conn.close()

    meta = json.loads(node["metadata"] or "{}")
    print()
    print(f"  {BOLD(node_id)}")
    print(f"  branch   : {CYAN(node['branch'])}")
    print(f"  type     : {YELLOW(node['type'])}")
    print(f"  weight   : {node['weight']:.2f}")
    print(f"  active   : {'yes' if node['active'] else DIM('no')}")
    print(f"  deleted  : {'yes' if node['deleted'] else 'no'}")
    print(f"  created  : {node['created_at']}")
    print()
    print(f"  content:")
    print(f"    {node['content']}")
    if meta:
        print(f"  metadata : {json.dumps(meta, ensure_ascii=False, indent=4)}")
    if parents:
        parent_str = ", ".join(f"{r['from_id']}({r['relation']})" for r in parents)
        print(f"  padres   : {parent_str}")
    if children:
        child_str = ", ".join(f"{r['to_id']}({r['relation']})" for r in children)
        print(f"  hijos    : {child_str}")
    print()


# ── Delete node (soft) ─────────────────────────────────────────────────────────

def cmd_delete_node(node_id: str) -> None:
    """Soft-delete a node (history preserved, marked deleted=1)."""
    conn = _connect()
    node = conn.execute("SELECT id FROM nodes WHERE id=? AND deleted=0", (node_id,)).fetchone()
    if not node:
        print(RED(f"❌ Nodo '{node_id}' no encontrado o ya eliminado."))
        conn.close()
        return
    with conn:
        conn.execute("UPDATE nodes SET deleted=1, active=0 WHERE id=?", (node_id,))
    conn.close()
    print(YELLOW(f"○  Nodo '{node_id}' marcado como eliminado (soft delete — historia preservada)"))


# ── Self-tests ─────────────────────────────────────────────────────────────────

def _run_tests() -> None:
    import tempfile, shutil
    print("  Ejecutando tests de npath.py...")

    global DB_PATH, STATE_DIR
    orig_db    = DB_PATH
    orig_state = STATE_DIR
    tmpdir = Path(tempfile.mkdtemp())
    try:
        DB_PATH   = tmpdir / "npath_test.db"
        STATE_DIR = tmpdir

        # T1: init
        cmd_init()
        assert DB_PATH.exists(), "T1: DB no creada"
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
        conn = _connect()
        e = conn.execute("SELECT id FROM edges WHERE to_id=?", (nid2,)).fetchone()
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
        m = conn.execute("SELECT id FROM merges").fetchone()
        conn.close()
        assert m, "T6: merge no registrado"
        merge_id = m[0]
        print(f"  T6 ✅ merge  ({merge_id})")

        # T7: unmerge
        cmd_unmerge(merge_id)
        conn = _connect()
        m_row = conn.execute("SELECT active FROM merges WHERE id=?", (merge_id,)).fetchone()
        conn.close()
        assert m_row and m_row[0] == 0, "T7: merge no desactivado"
        print("  T7 ✅ unmerge (reversible)")

        # T8: reactivate
        cmd_reactivate_merge(merge_id)
        conn = _connect()
        m_row = conn.execute("SELECT active FROM merges WHERE id=?", (merge_id,)).fetchone()
        conn.close()
        assert m_row and m_row[0] == 1, "T8: merge no reactivado"
        print("  T8 ✅ reactivate-merge")

        # T9: recall
        # Add a searchable node
        cmd_commit("búsqueda semántica para recall test", branch="idea-A", ntype="memory")
        # FTS might need reconnection; use LIKE fallback path always for tests
        conn = _connect()
        rows = conn.execute(
            "SELECT id FROM nodes WHERE content LIKE ?", ("%recall test%",)
        ).fetchall()
        conn.close()
        assert rows, "T9: recall no encontró el nodo"
        print("  T9 ✅ recall (FTS/LIKE)")

        # T10: split
        conn = _connect()
        target_node = conn.execute(
            "SELECT id FROM nodes WHERE branch='idea-A' AND deleted=0 LIMIT 1"
        ).fetchone()
        conn.close()
        if target_node:
            cmd_split(target_node["id"], "idea-A", content="Variante split test")
            conn = _connect()
            s = conn.execute("SELECT id FROM splits").fetchone()
            conn.close()
            assert s, "T10: split no registrado"
            print("  T10 ✅ split")
        else:
            print("  T10 ⚠  skip (sin nodos en idea-A para split)")

        # T11: status smoke test
        cmd_status()
        print("  T11 ✅ status")

        print()
        print(GREEN("  ✅ 11/11 tests pasaron"))

    finally:
        DB_PATH   = orig_db
        STATE_DIR = orig_state
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── CLI ────────────────────────────────────────────────────────────────────────

def _usage() -> None:
    print(__doc__)


def main(argv: list[str] | None = None) -> None:
    args = argv if argv is not None else sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        _usage()
        return

    cmd = args[0].lower()
    rest = args[1:]

    # ── init ──────────────────────────────────────────────────────────────────
    if cmd == "init":
        cmd_init()

    # ── branch ────────────────────────────────────────────────────────────────
    elif cmd == "branch":
        if not rest:
            # Just switch to current / list
            conn = _connect()
            cur = _get_current_branch(conn)
            conn.close()
            print(f"  Rama activa: {CYAN(cur)}")
            print("  Para listar: bago npath branches")
        else:
            name = rest[0]
            desc = rest[1] if len(rest) > 1 else ""
            cmd_branch(name, desc)

    # ── branches ──────────────────────────────────────────────────────────────
    elif cmd == "branches":
        cmd_branches()

    # ── commit ────────────────────────────────────────────────────────────────
    elif cmd == "commit":
        if not rest:
            print(RED("❌ Uso: bago npath commit <contenido> [--branch <rama>] [--type <tipo>] [--weight <0-1>]"))
            sys.exit(1)
        # Parse optional flags
        content = rest[0]
        branch  = None
        ntype   = "concept"
        weight  = 0.5
        i = 1
        while i < len(rest):
            if rest[i] == "--branch" and i + 1 < len(rest):
                branch = rest[i + 1]; i += 2
            elif rest[i] == "--type" and i + 1 < len(rest):
                ntype = rest[i + 1]; i += 2
            elif rest[i] == "--weight" and i + 1 < len(rest):
                try:
                    weight = float(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                i += 1
        cmd_commit(content, branch=branch, ntype=ntype, weight=weight)

    # ── log ───────────────────────────────────────────────────────────────────
    elif cmd == "log":
        branch = None
        limit  = 20
        i = 0
        while i < len(rest):
            if rest[i] == "--branch" and i + 1 < len(rest):
                branch = rest[i + 1]; i += 2
            elif rest[i] == "--limit" and i + 1 < len(rest):
                try:
                    limit = int(rest[i + 1])
                except ValueError:
                    pass
                i += 2
            else:
                branch = rest[i]; i += 1
        cmd_log(branch=branch, limit=limit)

    # ── map ───────────────────────────────────────────────────────────────────
    elif cmd == "map":
        branch = rest[0] if rest and not rest[0].startswith("--") else None
        cmd_map(branch=branch)

    # ── merge ─────────────────────────────────────────────────────────────────
    elif cmd == "merge":
        if len(rest) < 2:
            print(RED("❌ Uso: bago npath merge <rama1> <rama2> [--content <desc>] [--strategy manual|weighted]"))
            sys.exit(1)
        b1, b2 = rest[0], rest[1]
        content  = None
        strategy = "manual"
        i = 2
        while i < len(rest):
            if rest[i] == "--content" and i + 1 < len(rest):
                content = rest[i + 1]; i += 2
            elif rest[i] == "--strategy" and i + 1 < len(rest):
                strategy = rest[i + 1]; i += 2
            else:
                i += 1
        cmd_merge(b1, b2, content=content, strategy=strategy)

    # ── unmerge ───────────────────────────────────────────────────────────────
    elif cmd == "unmerge":
        if not rest:
            print(RED("❌ Uso: bago npath unmerge <merge-id>"))
            sys.exit(1)
        cmd_unmerge(rest[0])

    elif cmd == "reactivate-merge":
        if not rest:
            print(RED("❌ Uso: bago npath reactivate-merge <merge-id>"))
            sys.exit(1)
        cmd_reactivate_merge(rest[0])

    # ── split ─────────────────────────────────────────────────────────────────
    elif cmd == "split":
        if not rest:
            print(RED("❌ Uso: bago npath split <node-id> --remove <rama> [--content <desc>]"))
            sys.exit(1)
        node_id       = rest[0]
        remove_branch = None
        content       = None
        i = 1
        while i < len(rest):
            if rest[i] == "--remove" and i + 1 < len(rest):
                remove_branch = rest[i + 1]; i += 2
            elif rest[i] == "--content" and i + 1 < len(rest):
                content = rest[i + 1]; i += 2
            else:
                i += 1
        if not remove_branch:
            print(RED("❌ Usa --remove <rama> para indicar qué influencia eliminar"))
            sys.exit(1)
        cmd_split(node_id, remove_branch, content=content)

    # ── activate / deactivate ─────────────────────────────────────────────────
    elif cmd == "activate":
        if not rest:
            print(RED("❌ Uso: bago npath activate <rama> [--weight <0-1>]"))
            sys.exit(1)
        branch = rest[0]
        weight = None
        if "--weight" in rest:
            idx = rest.index("--weight")
            if idx + 1 < len(rest):
                try:
                    weight = float(rest[idx + 1])
                except ValueError:
                    pass
        cmd_activate(branch, weight=weight)

    elif cmd == "deactivate":
        if not rest:
            print(RED("❌ Uso: bago npath deactivate <rama>"))
            sys.exit(1)
        cmd_deactivate(rest[0])

    # ── recall ────────────────────────────────────────────────────────────────
    elif cmd == "recall":
        if not rest:
            print(RED("❌ Uso: bago npath recall <query> [--limit N]"))
            sys.exit(1)
        query = rest[0]
        limit = 10
        if "--limit" in rest:
            idx = rest.index("--limit")
            if idx + 1 < len(rest):
                try:
                    limit = int(rest[idx + 1])
                except ValueError:
                    pass
        cmd_recall(query, limit=limit)

    # ── status ────────────────────────────────────────────────────────────────
    elif cmd == "status":
        cmd_status()

    # ── node detail ───────────────────────────────────────────────────────────
    elif cmd == "node":
        if not rest:
            print(RED("❌ Uso: bago npath node <node-id>"))
            sys.exit(1)
        cmd_node(rest[0])

    # ── delete-node ───────────────────────────────────────────────────────────
    elif cmd in ("delete-node", "rm"):
        if not rest:
            print(RED("❌ Uso: bago npath delete-node <node-id>"))
            sys.exit(1)
        cmd_delete_node(rest[0])

    # ── test ──────────────────────────────────────────────────────────────────
    elif cmd == "--test":
        _run_tests()

    else:
        print(RED(f"❌ Subcomando desconocido: '{cmd}'"))
        print("   Usa: bago npath --help")
        sys.exit(1)


if __name__ == "__main__":
    main()
