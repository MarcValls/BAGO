from __future__ import annotations

from typing import Any


def cmd_memory(mgr: Any, engine: Any, args: list[str]) -> dict:
    """Gestiona la base de conocimiento: /memory [list|search|add|delete|hybrid-add|hybrid-search]."""
    if not args or args[0] == "list":
        recent = mgr.knowledge.list_recent(limit=10)
        if not recent:
            return {"ok": True, "message": "No hay recuerdos almacenados."}
        lines = []
        for r in recent:
            content = " ".join(str(r.get("content", "")).split())
            snippet = content if len(content) <= 100 else content[:99] + "…"
            lines.append(
                f"  {r['id']:3} | {r['created_at'][:19]} | {r.get('source_session') or '—':<16} | {snippet}"
            )
        return {"ok": True, "message": f"Recuerdos recientes ({len(recent)}):\n" + "\n".join(lines)}
    if args[0] == "search" and len(args) >= 2:
        query = " ".join(args[1:])
        results = mgr.knowledge.search(query, limit=5)
        if not results:
            return {"ok": True, "message": f"No se encontraron recuerdos para '{query}'."}
        lines = [f"  • {r['content'][:100]}... (sesión: {r['source_session']})" for r in results]
        return {"ok": True, "message": f"Resultados para '{query}':\n" + "\n".join(lines)}
    if args[0] == "add" and len(args) >= 2:
        content = " ".join(args[1:])
        mid = mgr.knowledge.add(content, source_session=mgr.session_id)
        return {"ok": True, "message": f"✓ Recuerdo añadido (ID: {mid})."}
    if args[0] == "hybrid-add" and len(args) >= 2:
        content = " ".join(args[1:])
        result = mgr.memory_add_hybrid(content)
        return {
            "ok": True,
            "message": (
                f"✓ Recuerdo híbrido añadido (ID: {result['memory_id']}, "
                f"embedding: {result['embedding_id']})."
            ),
        }
    if args[0] == "hybrid-search" and len(args) >= 2:
        query = " ".join(args[1:])
        results = mgr.memory_search_hybrid(query, limit=5)
        if not results:
            return {"ok": True, "message": f"No hay resultados híbridos para '{query}'."}
        lines = [
            f"  • score={r['score']:.3f} | memoria {r['memory_id']} | {r['content'][:80]}..."
            for r in results
        ]
        return {"ok": True, "message": f"Resultados híbridos para '{query}':\n" + "\n".join(lines)}
    if args[0] == "delete" and len(args) >= 2:
        try:
            mid = int(args[1])
            ok = mgr.knowledge.delete(mid)
            if ok:
                return {"ok": True, "message": f"✓ Recuerdo {mid} eliminado."}
            return {"ok": False, "message": f"No se encontró el recuerdo {mid}."}
        except ValueError:
            return {"ok": False, "message": "Uso: /memory delete <id>"}
    return {
        "ok": False,
        "message": (
            "Uso: /memory [list|search <query>|add <contenido>|hybrid-add <contenido>|"
            "hybrid-search <query>|delete <id>]"
        ),
    }
