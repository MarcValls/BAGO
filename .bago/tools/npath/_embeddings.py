"""npath._embeddings — Semantic search via Ollama embeddings + cosine similarity."""
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

from npath._db import _connect, _now, BOLD, GREEN, CYAN, YELLOW, RED, DIM
from npath._ollama import _ollama_available, _OLLAMA_URL

_EMBED_MODEL_PREF = [
    "nomic-embed-text", "mxbai-embed-large", "all-minilm",
    "llama3", "qwen", "mistral",
]


# ── Ollama embedding call ──────────────────────────────────────────────────────

def _ollama_embed(text: str, model: str) -> Optional[list]:
    """Get embedding vector from Ollama. Returns list[float] or None."""
    import urllib.request
    payload = json.dumps({"model": model, "prompt": text}).encode()
    req = urllib.request.Request(
        f"{_OLLAMA_URL}/api/embeddings", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        return data.get("embedding")
    except Exception:
        return None


def _pick_embed_model() -> Optional[str]:
    """Pick best available embedding model from Ollama."""
    available, models = _ollama_available()
    if not available or not models:
        return None
    for pref in _EMBED_MODEL_PREF:
        for m in models:
            if pref in m.lower():
                return m
    return models[0]


# ── Cosine similarity (pure Python) ───────────────────────────────────────────

def _cosine_similarity(a: list, b: list) -> float:
    if len(a) != len(b):
        return 0.0
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(x * x for x in b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_embed(
    branch: Optional[str] = None,
    model: Optional[str] = None,
    batch: int = 50,
) -> None:
    """Embed all un-embedded nodes in a branch using Ollama."""
    resolved = model or _pick_embed_model()
    if not resolved:
        print(RED("❌ Ollama no disponible o sin modelos. Inicia con: ollama serve"))
        return

    conn    = _connect()
    current = branch or (conn.execute("SELECT value FROM npath_meta WHERE key='current_branch'").fetchone() or {}).get("value", "main")

    query = (
        "SELECT n.id, n.content FROM nodes n"
        " LEFT JOIN node_embeddings e ON e.node_id = n.id"
        " WHERE n.deleted=0 AND n.active=1 AND e.node_id IS NULL"
    )
    if current != "all":
        rows = conn.execute(query + f" AND n.branch=? LIMIT {batch}", (current,)).fetchall()
    else:
        rows = conn.execute(query + f" LIMIT {batch}").fetchall()

    if not rows:
        print(f"  {DIM('Sin nodos nuevos para embeber en rama:')} {CYAN(current)}")
        conn.close(); return

    print(f"\n  Embebiendo {len(rows)} nodos  [{CYAN(current)}]  modelo={DIM(resolved)}")
    ok = 0
    for row in rows:
        vec = _ollama_embed(row["content"], resolved)
        if vec:
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO node_embeddings (node_id, model, vector, created_at)"
                    " VALUES (?,?,?,?)",
                    (row["id"], resolved, json.dumps(vec), _now()),
                )
            print(f"  {GREEN('●')} {row['id']}  {DIM(row['content'][:50])}")
            ok += 1
        else:
            print(f"  {YELLOW('○')} {row['id']}  {RED('error al embeber')}")

    conn.close()
    print(f"\n  {GREEN(f'✅ {ok}/{len(rows)} nodos embebidos')}")


def cmd_similar(
    node_id: str,
    limit: int = 8,
    threshold: float = 0.5,
) -> None:
    """Find nodes semantically similar to a given node using cosine similarity."""
    conn = _connect()
    target_row = conn.execute(
        "SELECT vector, model FROM node_embeddings WHERE node_id=?", (node_id,)
    ).fetchone()

    if not target_row:
        node_row = conn.execute("SELECT content FROM nodes WHERE id=? AND deleted=0", (node_id,)).fetchone()
        if not node_row:
            print(RED(f"❌ Nodo '{node_id}' no encontrado."))
            conn.close(); return
        model = _pick_embed_model()
        if not model:
            print(RED("❌ Sin embedding para ese nodo. Ejecuta: bago npath embed"))
            conn.close(); return
        print(f"  {DIM('Embebiendo nodo on-the-fly...')} ", end="", flush=True)
        vec = _ollama_embed(node_row["content"], model)
        if not vec:
            print(RED("error"))
            conn.close(); return
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO node_embeddings (node_id, model, vector, created_at)"
                " VALUES (?,?,?,?)",
                (node_id, model, json.dumps(vec), _now()),
            )
        print(GREEN("ok"))
        target_vec = vec
    else:
        target_vec = json.loads(target_row["vector"])

    all_embs = conn.execute(
        "SELECT e.node_id, e.vector, n.branch, n.content, n.type, n.weight"
        " FROM node_embeddings e JOIN nodes n ON n.id = e.node_id"
        " WHERE e.node_id != ? AND n.deleted=0 AND n.active=1",
        (node_id,),
    ).fetchall()
    conn.close()

    scores = []
    for row in all_embs:
        vec = json.loads(row["vector"])
        sim = _cosine_similarity(target_vec, vec)
        if sim >= threshold:
            scores.append((sim, row))

    scores.sort(key=lambda x: x[0], reverse=True)
    top = scores[:limit]

    if not top:
        print(f"  Sin resultados similares (threshold={threshold:.2f})")
        return

    conn2 = _connect()
    src = conn2.execute("SELECT branch, content, type FROM nodes WHERE id=?", (node_id,)).fetchone()
    conn2.close()
    src_content = src["content"][:70] if src else node_id

    print()
    print(f"  {BOLD('Similar a:')} {CYAN(node_id)}  {DIM(src_content)}")
    print("  " + "─" * 70)
    for sim, row in top:
        bar = "█" * int(sim * 20)
        print(
            f"  {CYAN(row['node_id'])}  {GREEN(f'{sim:.3f}')} {DIM(bar)}"
            f"  [{row['branch']}]  {YELLOW(row['type'])}({row['weight']:.1f})"
        )
        print(f"    {row['content'][:70]}")
    print()



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
