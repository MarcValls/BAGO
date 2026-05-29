"""bago.api.routes.embed — POST /api/embed"""

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
from ..models.schemas import EmbedRequest, EmbedResponse

router = APIRouter()


@router.post("/api/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest):
    """Genera embeddings usando el modelo especificado o el default.
    Delega a Ollama /api/embeddings internamente."""
    from ..server import get_bago
    bago = get_bago()

    model = req.model or bago.default_embedding_model
    t0 = time.perf_counter()
    try:
        result = bago.embed(model=model, input=req.input, options=req.options)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    elapsed = int((time.perf_counter() - t0) * 1e9)
    return EmbedResponse(
        model=model,
        embeddings=result.get("embeddings", []),
        total_duration=elapsed,
        load_duration=result.get("load_duration", 0),
        prompt_eval_count=result.get("prompt_eval_count", 0),
    )



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
