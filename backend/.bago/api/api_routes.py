"""api_routes.py \u2014 Indice vivo de rutas del bridge BAGO.

Fuente de verdad: `api_dispatch.ROUTE_META` (estaticas) y
`api_dispatch.DYNAMIC_ROUTE_META` (patrones). Sin regex sobre codigo fuente
ni closure walking: ambas declaran `(method, path, mod, fn)` explicitamente.

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


def all_routes() -> List[RouteEntry]:
    """Lista completa de rutas del bridge (estaticas + dinamicas)."""
    from api_dispatch import DYNAMIC_ROUTE_META, ROUTE_META
    out: List[RouteEntry] = []
    for method, path, mod_name, fn_name in ROUTE_META:
        out.append({
            "method": method,
            "path": path,
            "handler_module": mod_name,
            "handler_fn": fn_name,
            "pattern": "<" in path,
        })
    for method, path, mod_name, fn_name in DYNAMIC_ROUTE_META:
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
