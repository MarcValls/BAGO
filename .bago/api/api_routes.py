"""api_routes.py \u2014 Indice vivo de rutas del bridge BAGO.

Fuente de verdad: `api_dispatch.ROUTE_META` (estaticas) + lista local
de patrones dinamicos. Sin regex sobre codigo fuente, sin closure
walking: ROUTE_META ya declara `(method, path, mod, fn)` explicitamente.

Consumidores:
- `bago api list-routes` (offline)
- `GET /routes` (online, autenticado)
"""

from __future__ import annotations

from typing import Dict, List, TypedDict


class RouteEntry(TypedDict):
    method: str
    path: str
    handler_module: str
    handler_fn: str
    pattern: bool


# Patrones dinamicos que viven en `resolve_get/post/router()`. Mantener
# en sync con el codigo de dispatch (no hay reflexion posible aqui).
_DYNAMIC_PATTERNS: tuple = (
    ("GET",  "/models/<provider>",          "handlers_models",  "handle"),
    ("GET",  "/files/read/<path:filepath>", "handlers_files",   "handle_read"),
    ("POST", "/router/toggle/<key>",        "handlers_router",  "handle_toggle"),
)


def all_routes() -> List[RouteEntry]:
    """Lista completa de rutas del bridge (estaticas + dinamicas)."""
    from api_dispatch import ROUTE_META
    out: List[RouteEntry] = []
    for method, path, mod_name, fn_name in ROUTE_META:
        out.append({
            "method": method,
            "path": path,
            "handler_module": mod_name,
            "handler_fn": fn_name,
            "pattern": "<" in path,
        })
    for method, path, mod_name, fn_name in _DYNAMIC_PATTERNS:
        out.append({
            "method": method,
            "path": path,
            "handler_module": mod_name,
            "handler_fn": fn_name,
            "pattern": True,
        })
    out.sort(key=lambda r: (r["method"], r["path"]))
    return out


def api_prefixes() -> tuple:
    """Re-expone `api_dispatch.API_PREFIXES`."""
    from api_dispatch import API_PREFIXES
    return API_PREFIXES


def auth_header() -> str:
    """Header canonico para autenticar contra el bridge."""
    return "X-Bago-Token"


def by_method(method: str) -> List[RouteEntry]:
    return [r for r in all_routes() if r["method"] == method.upper()]


def patterns_only() -> List[RouteEntry]:
    return [r for r in all_routes() if r["pattern"]]


def static_routes() -> List[RouteEntry]:
    return [r for r in all_routes() if not r["pattern"]]