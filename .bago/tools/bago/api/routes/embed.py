"""bago.api.routes.embed — POST /api/embed"""

from __future__ import annotations

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
