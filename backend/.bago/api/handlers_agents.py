"""handlers_agents.py — CRUD API for configurable agents (AgentFactory + AgentGateway)."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler

AGENTS_STATE_DIR = Path(".bago/state/agents")

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _is_safe_agent_id(agent_id: str) -> bool:
    return isinstance(agent_id, str) and bool(_SAFE_ID_RE.match(agent_id))


def _send(handler, code: int, payload: dict) -> None:
    from api_serializers import send_json
    send_json(handler, code, payload)


def _load_agents_registry() -> dict:
    AGENTS_STATE_DIR.mkdir(parents=True, exist_ok=True)
    registry_path = AGENTS_STATE_DIR / "agents_registry.json"
    if registry_path.exists():
        try:
            return json.loads(registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"schema": 1, "agents": []}


def _save_agents_registry(data: dict) -> None:
    AGENTS_STATE_DIR.mkdir(parents=True, exist_ok=True)
    registry_path = AGENTS_STATE_DIR / "agents_registry.json"
    registry_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _agent_to_contract(agent_data: dict) -> dict:
    return {
        "id": agent_data["id"],
        "name": agent_data.get("name", ""),
        "description": agent_data.get("description", ""),
        "systemPrompt": agent_data.get("systemPrompt", ""),
        "model": agent_data.get("model", ""),
        "provider": agent_data.get("provider", ""),
        "temperature": agent_data.get("temperature", 0.7),
        "maxTokens": agent_data.get("maxTokens", 4096),
        "enabled": agent_data.get("enabled", True),
        "createdAt": agent_data.get("createdAt", ""),
        "updatedAt": agent_data.get("updatedAt", ""),
        "revision": agent_data.get("revision", "1"),
    }


def handle_get_list(handler: "BaseHTTPRequestHandler") -> None:
    registry = _load_agents_registry()
    agents = [_agent_to_contract(a) for a in registry.get("agents", [])]
    _send(handler, 200, {"ok": True, "agents": agents})


def handle_get(handler: "BaseHTTPRequestHandler", agent_id: str) -> None:
    if not _is_safe_agent_id(agent_id):
        _send(handler, 400, {"ok": False, "error": "Invalid agent id"})
        return
    registry = _load_agents_registry()
    for agent in registry.get("agents", []):
        if agent.get("id") == agent_id:
            _send(handler, 200, _agent_to_contract(agent))
            return
    _send(handler, 404, {"ok": False, "error": f"Agente '{agent_id}' no encontrado"})


def _generate_id() -> str:
    return uuid.uuid4().hex[:12]


def handle_post(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    name = str(body.get("name") or "").strip()
    if not name:
        _send(handler, 400, {"ok": False, "error": "'name' es obligatorio"})
        return
    registry = _load_agents_registry()
    existing = [a for a in registry["agents"] if a.get("name", "").lower() == name.lower()]
    if existing:
        _send(handler, 409, {"ok": False, "error": f"Ya existe un agente con nombre '{name}'", "code": "AGENT_NAME_CONFLICT"})
        return
    now = ""
    try:
        from datetime import datetime
        now = datetime.utcnow().isoformat() + "Z"
    except Exception:
        pass
    agent = {
        "id": _generate_id(),
        "name": name,
        "description": str(body.get("description") or ""),
        "systemPrompt": str(body.get("systemPrompt") or ""),
        "model": str(body.get("model") or ""),
        "provider": str(body.get("provider") or ""),
        "temperature": float(body.get("temperature", 0.7)),
        "maxTokens": int(body.get("maxTokens", 4096)),
        "enabled": bool(body.get("enabled", True)),
        "createdAt": now,
        "updatedAt": now,
        "revision": "1",
    }
    registry.setdefault("agents", []).append(agent)
    _save_agents_registry(registry)
    _send(handler, 201, _agent_to_contract(agent))


def handle_put(handler: "BaseHTTPRequestHandler", body: dict, agent_id: str) -> None:
    if not _is_safe_agent_id(agent_id):
        _send(handler, 400, {"ok": False, "error": "Invalid agent id"})
        return
    registry = _load_agents_registry()
    for i, agent in enumerate(registry.get("agents", [])):
        if agent.get("id") == agent_id:
            incoming_revision = str(body.get("revision") or "")
            if incoming_revision and agent.get("revision") and incoming_revision != str(agent.get("revision")):
                _send(handler, 409, {
                    "ok": False,
                    "error": "Conflicto de revisión: el agente fue modificado por otro proceso",
                    "code": "AGENT_REVISION_CONFLICT",
                    "currentRevision": agent.get("revision"),
                })
                return
            now = ""
            try:
                from datetime import datetime
                now = datetime.utcnow().isoformat() + "Z"
            except Exception:
                pass
            registry["agents"][i] = {
                **agent,
                "name": str(body.get("name", agent.get("name", ""))),
                "description": str(body.get("description", agent.get("description", ""))),
                "systemPrompt": str(body.get("systemPrompt", agent.get("systemPrompt", ""))),
                "model": str(body.get("model", agent.get("model", ""))),
                "provider": str(body.get("provider", agent.get("provider", ""))),
                "temperature": float(body.get("temperature", agent.get("temperature", 0.7))),
                "maxTokens": int(body.get("maxTokens", agent.get("maxTokens", 4096))),
                "enabled": bool(body.get("enabled", agent.get("enabled", True))),
                "updatedAt": now,
                "revision": str(int(agent.get("revision", "1")) + 1),
            }
            _save_agents_registry(registry)
            _send(handler, 200, _agent_to_contract(registry["agents"][i]))
            return
    _send(handler, 404, {"ok": False, "error": f"Agente '{agent_id}' no encontrado"})


def handle_delete(handler: "BaseHTTPRequestHandler", agent_id: str) -> None:
    if not _is_safe_agent_id(agent_id):
        _send(handler, 400, {"ok": False, "error": "Invalid agent id"})
        return
    registry = _load_agents_registry()
    original_len = len(registry.get("agents", []))
    registry["agents"] = [a for a in registry.get("agents", []) if a.get("id") != agent_id]
    if len(registry["agents"]) == original_len:
        _send(handler, 404, {"ok": False, "error": f"Agente '{agent_id}' no encontrado"})
        return
    _save_agents_registry(registry)
    _send(handler, 204, {})


def handle_duplicate(handler: "BaseHTTPRequestHandler", agent_id: str) -> None:
    if not _is_safe_agent_id(agent_id):
        _send(handler, 400, {"ok": False, "error": "Invalid agent id"})
        return
    registry = _load_agents_registry()
    for agent in registry.get("agents", []):
        if agent.get("id") == agent_id:
            now = ""
            try:
                from datetime import datetime
                now = datetime.utcnow().isoformat() + "Z"
            except Exception:
                pass
            copy = {**agent}
            copy["id"] = _generate_id()
            copy["name"] = agent.get("name", "") + " (copy)"
            copy["createdAt"] = now
            copy["updatedAt"] = now
            copy["revision"] = "1"
            registry.setdefault("agents", []).append(copy)
            _save_agents_registry(registry)
            _send(handler, 201, _agent_to_contract(copy))
            return
    _send(handler, 404, {"ok": False, "error": f"Agente '{agent_id}' no encontrado"})


def handle_test(handler: "BaseHTTPRequestHandler", agent_id: str) -> None:
    """Run a no-op test of the agent configuration — validates model/provider resolution."""
    if not _is_safe_agent_id(agent_id):
        _send(handler, 400, {"ok": False, "error": "Invalid agent id"})
        return
    registry = _load_agents_registry()
    for agent in registry.get("agents", []):
        if agent.get("id") == agent_id:
            model = agent.get("model", "")
            provider = agent.get("provider", "")
            errors = []
            if not model:
                errors.append("Modelo no especificado")
            if not provider:
                errors.append("Provider no especificado")
            _send(handler, 200, {
                "ok": True,
                "agentId": agent_id,
                "success": len(errors) == 0,
                "errors": errors,
                "message": "Test completado sin errores" if not errors else "Errores encontrados",
            })
            return
    _send(handler, 404, {"ok": False, "error": f"Agente '{agent_id}' no encontrado"})
