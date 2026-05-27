"""bago.api.routes.generate — POST /api/generate"""

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
from fastapi import APIRouter, HTTPException
from ..models.schemas import GenerateRequest, GenerateResponse

router = APIRouter()


@router.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """Generate endpoint compatible con Ollama + extensiones BAGO.

    A diferencia de /api/chat, este endpoint no mantiene historial de sesion.
    Es una llamada puntual con routing automatico.
    """
    from ..server import get_bago
    bago = get_bago()

    model_name = req.model or bago.default_model
    provider_name = req.provider or ""

    if not provider_name:
        route = bago.route(req.prompt)
        provider_name = route["provider"]
        model_name = route["model"]

    messages = []
    if req.system:
        messages.append({"role": "system", "content": req.system})
    messages.append({"role": "user", "content": req.prompt})

    t0 = time.perf_counter()
    try:
        result = bago.chat(
            messages=messages,
            model=model_name,
            provider=provider_name,
            quality_guard=req.quality_guard if req.quality_guard is not None else True,
            context_escalation=False,
            max_switches=1,
            options=req.options,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    elapsed = int((time.perf_counter() - t0) * 1e9)

    return GenerateResponse(
        model=result.get("model", model_name),
        provider=result.get("provider", provider_name),
        response=result["content"],
        total_duration=elapsed,
        eval_count=result.get("eval_count", 0),
        switches=result.get("switches", 0),
        original_model=result.get("original_model", req.model),
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
