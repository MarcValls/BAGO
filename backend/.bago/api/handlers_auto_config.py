"""handlers_auto_config.py — Endpoints REST para /configure/auto/*

POST /configure/auto/start   — lanza los tests (background)
GET  /configure/auto/status  — estado del job en curso
POST /configure/auto/apply   — aplica la config generada al config del usuario
POST /configure/auto/cancel  — cancela el job en curso
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle_auto_start(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /configure/auto/start — body opcional: {"judge_provider": "copilot"|"ollama-cloud"}"""
    from api_serializers import send_json
    import auto_configurator

    judge_override = None
    jp = (body or {}).get("judge_provider")
    if jp in ("copilot", "ollama-cloud"):
        judge_override = (jp, "")

    result = auto_configurator.start_job(judge_override=judge_override)
    send_json(handler, 200 if result.get("ok") else 400, result)


def handle_auto_status(handler: "BaseHTTPRequestHandler") -> None:
    """GET /configure/auto/status — estado del job."""
    from api_serializers import send_json
    import auto_configurator
    send_json(handler, 200, auto_configurator.get_status())


def handle_auto_apply(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    """POST /configure/auto/apply — aplica la config generada."""
    from api_serializers import send_json
    import auto_configurator
    result = auto_configurator.apply_generated_config()
    send_json(handler, 200 if result.get("ok") else 400, result)


def handle_auto_cancel(handler: "BaseHTTPRequestHandler", body: dict | None = None) -> None:
    """POST /configure/auto/cancel — cancela el job en curso."""
    from api_serializers import send_json
    import auto_configurator
    result = auto_configurator.cancel_job()
    send_json(handler, 200 if result.get("ok") else 400, result)
