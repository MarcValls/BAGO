"""handlers_interpretations.py — Interpretation entity endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _state(handler) -> Path:
    from api_state import resolve_state_root
    return Path(resolve_state_root(handler))


def _interpretations_dir(state: Path) -> Path:
    d = state / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _send(handler, code: int, payload: dict) -> None:
    from api_serializers import send_json
    send_json(handler, code, payload)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_input(text: str) -> str:
    return text.strip()


def _detect_intent(text: str) -> str:
    """Simple keyword-based intent detection."""
    lower = text.lower()
    if any(k in lower for k in ("create", "new", "add", "make")):
        return "create_resource"
    if any(k in lower for k in ("delete", "remove", "drop")):
        return "delete_resource"
    if any(k in lower for k in ("update", "edit", "modify", "change")):
        return "update_resource"
    if any(k in lower for k in ("show", "list", "get", "find", "search")):
        return "query_resource"
    if any(k in lower for k in ("explain", "what", "how", "why")):
        return "explanation"
    if any(k in lower for k in ("test", "run", "execute", "check")):
        return "execution"
    return "general"


def _build_stages(interpretation_id: str, input_text: str) -> list[dict[str, Any]]:
    """Build the observable interpretation stages."""
    now = _now()
    stages = []

    # 1. input
    stages.append({
        "id": f"{interpretation_id}-input",
        "order": 0,
        "type": "input",
        "label": "Entrada",
        "summary": input_text[:120] + ("..." if len(input_text) > 120 else ""),
        "durationMs": None,
    })

    # 2. normalization
    normalized = _normalize_input(input_text)
    stages.append({
        "id": f"{interpretation_id}-normalization",
        "order": 1,
        "type": "normalization",
        "label": "Normalización",
        "summary": f"Texto normalizado ({len(normalized)} caracteres)",
        "evidence": [{"type": "normalized_text", "value": normalized}],
        "durationMs": None,
    })

    # 3. intent
    intent = _detect_intent(normalized)
    stages.append({
        "id": f"{interpretation_id}-intent",
        "order": 2,
        "type": "intent",
        "label": "Intención",
        "summary": f"Intención detectada: {intent}",
        "evidence": [{"type": "intent_signal", "value": intent}],
        "durationMs": None,
    })

    # 4. context (placeholder)
    stages.append({
        "id": f"{interpretation_id}-context",
        "order": 3,
        "type": "context",
        "label": "Contexto",
        "summary": "Contexto de sesión recuperado",
        "evidence": [{"type": "context_available", "value": False}],
        "durationMs": None,
    })

    # 5. constraints (placeholder)
    stages.append({
        "id": f"{interpretation_id}-constraints",
        "order": 4,
        "type": "constraints",
        "label": "Restricciones",
        "summary": "Sin restricciones explícitas",
        "durationMs": None,
    })

    # 6. routing
    stages.append({
        "id": f"{interpretation_id}-routing",
        "order": 5,
        "type": "routing",
        "label": "Routing",
        "summary": f"Destino: {intent}",
        "evidence": [{"type": "route_target", "value": intent}],
        "durationMs": None,
    })

    # 7. decision
    stages.append({
        "id": f"{interpretation_id}-decision",
        "order": 6,
        "type": "decision",
        "label": "Decisión",
        "summary": "Decisión de procesamiento completada",
        "durationMs": None,
    })

    # 8. output
    stages.append({
        "id": f"{interpretation_id}-output",
        "order": 7,
        "type": "output",
        "label": "Resultado",
        "summary": "Interpretación finalizada",
        "durationMs": None,
    })

    return stages


def _save_interpretation(state: Path, interpretation: dict[str, Any]) -> None:
    interpretations_dir = _interpretations_dir(state)
    fp = interpretations_dir / f"{interpretation['interpretationId']}.json"
    fp.write_text(__import__("json").dumps(interpretation, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_interpretation(state: Path, interpretation_id: str) -> dict[str, Any] | None:
    fp = _interpretations_dir(state) / f"{interpretation_id}.json"
    if not fp.exists():
        return None
    try:
        import json
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _list_interpretations(state: Path, limit: int = 20) -> list[dict[str, Any]]:
    interpretations_dir = _interpretations_dir(state)
    items = []
    for fp in interpretations_dir.glob("*.json"):
        try:
            items.append(__import__("json").loads(fp.read_text(encoding="utf-8")))
        except Exception:
            pass
    items.sort(key=lambda x: x.get("startedAt", ""), reverse=True)
    return items[:limit]


# ─── POST /interpretations ───────────────────────────────────────────────


def handle_post(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    state = _state(handler)
    input_text = str(body.get("input") or "").strip()
    if not input_text:
        _send(handler, 400, {"ok": False, "error": "El campo 'input' es obligatorio"})
        return

    interpretation_id = uuid.uuid4().hex[:16]
    started_at = _now()

    mgr = None
    agent_id = str(body.get("agentId") or "").strip() or None
    provider: str | None = None
    model: str | None = None
    try:
        from api_state import get_mgr
        mgr = get_mgr(handler)
        if mgr:
            provider = getattr(mgr, "provider", None) or None
            model = getattr(mgr, "model", None) or None
    except Exception:
        pass

    stages = _build_stages(interpretation_id, input_text)

    # Run interpretation through the reflexive interpreter if available
    final_output: str | None = None
    confidence: float | None = None
    if mgr and hasattr(mgr, "analyze_reflexive_turn"):
        try:
            analysis = dict(mgr.analyze_reflexive_turn(input_text))
            if isinstance(analysis, dict):
                final_output = analysis.get("report") or analysis.get("summary") or None
                confidence = float(analysis["confidence"]) if "confidence" in analysis else None
        except Exception:
            pass

    finished_at = _now()

    interpretation: dict[str, Any] = {
        "interpretationId": interpretation_id,
        "input": input_text,
        "stages": stages,
        "interpretedIntent": _detect_intent(input_text),
        "finalOutput": final_output,
        "confidence": confidence,
        "agentId": agent_id,
        "provider": provider,
        "model": model,
        "startedAt": started_at,
        "finishedAt": finished_at,
        "durationMs": 0,
    }

    # Calculate duration
    try:
        from datetime import datetime as dt
        start = dt.fromisoformat(started_at)
        end = dt.fromisoformat(finished_at)
        interpretation["durationMs"] = int((end - start).total_seconds() * 1000)
    except Exception:
        interpretation["durationMs"] = 0

    _save_interpretation(state, interpretation)

    _send(handler, 201, {"ok": True, "interpretation": interpretation})


# ─── GET /interpretations/:id ───────────────────────────────────────────


def handle_get(handler: "BaseHTTPRequestHandler", interpretation_id: str) -> None:
    state = _state(handler)
    interpretation = _load_interpretation(state, interpretation_id)
    if interpretation is None:
        _send(handler, 404, {"ok": False, "error": "Interpretación no encontrada"})
        return
    _send(handler, 200, {"ok": True, "interpretation": interpretation})


# ─── GET /interpretations ───────────────────────────────────────────────


def handle_list(handler: "BaseHTTPRequestHandler") -> None:
    from urllib.parse import parse_qs, urlparse
    state = _state(handler)
    parsed = urlparse(getattr(handler, "path", ""))
    query = parse_qs(parsed.query)
    try:
        limit = int((query.get("limit", ["20"])[0]))
    except (ValueError, TypeError):
        limit = 20
    limit = max(1, min(limit, 100))

    items = _list_interpretations(state, limit)
    _send(handler, 200, {
        "ok": True,
        "interpretations": items,
        "count": len(items),
    })
