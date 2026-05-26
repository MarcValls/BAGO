"""npath._ollama — LLM integration: think, reflect, suggest, evolve."""
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
import re
from typing import Optional

from bago.ollama_runtime import default_ollama_base_url

from npath._db import (
    _connect, _get_current_branch, _now,
    BOLD, GREEN, CYAN, YELLOW, RED, DIM,
)
from npath._graph import cmd_commit

_OLLAMA_URL    = default_ollama_base_url()
_DEFAULT_MODEL = "llama3"


# ── Availability ───────────────────────────────────────────────────────────────

def _ollama_available() -> tuple[bool, list[str]]:
    """Check if Ollama is running. Returns (available, list_of_models)."""
    import urllib.request
    try:
        with urllib.request.urlopen(f"{_OLLAMA_URL}/api/tags", timeout=2) as r:
            data = json.loads(r.read())
        models = [m["name"] for m in data.get("models", [])]
        return True, models
    except Exception:
        return False, []


def _pick_model(model_arg: Optional[str]) -> Optional[str]:
    """Resolve model: prefer explicit arg, then first preferred, then any."""
    available, models = _ollama_available()
    if not available:
        return None
    if model_arg:
        for m in models:
            if model_arg in m or m in model_arg:
                return m
        return model_arg
    for preferred in ["llama3", "mistral", "gemma", "qwen", "phi"]:
        for m in models:
            if preferred in m.lower():
                return m
    return models[0] if models else _DEFAULT_MODEL


# ── Generate ───────────────────────────────────────────────────────────────────

def _ollama_generate(
    prompt: str,
    model: str = _DEFAULT_MODEL,
    system: str = "",
    stream: bool = True,
) -> str:
    """Call Ollama /api/generate. Streams to stdout if stream=True."""
    import urllib.request
    payload: dict = {"model": model, "prompt": prompt, "stream": stream}
    if system:
        payload["system"] = system

    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{_OLLAMA_URL}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    full_text = ""
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            if stream:
                print()
                for line in r:
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    token = chunk.get("response", "")
                    print(token, end="", flush=True)
                    full_text += token
                    if chunk.get("done"):
                        break
                print()
            else:
                raw = json.loads(r.read())
                full_text = raw.get("response", "")
    except Exception as e:
        print(RED(f"\n❌ Ollama error: {e}"))
        print("   Asegúrate de que Ollama está corriendo: ollama serve")
        return ""
    return full_text.strip()


# ── Graph context builder ──────────────────────────────────────────────────────

def _build_graph_context(branch: Optional[str] = None, limit: int = 15) -> str:
    """Build a text representation of the graph for LLM context."""
    conn = _connect()
    current = _get_current_branch(conn)
    target  = branch or current

    branches_all = conn.execute(
        "SELECT name, description, active FROM branches ORDER BY created_at"
    ).fetchall()

    if target == "all":
        nodes = conn.execute(
            "SELECT id, branch, content, type, weight, created_at FROM nodes"
            " WHERE deleted=0 AND active=1 ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    else:
        nodes = conn.execute(
            "SELECT id, branch, content, type, weight, created_at FROM nodes"
            " WHERE branch=? AND deleted=0 AND active=1 ORDER BY created_at DESC LIMIT ?",
            (target, limit),
        ).fetchall()

    merges = conn.execute(
        "SELECT id, sources, result_node FROM merges WHERE active=1"
    ).fetchall()
    conn.close()

    lines = [
        "# Estado del grafo cognitivo BAGO (npath)",
        f"Rama activa: {current}",
        "",
        "## Ramas",
    ]
    for b in branches_all:
        mark = "▶" if b["name"] == current else "○"
        lines.append(
            f"  {mark} {b['name']}  {'activa' if b['active'] else 'inactiva'}  {b['description'] or ''}"
        )

    lines += ["", f"## Nodos recientes — rama: {target}", ""]
    for n in nodes:
        lines.append(
            f"  [{n['id']}] branch={n['branch']} type={n['type'].upper()}"
            f" weight={n['weight']:.1f} @{n['created_at'][:16]}"
        )
        lines.append(f"    {n['content']}")
        lines.append("")

    if merges:
        lines += ["## Fusiones activas", ""]
        for m in merges:
            sources = ", ".join(json.loads(m["sources"]))
            lines.append(f"  {m['id']}: {sources} → {m['result_node']}")

    return "\n".join(lines)


# ── Subcommands ────────────────────────────────────────────────────────────────

def cmd_think(
    query: str,
    branch: Optional[str] = None,
    model: Optional[str] = None,
    do_commit: bool = False,
    limit: int = 15,
) -> None:
    """Ask Ollama to reason about the graph + a question."""
    resolved = _pick_model(model)
    if resolved is None:
        print(RED("❌ Ollama no disponible. Inicia con: ollama serve")); return

    ctx    = _build_graph_context(branch=branch, limit=limit)
    system = (
        "Eres un asistente de pensamiento que razona sobre un grafo cognitivo versionado. "
        "El grafo representa ideas, decisiones y memoria de un proyecto de software. "
        "Responde de forma concisa y estructurada. No repitas el contexto."
    )
    prompt = f"{ctx}\n\n## Pregunta\n{query}"

    print(f"\n  {DIM('Modelo:')} {CYAN(resolved)}  {DIM('Rama:')} {branch or '(actual)'}")
    print(f"  {BOLD(query)}")
    print("  " + "─" * 60)

    answer = _ollama_generate(prompt, model=resolved, system=system, stream=True)

    if do_commit and answer:
        conn = _connect()
        cur  = branch or _get_current_branch(conn)
        conn.close()
        nid  = cmd_commit(
            f"[think] {query[:60]}\n→ {answer[:300]}",
            branch=cur, ntype="memory", weight=0.7,
            metadata={"query": query, "model": resolved, "source": "ollama_think"},
        )
        print(f"\n  {DIM('Guardado como nodo:')} {CYAN(nid)}")


def cmd_reflect(
    branch: Optional[str] = None,
    model: Optional[str] = None,
    do_commit: bool = False,
) -> None:
    """Ask Ollama to summarize and reflect on a branch's state."""
    resolved = _pick_model(model)
    if resolved is None:
        print(RED("❌ Ollama no disponible. Inicia con: ollama serve")); return

    conn = _connect()
    cur  = branch or _get_current_branch(conn)
    conn.close()

    ctx    = _build_graph_context(branch=cur, limit=20)
    system = (
        "Eres un asistente de reflexión cognitiva. Lee el estado de una trayectoria "
        "de pensamiento y produce: (1) resumen en 2-3 frases, (2) patrones o temas "
        "clave, (3) lo que falta o puede estar incompleto. Responde en español."
    )
    prompt = f"{ctx}\n\nGenera una reflexión estructurada sobre la rama '{cur}'."

    print(f"\n  {DIM('Reflexión sobre:')} {CYAN(cur)}  {DIM('Modelo:')} {resolved}")
    print("  " + "─" * 60)

    answer = _ollama_generate(prompt, model=resolved, system=system, stream=True)

    if do_commit and answer:
        nid = cmd_commit(
            f"[reflect] {answer[:300]}", branch=cur, ntype="memory", weight=0.75,
            metadata={"source": "ollama_reflect", "model": resolved},
        )
        print(f"\n  {DIM('Guardado como nodo:')} {CYAN(nid)}")


def cmd_suggest(
    branch: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Ask Ollama what next steps, nodes or branches to create."""
    resolved = _pick_model(model)
    if resolved is None:
        print(RED("❌ Ollama no disponible. Inicia con: ollama serve")); return

    conn = _connect()
    cur  = branch or _get_current_branch(conn)
    conn.close()

    ctx    = _build_graph_context(branch=cur, limit=15)
    system = (
        "Eres un asistente de planificación cognitiva. Analiza el grafo y sugiere "
        "acciones concretas en lista:\n"
        "- Nuevos nodos a crear (contenido exacto y tipo)\n"
        "- Posibles merges entre ramas\n"
        "- Ramas nuevas a explorar\n"
        "Sé específico y accionable. Responde en español."
    )
    prompt = f"{ctx}\n\n¿Qué debería hacer a continuación en la rama '{cur}'?"

    print(f"\n  {DIM('Sugerencias para:')} {CYAN(cur)}  {DIM('Modelo:')} {resolved}")
    print("  " + "─" * 60)
    _ollama_generate(prompt, model=resolved, system=system, stream=True)


def cmd_evolve(
    branch: Optional[str] = None,
    model: Optional[str] = None,
    n_nodes: int = 3,
    do_commit: bool = True,
) -> None:
    """Ask Ollama to generate N new nodes and optionally commit them."""
    resolved = _pick_model(model)
    if resolved is None:
        print(RED("❌ Ollama no disponible. Inicia con: ollama serve")); return

    conn = _connect()
    cur  = branch or _get_current_branch(conn)
    conn.close()

    ctx    = _build_graph_context(branch=cur, limit=12)
    system = (
        "Eres un generador de nodos cognitivos. Propones los siguientes nodos lógicos "
        f"para una trayectoria de pensamiento. Responde SOLO con un JSON array de {n_nodes} "
        "objetos, sin texto extra:\n"
        '[{"content": "...", "type": "concept|memory|decision|hypothesis", "weight": 0.0-1.0}]'
    )
    prompt = f"{ctx}\n\nGenera los próximos {n_nodes} nodos para la rama '{cur}'."

    print(f"\n  {DIM('Evolución de:')} {CYAN(cur)}  {DIM('Modelo:')} {resolved}  {DIM(f'({n_nodes} nodos)')}")
    print("  " + "─" * 60)

    raw = _ollama_generate(prompt, model=resolved, system=system, stream=False)
    if not raw:
        return

    print(f"  {DIM('LLM response:')}")
    print(f"  {raw[:200]}{'…' if len(raw) > 200 else ''}")
    print()

    json_match = re.search(r'\[.*?\]', raw, re.DOTALL)
    if not json_match:
        print(YELLOW("⚠  No se encontró JSON en la respuesta."))
        return

    try:
        proposed = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(YELLOW(f"⚠  JSON inválido: {e}")); return

    committed = []
    for node_def in proposed[:n_nodes]:
        content = str(node_def.get("content", "")).strip()
        ntype   = str(node_def.get("type", "concept")).strip()
        weight  = float(node_def.get("weight", 0.6))
        if not content:
            continue
        nid = (
            cmd_commit(content, branch=cur, ntype=ntype, weight=weight,
                       metadata={"source": "ollama_evolve", "model": resolved})
            if do_commit else None
        )
        committed.append((content, ntype, weight, nid))

    suffix = " y guardados" if do_commit else f"  {DIM('(sin --commit, no guardados)')}"
    print(f"  {GREEN(f'✅ {len(committed)} nodo(s) generados')}{suffix}")
    for content, ntype, weight, nid in committed:
        nid_str = f"  {CYAN(nid)}" if nid else ""
        print(f"  {YELLOW(ntype)}({weight:.1f}){nid_str}  {content[:70]}")


def cmd_ollama_status() -> None:
    """Show Ollama availability and loaded models."""
    available, models = _ollama_available()
    if not available:
        print(RED("  ○ Ollama no disponible") + f"  {DIM('ollama serve')}")
        return
    print(GREEN("  ● Ollama activo") + f"  {DIM(_OLLAMA_URL)}")
    if models:
        print(f"  Modelos disponibles ({len(models)}):")
        for m in models:
            print(f"    - {CYAN(m)}")
    else:
        print(f"  Sin modelos instalados. Prueba: {DIM('ollama pull llama3')}")
