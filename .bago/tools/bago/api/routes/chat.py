"""bago.api.routes.chat — POST /api/chat"""

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

import time
import json
from fastapi import APIRouter, HTTPException
from ..models.schemas import ChatRequest, ChatResponse, ChatMessage

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Chat endpoint compatible con Ollama + extensiones BAGO.

    BAGO extensions:
    - provider: fuerza provider ("ollama-local", "copilot", "codex")
    - quality_guard: activa/desactiva deteccion de basura y re-escalado
    - context_escalation: escala a cloud cuando se satura contexto
    - max_switches: limite de switches de provider por sesion
    """
    from ..server import get_bago
    bago = get_bago()

    model_name = req.model or bago.default_model
    provider_name = req.provider or ""

    # Route: si no hay provider explicito, usar auto-routing
    if not provider_name:
        route = bago.route(req.messages[-1].content if req.messages else "")
        provider_name = route["provider"]
        model_name = route.get("wire_name", route["model"])

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    # Inject system prompt
    system = req.system or ""
    if system:
        messages.insert(0, {"role": "system", "content": system})

    t0 = time.perf_counter()
    try:
        result = bago.chat(
            messages=messages,
            model=model_name,
            provider=provider_name,
            quality_guard=req.quality_guard if req.quality_guard is not None else True,
            context_escalation=req.context_escalation if req.context_escalation is not None else True,
            max_switches=req.max_switches or 3,
            options=req.options,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    elapsed = int((time.perf_counter() - t0) * 1e9)

    return ChatResponse(
        model=result.get("model", model_name),
        provider=result.get("provider", provider_name),
        message=ChatMessage(role="assistant", content=result["content"]),
        total_duration=elapsed,
        eval_count=result.get("eval_count", 0),
        eval_duration=result.get("eval_duration", 0),
        load_duration=result.get("load_duration", 0),
        prompt_eval_count=result.get("prompt_eval_count", 0),
        prompt_eval_duration=result.get("prompt_eval_duration", 0),
        switches=result.get("switches", 0),
        original_model=result.get("original_model", req.model),
        original_provider=result.get("original_provider", ""),
        route_reason=result.get("route_reason", ""),
    )



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
