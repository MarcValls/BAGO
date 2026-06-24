"""api_dispatch.py \u2014 HTTP routing for the BAGO API bridge.

Single place where `do_GET` and `do_POST` decide which handler module
runs. Handlers live in `handlers_<domain>.py` and are called as
`module.handle(self)` where `self` is the BagoAPIHandler instance.

Adding a new endpoint = adding one entry to `GET_ROUTES` or `POST_ROUTES`.
No need to edit bridge.py.

This module also defines `API_PREFIXES` (the set of paths the bridge
treats as API rather than static). Keep it in sync with the actual routes
or the 404 short-circuit in bridge.py will misbehave.
"""

from __future__ import annotations

import importlib
from typing import Callable, Tuple


def _call(mod_name: str, fn_name: str, *extra):
    """Lazy import + call. Re-imports each call so monkey-patching handlers
    in tests works without reloading the dispatch table.

    Extra positional args are passed to the handler after `handler`.
    Use this for handlers with signatures like `handle(handler, provider)`.
    """
    def _inner(handler, *args):
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, fn_name)
        if extra:
            return fn(handler, *extra, *args)
        return fn(handler, *args)
    return _inner


def _post(mod_name: str, fn_name: str):
    """Build a POST handler closure that ignores URL/body args and calls
    `fn_name(handler, body)`. Kept as a top-level helper so _from_meta
    can reference it from below.
    """
    def _inner(handler, body):
        mod = importlib.import_module(mod_name)
        return getattr(mod, fn_name)(handler, body)
    return _inner


# Single source of truth for static routes.
# (method, path, handler_module, handler_fn). Order is preserved; route
# dispatch iterates in this order so callers see deterministic behaviour.
# Dynamic patterns (/models/<provider>, /files/read/<path>, /router/toggle/<key>)
# live separately in DYNAMIC_ROUTES below.
ROUTE_META: tuple = (
    # GET routes
    ("GET",  "/status",              "handlers_status",     "handle"),
    ("GET",  "/session",             "handlers_session",    "handle"),
    ("GET",  "/history",             "handlers_history",    "handle"),
    ("GET",  "/providers",           "handlers_providers",  "handle"),
    ("GET",  "/memory/list",         "handlers_memory",     "handle"),
    ("GET",  "/schedule/list",       "handlers_schedule",   "handle"),
    ("GET",  "/subagents/catalogue", "handlers_subagents",  "handle"),
    ("GET",  "/menu",                "handlers_menu",       "handle"),
    ("GET",  "/catalog/status",      "handlers_catalog",    "handle_status"),
    ("GET",  "/simulation/status",   "handlers_simulation", "handle_status"),
    ("GET",  "/simulation/events",   "handlers_simulation", "handle_events"),
    ("GET",  "/rl/status",           "handlers_rl",         "handle_status"),
    ("GET",  "/files/list",          "handlers_files",      "handle_list"),
    ("GET",  "/router/list",         "handlers_router",     "handle"),
    ("GET",  "/routes",              "handlers_routes",     "handle"),
    # POST routes
    ("POST", "/chat",                "handlers_chat",       "handle"),
    ("POST", "/chat/stream",         "handlers_chat_stream", "handle"),
    ("POST", "/command",             "handlers_command",    "handle"),
    ("POST", "/switch",              "handlers_switch",     "handle"),
    ("POST", "/catalog/config",      "handlers_catalog",    "handle_config"),
    ("POST", "/simulation/config",   "handlers_simulation", "handle_config"),
    ("POST", "/rl/shadow",           "handlers_rl",         "handle_shadow"),
    ("POST", "/router/auto",         "handlers_router",     "handle_auto"),
)


def _build_static_routes() -> dict:
    """Derive GET_ROUTES / POST_ROUTES from ROUTE_META so the dispatch
    table cannot diverge from the public metadata. Returns a combined
    dict keyed by path; callers filter by method.
    """
    out: dict = {}
    for method, path, mod_name, fn_name in ROUTE_META:
        if method == "GET":
            out[path] = _call(mod_name, fn_name)
        elif method == "POST":
            out[path] = _post(mod_name, fn_name)
    return out


_STATIC_ROUTES: dict = _build_static_routes()

GET_ROUTES: dict = {p: c for p, c in _STATIC_ROUTES.items() if any(m == "GET" and pp == p for m, pp, _, _ in ROUTE_META)}
POST_ROUTES: dict = {p: c for p, c in _STATIC_ROUTES.items() if any(m == "POST" and pp == p for m, pp, _, _ in ROUTE_META)}


def resolve_get(handler, path: str) -> Tuple[bool, Callable | None]:
    """Return (matched, call) for a GET path. matched=False means 404."""
    if path in GET_ROUTES:
        return True, GET_ROUTES[path]
    if path.startswith("/models/"):
        provider = path[len("/models/"):]
        if provider:
            return True, _call("handlers_models", "handle", provider)
    if path.startswith("/files/read/"):
        file_path = path[len("/files/read/"):]
        return True, _call("handlers_files", "handle_read", file_path)
    return False, None


def resolve_post(handler, path: str, body: dict) -> Tuple[bool, Callable | None]:
    if path in POST_ROUTES:
        return True, POST_ROUTES[path]
    return False, None


def resolve_router(handler, path: str, body: dict) -> Tuple[bool, Callable | None]:
    """Pattern route: POST /router/toggle/<provider>/<model>.

    The key is in the URL, not the body, so we wrap the handler to
    ignore the body argument that do_POST passes in.
    """
    if path.startswith("/router/toggle/"):
        key = path[len("/router/toggle/"):]
        if key:
            mod = importlib.import_module("handlers_router")
            def _toggler(handler, body, _key=key):
                return mod.handle_toggle(handler, _key)
            return True, _toggler
    return False, None


API_PREFIXES = (
    "/status",
    "/session",
    "/history",
    "/providers",
    "/menu",
    "/models",
    "/chat",
    "/chat/stream",
    "/command",
    "/switch",
    "/catalog",
    "/simulation",
    "/rl",
    "/files",
    "/memory",
    "/schedule",
    "/subagents",
    "/router",
    "/routes",
)
