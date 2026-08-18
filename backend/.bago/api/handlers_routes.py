"""handlers_routes.py \u2014 GET /routes para el bridge BAGO.

Devuelve la tabla viva de rutas del bridge (metodo, path, handler,
si es patron dinamico). Pensado como healthcheck/documentacion
para clientes HTTP y para otros agentes que aterricen en el bridge
sin saber que endpoints existen.

Requiere el header de auth del bridge (X-Bago-Token por defecto).
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    from api_routes import all_routes, api_prefixes, auth_header

    payload = {
        "ok": True,
        "routes": all_routes(),
        "count": len(all_routes()),
        "api_prefixes": list(api_prefixes()),
        "auth": auth_header(),
        "note": "Fuente: api_dispatch.ROUTE_META + patrones dinamicos.",
    }
    send_json(handler, 200, payload)