"""GET /subagents/catalogue backed by the canonical roles manifest."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

_ROLES_DIR = Path(__file__).resolve().parents[1] / "roles"
_MANIFEST_PATH = _ROLES_DIR / "manifest.json"

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    try:
        manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        roles = manifest.get("roles", {})
        if not isinstance(roles, dict):
            raise ValueError("manifest.roles debe ser un objeto")
        agents = []
        for role_id, raw in roles.items():
            if not isinstance(raw, dict) or str(raw.get("status", "active")) != "active":
                continue
            relative_file = str(raw.get("file", "")).strip()
            agents.append({
                "id": str(role_id),
                "name": str(raw.get("name") or role_id),
                "family": str(raw.get("family") or "unknown"),
                "description": str(raw.get("description") or "Rol operativo de BAGO"),
                "version": str(raw.get("version") or manifest.get("version") or "unknown"),
                "tools": [str(tool) for tool in raw.get("tools", []) if str(tool).strip()],
                "source": relative_file,
                "available": bool(relative_file and (_ROLES_DIR / relative_file).is_file()),
            })
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        send_json(handler, 503, {"ok": False, "error": f"catálogo de roles no disponible: {exc}"})
        return

    agents.sort(key=lambda agent: (agent["family"], agent["name"].lower()))
    send_json(handler, 200, {
        "ok": True,
        "agents": agents,
        "count": len(agents),
        "families": manifest.get("families", {}),
        "version": manifest.get("version", "unknown"),
        "source": ".bago/roles/manifest.json",
    })
