"""npath._view — Log, map, status, node, recall, delete-node commands."""
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
import sqlite3
from typing import Optional

from npath._db import (
    _connect, _get_current_branch, DB_PATH,
    BOLD, GREEN, CYAN, YELLOW, RED, DIM,
)


# ── Log ────────────────────────────────────────────────────────────────────────

def cmd_log(branch: Optional[str] = None, limit: int = 20) -> None:
    """Show node history for a branch (or all branches)."""
    conn = _connect()
    current = _get_current_branch(conn)
    target  = branch or current

    if target == "all":
        rows = conn.execute(
            "SELECT id, branch, content, type, weight, active, created_at"
            " FROM nodes WHERE deleted=0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        title = "all branches"
    else:
        rows = conn.execute(
            "SELECT id, branch, content, type, weight, active, created_at"
            " FROM nodes WHERE branch=? AND deleted=0 ORDER BY created_at DESC LIMIT ?",
            (target, limit),
        ).fetchall()
        title = target
    conn.close()

    if not rows:
        print(f"  Sin nodos en [{CYAN(title)}]")
        return

    print()
    print(f"  Log — {CYAN(title)}{' (rama activa)' if title == current else ''}")
    print("  " + "─" * 72)
    for r in rows:
        active_mark = GREEN("●") if r["active"] else DIM("○")
        ts          = r["created_at"][:16]
        content_s   = r["content"][:55] + ("…" if len(r["content"]) > 55 else "")
        print(
            f"  {active_mark} {CYAN(r['id'])}  {DIM(ts)}"
            f"  {YELLOW(r['type'])}({r['weight']:.1f})"
        )
        print(f"      {content_s}")
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

    icons = {
        "concept": "💡", "merge": "🔀", "decision": "🎯",
        "file": "📄", "memory": "🧠", "hypothesis": "🔬", "split": "✂️",
    }

    print("```mermaid")
    print("graph LR")

    branches_used: dict[str, list] = {}
    for n in nodes:
        branches_used.setdefault(n["branch"], []).append(n)

    for bname, bnodes in branches_used.items():
        safe_b = bname.replace("-", "_").replace("/", "_")
        print(f'    subgraph {safe_b}["{bname}"]')
        for n in bnodes:
            icon    = icons.get(n["type"], "○")
            label   = n["content"][:30].replace('"', "'")
            safe_id = n["id"].replace("-", "_")
            print(f'        {safe_id}["{icon} {label}"]')
        print("    end")

    for e in edges:
        arrow    = {"merges": "==>", "splits": "-.->"}.get(e["relation"], "-->")
        safe_frm = e["from_id"].replace("-", "_")
        safe_to  = e["to_id"].replace("-", "_")
        print(f"    {safe_frm} {arrow} {safe_to}")

    print("```")


# ── Status ─────────────────────────────────────────────────────────────────────

def cmd_status() -> None:
    """Show a summary of the graph state."""
    conn = _connect()
    current    = _get_current_branch(conn)
    n_branches = conn.execute("SELECT COUNT(*) FROM branches WHERE active=1").fetchone()[0]
    n_nodes    = conn.execute("SELECT COUNT(*) FROM nodes WHERE deleted=0 AND active=1").fetchone()[0]
    n_edges    = conn.execute("SELECT COUNT(*) FROM edges WHERE active=1").fetchone()[0]
    n_merges   = conn.execute("SELECT COUNT(*) FROM merges WHERE active=1").fetchone()[0]
    n_splits   = conn.execute("SELECT COUNT(*) FROM splits WHERE active=1").fetchone()[0]
    n_current  = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE branch=? AND deleted=0", (current,)
    ).fetchone()[0]
    n_embedded = conn.execute("SELECT COUNT(*) FROM node_embeddings").fetchone()[0]
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
    print(f"  Embebidos     : {n_embedded}")
    print(f"  DB            : {DIM(str(DB_PATH))}")
    print()


# ── Node detail ────────────────────────────────────────────────────────────────

def cmd_node(node_id: str) -> None:
    """Show details of a specific node."""
    conn = _connect()
    node = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
    if not node:
        print(RED(f"❌ Nodo '{node_id}' no encontrado."))
        conn.close(); return

    parents  = conn.execute(
        "SELECT from_id, relation FROM edges WHERE to_id=? AND active=1", (node_id,)
    ).fetchall()
    children = conn.execute(
        "SELECT to_id, relation FROM edges WHERE from_id=? AND active=1", (node_id,)
    ).fetchall()
    embedded = conn.execute(
        "SELECT model, created_at FROM node_embeddings WHERE node_id=?", (node_id,)
    ).fetchone()
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
    if embedded:
        print(f"  embedding: {DIM(embedded['model'])} @ {embedded['created_at'][:16]}")
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
        conn.close(); return
    with conn:
        conn.execute("UPDATE nodes SET deleted=1, active=0 WHERE id=?", (node_id,))
    conn.close()
    print(YELLOW(f"○  Nodo '{node_id}' marcado como eliminado (soft delete — historia preservada)"))


# ── Recall (FTS5 + optional semantic) ─────────────────────────────────────────

def cmd_recall(query: str, limit: int = 10, semantic: bool = True) -> None:
    """Full-text search + optional semantic similarity across all nodes."""
    conn = _connect()
    try:
        fts_rows = conn.execute(
            """SELECT n.id, n.branch, n.content, n.type, n.weight, n.created_at
               FROM nodes_fts f
               JOIN nodes n ON n.rowid = f.rowid
               WHERE nodes_fts MATCH ? AND n.deleted=0
               ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        fts_rows = conn.execute(
            """SELECT id, branch, content, type, weight, created_at
               FROM nodes WHERE deleted=0
               AND (content LIKE ? OR type LIKE ? OR metadata LIKE ?)
               ORDER BY created_at DESC LIMIT ?""",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        ).fetchall()
    conn.close()

    seen_ids = {r["id"] for r in fts_rows}
    results  = list(fts_rows)

    # Semantic augmentation (non-blocking, optional)
    if semantic:
        try:
            from npath._embeddings import _pick_embed_model, _ollama_embed, _cosine_similarity
            model = _pick_embed_model()
            if model:
                query_vec = _ollama_embed(query, model)
                if query_vec:
                    conn2 = _connect()
                    emb_rows = conn2.execute(
                        "SELECT e.node_id, e.vector, n.branch, n.content, n.type, n.weight, n.created_at"
                        " FROM node_embeddings e JOIN nodes n ON n.id = e.node_id"
                        " WHERE n.deleted=0 AND n.active=1"
                    ).fetchall()
                    conn2.close()
                    scored = []
                    for row in emb_rows:
                        if row["node_id"] in seen_ids:
                            continue
                        vec = json.loads(row["vector"])
                        sim = _cosine_similarity(query_vec, vec)
                        if sim >= 0.5:
                            scored.append((sim, row))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    for sim, row in scored[:limit]:
                        results.append(row)
                        seen_ids.add(row["node_id"])
        except Exception:
            pass  # Embeddings not available — FTS only

    if not results:
        print(f"  Sin resultados para: {YELLOW(repr(query))}")
        return

    print()
    print(f"  Recall: {BOLD(repr(query))}  ({len(results)} resultado(s))")
    print("  " + "─" * 70)
    for r in results:
        node_id_key = "node_id" if "node_id" in r.keys() else "id"
        rid     = r[node_id_key]
        ts      = r["created_at"][:16]
        content = r["content"][:65] + ("…" if len(r["content"]) > 65 else "")
        print(
            f"  {CYAN(rid)}  {DIM(ts)}  [{r['branch']}]  {YELLOW(r['type'])}({r['weight']:.1f})"
        )
        print(f"    {content}")
    print()
