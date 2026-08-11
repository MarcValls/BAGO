"""handlers_agents.py — CRUD endpoints for persistent Agent configs."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _state(handler) -> Path:
    from api_state import resolve_state_root
    return Path(resolve_state_root(handler))


def _agents_dir(state: Path) -> Path:
    d = state / "agents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_agents(state: Path) -> list[dict[str, Any]]:
    agents_dir = _agents_dir(state)
    agents = []
    for fp in agents_dir.glob("*.json"):
        try:
            agents.append(json.loads(fp.read_text(encoding="utf-8")))
        except Exception:
            pass
    agents.sort(key=lambda a: a.get("name", "").lower())
    return agents


def _save_agent(state: Path, agent: dict[str, Any]) -> None:
    agents_dir = _agents_dir(state)
    fp = agents_dir / f"{agent['id']}.json"
    fp.write_text(json.dumps(agent, ensure_ascii=False, indent=2), encoding="utf-8")


def _send(handler, code: int, payload: dict) -> None:
    from api_serializers import send_json
    send_json(handler, code, payload)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _agent_to_config(agent: dict[str, Any]) -> dict[str, Any]:
    """Strip runtime-only fields before returning to client."""
    return {k: v for k, v in agent.items() if k != "_runtime"}


# ─── GET /agents ─────────────────────────────────────────────────────────


def handle_list(handler: "BaseHTTPRequestHandler") -> None:
    state = _state(handler)
    agents = _load_agents(state)
    _send(handler, 200, {
        "ok": True,
        "agents": [_agent_to_config(a) for a in agents],
        "count": len(agents),
    })


# ─── GET /agents/:id ────────────────────────────────────────────────────


def _agent_by_id(state: Path, agent_id: str) -> dict[str, Any] | None:
    fp = _agents_dir(state) / f"{agent_id}.json"
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None


def handle_get(handler: "BaseHTTPRequestHandler", agent_id: str) -> None:
    state = _state(handler)
    agent = _agent_by_id(state, agent_id)
    if agent is None:
        _send(handler, 404, {"ok": False, "error": "Agente no encontrado"})
        return
    _send(handler, 200, {"ok": True, "agent": _agent_to_config(agent)})


# ─── POST /agents ────────────────────────────────────────────────────────


def handle_post(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    state = _state(handler)

    name = str(body.get("name") or "").strip()
    if not name:
        _send(handler, 400, {"ok": False, "error": "El campo 'name' es obligatorio"})
        return

    agent_id = str(body.get("id") or uuid.uuid4().hex[:12])
    existing = _agent_by_id(state, agent_id)
    if existing is not None:
        _send(handler, 409, {"ok": False, "error": "Ya existe un agente con ese id"})
        return

    now = _now()
    agent: dict[str, Any] = {
        "id": agent_id,
        "name": name,
        "description": str(body.get("description") or "").strip() or None,
        "systemPrompt": str(body.get("systemPrompt") or "").strip(),
        "provider": str(body.get("provider") or "").strip() or None,
        "model": str(body.get("model") or "").strip() or None,
        "temperature": float(body["temperature"]) if "temperature" in body else None,
        "maxTokens": int(body["maxTokens"]) if "maxTokens" in body else None,
        "enabled": bool(body.get("enabled", True)),
        "revision": 1,
        "createdAt": now,
        "updatedAt": now,
        "_runtime": {
            "available": False,
            "configurationValid": False,
            "effectiveProvider": None,
            "effectiveModel": None,
            "errors": [],
        },
    }

    _save_agent(state, agent)
    _send(handler, 201, {"ok": True, "agent": _agent_to_config(agent)})


# ─── PUT /agents/:id ────────────────────────────────────────────────────


def handle_put(handler: "BaseHTTPRequestHandler", agent_id: str, body: dict) -> None:
    state = _state(handler)
    agent = _agent_by_id(state, agent_id)
    if agent is None:
        _send(handler, 404, {"ok": False, "error": "Agente no encontrado"})
        return

    client_revision = int(body.get("revision", 0))
    if client_revision != agent["revision"]:
        _send(handler, 409, {
            "ok": False,
            "error": "AGENT_REVISION_CONFLICT",
            "message": "El agente ha cambiado desde que lo abriste.",
            "serverRevision": agent["revision"],
            "serverAgent": _agent_to_config(agent),
        })
        return

    for field in ("name", "description", "systemPrompt", "provider", "model",
                  "temperature", "maxTokens", "enabled"):
        if field in body:
            value = body[field]
            if field in ("temperature",):
                value = float(value) if value is not None else None
            elif field in ("maxTokens",):
                value = int(value) if value is not None else None
            elif field == "enabled":
                value = bool(value)
            elif field in ("description", "provider", "model"):
                value = str(value).strip() if value else None
            else:
                value = str(value).strip() if value else ""
            agent[field] = value

    agent["revision"] += 1
    agent["updatedAt"] = _now()
    _save_agent(state, agent)
    _send(handler, 200, {"ok": True, "agent": _agent_to_config(agent)})


# ─── DELETE /agents/:id ─────────────────────────────────────────────────


def handle_delete(handler: "BaseHTTPRequestHandler", agent_id: str) -> None:
    state = _state(handler)
    agent = _agent_by_id(state, agent_id)
    if agent is None:
        _send(handler, 404, {"ok": False, "error": "Agente no encontrado"})
        return

    fp = _agents_dir(state) / f"{agent_id}.json"
    fp.unlink(missing_ok=True)
    _send(handler, 200, {"ok": True, "deleted": agent_id})


# ─── POST /agents/:id/test ───────────────────────────────────────────────


def handle_test(handler: "BaseHTTPRequestHandler", agent_id: str, body: dict) -> None:
    state = _state(handler)
    agent = _agent_by_id(state, agent_id)
    if agent is None:
        _send(handler, 404, {"ok": False, "error": "Agente no encontrado"})
        return

    mgr = None
    try:
        from api_state import get_mgr
        mgr = get_mgr(handler)
    except Exception:
        pass

    start = datetime.now(timezone.utc)
    test_input = str(body.get("input") or "Hello, respond with OK if you can read this.")[:500]

    if mgr is None or not hasattr(mgr, "adapters"):
        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        _send(handler, 200, {
            "ok": True,
            "success": False,
            "agentId": agent_id,
            "durationMs": duration_ms,
            "error": "SessionManager no disponible para test",
        })
        return

    try:
        adapter = mgr.adapters.get(agent.get("provider", ""))
        if adapter is None:
            raise ValueError(f"Provider {agent.get('provider')} no disponible")

        model = agent.get("model") or "unknown"
        messages = [{"role": "user", "content": test_input}]
        response = adapter.chat(model=model, messages=messages)

        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        output = str(response.get("content") or response.get("message", {}).get("content", ""))
        _send(handler, 200, {
            "ok": True,
            "success": True,
            "agentId": agent_id,
            "provider": agent.get("provider"),
            "model": model,
            "durationMs": duration_ms,
            "output": output[:2000],
        })
    except Exception as exc:
        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        _send(handler, 200, {
            "ok": True,
            "success": False,
            "agentId": agent_id,
            "provider": agent.get("provider"),
            "model": agent.get("model"),
            "durationMs": duration_ms,
            "error": str(exc),
        })
