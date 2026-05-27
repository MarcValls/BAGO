"""bago.api.routes.bago — BAGO-only endpoints: /api/route, /api/health,
/api/providers, /api/escalate, /api/session
"""

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
from ..models.schemas import (
    RouteRequest, RouteResponse,
    HealthResponse, ProviderHealth,
    EscalateRequest, EscalateResponse,
    SessionCreateRequest, SessionInfo, SessionResponse,
)

router = APIRouter()


@router.post("/api/route", response_model=RouteResponse)
async def route(req: RouteRequest):
    """Preview del routing: dado un prompt, devuelve que provider/modelo se elegira
    sin ejecutar la llamada. Util para debugging y UI."""
    from ..server import get_bago
    bago = get_bago()

    route_info = bago.route(req.prompt, model=req.model, provider=req.provider)
    fallback_chain = bago.fallback_chain(route_info.get("model", ""))

    return RouteResponse(
        provider=route_info.get("provider", ""),
        model=route_info.get("model", ""),
        wire_name=route_info.get("wire_name", ""),
        reason=route_info.get("reason", ""),
        rule_id=route_info.get("rule_id", ""),
        fallback_available=fallback_chain,
        quality_guard=route_info.get("quality_guard", True),
        context_escalation=route_info.get("context_escalation", True),
    )


@router.post("/api/health", response_model=HealthResponse)
async def health():
    """Health completo: providers, modelos disponibles, latencia, score global."""
    from ..server import get_bago
    bago = get_bago()

    providers = []
    total_score = 0
    n_providers = 0

    for prov_name, prov_data in bago.providers().items():
        t0 = time.perf_counter()
        try:
            available = bago.check_provider(prov_name)
            latency = (time.perf_counter() - t0) * 1000
            n_models = len(prov_data.get("models", {}))
            if available:
                total_score += 100
            else:
                total_score += 20
            providers.append(ProviderHealth(
                name=prov_name, available=available,
                models=n_models, latency_ms=round(latency, 1),
            ))
        except Exception as e:
            providers.append(ProviderHealth(
                name=prov_name, available=False, error=str(e),
            ))
            total_score += 0
        n_providers += 1

    score = int(total_score / max(n_providers, 1))
    return HealthResponse(
        score=score,
        providers=providers,
        version=bago.version,
    )


@router.get("/api/providers")
async def providers():
    """Lista providers con estado y modelos."""
    from ..server import get_bago
    bago = get_bago()
    return bago.providers()


@router.post("/api/escalate", response_model=EscalateResponse)
async def escalate(req: EscalateRequest):
    """Fuerza escalado a cloud para una sesion activa."""
    from ..server import get_bago
    bago = get_bago()

    result = bago.escalate(
        session_id=req.session_id,
        target_provider=req.target_provider,
        target_model=req.target_model,
    )
    return EscalateResponse(
        provider=result.get("provider", ""),
        model=result.get("model", ""),
        reason=result.get("reason", ""),
    )


@router.post("/api/session", response_model=SessionResponse)
async def create_session(req: SessionCreateRequest):
    """Crea o recupera una sesion de chat BAGO."""
    from ..server import get_bago
    bago = get_bago()

    sess = bago.create_session(
        model=req.model,
        provider=req.provider,
        system=req.system,
    )
    return SessionResponse(
        session=SessionInfo(
            id=sess.get("id", ""),
            provider=sess.get("provider", ""),
            model=sess.get("model", ""),
            switches=sess.get("switches", 0),
            messages=sess.get("message_count", 0),
            created_at=sess.get("created_at", ""),
        )
    )


@router.get("/api/ps")
async def ps():
    """Lista modelos actualmente cargados en memoria (Ollama + sesiones BAGO)."""
    from ..server import get_bago
    bago = get_bago()
    return bago.running_models()



def _run_tests() -> int:
    """Self-test stub: verifies module imports."""
    print(__file__ + " --test: PASS (imports OK)")
    return 0


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
