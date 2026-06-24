"""handlers_router.py \u2014 GET /router/list[?refresh=1] for the BAGO HTTP bridge.

Returns the model picker state for the current session. The picker is
populated from the SessionManager's adapter catalog (when available) or
from a hard-coded fallback list of BAGO-known local + cloud models.

GET /router/list         \u2014 returns current picker state with `selected`
                          flags from .bago_model_selection.json
GET /router/list?refresh=1 \u2014 re-pulls catalog and merges in saved selection
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import TYPE_CHECKING

_RUNTIME_DIR = Path(__file__).resolve().parents[1] / "chat"
if str(_RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNTIME_DIR))

if TYPE_CHECKING:
    from http.server import BaseHTTPRequestHandler


def _state_root(handler) -> Path:
    mgr = getattr(handler, "session_mgr", None)
    if mgr is not None and hasattr(mgr, "state_root"):
        return Path(mgr.state_root)
    return Path.home() / ".bago" / "state"


def handle(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json
    import urllib.parse as _up

    from repl_model_router import (
        Selection, discover_models, load_selection, render_picker,
        render_selection, save_selection,
    )

    q = _up.parse_qs(_up.urlparse(handler.path).query)
    refresh = q.get("refresh", ["0"])[0] in ("1", "true", "yes")

    state = _state_root(handler)
    sel = load_selection(state)
    if refresh or not sel.entries:
        mgr = getattr(handler, "session_mgr", None)
        sel = Selection(entries=discover_models(mgr), auto_switch=sel.auto_switch)
        save_selection(state, sel)

    serialised = [
        {
            "provider": e.provider,
            "model_id": e.model_id,
            "wire_name": e.wire_name,
            "context_tokens": e.context_tokens,
            "best_for": e.best_for,
            "available": e.available,
            "selected": e.selected,
            "key": e.key(),
        }
        for e in sel.entries
    ]
    send_json(handler, 200, {
        "entries": serialised,
        "selected_count": sum(1 for e in sel.entries if e.selected),
        "auto_switch": sel.auto_switch,
        "last_pick": sel.last_pick,
        "last_pick_at": sel.last_pick_at,
    })


def handle_toggle(handler: "BaseHTTPRequestHandler", key: str) -> None:
    from api_serializers import send_json

    from repl_model_router import (
        Selection, discover_models, load_selection, save_selection, toggle,
    )

    state = _state_root(handler)
    sel = load_selection(state)
    if not sel.entries:
        mgr = getattr(handler, "session_mgr", None)
        sel = Selection(entries=discover_models(mgr), auto_switch=sel.auto_switch)
    try:
        sel = toggle(sel, key)
    except KeyError as exc:
        send_json(handler, 404, {"error": str(exc)})
        return
    save_selection(state, sel)
    send_json(handler, 200, {
        "ok": True,
        "key": key,
        "selected_count": sum(1 for e in sel.entries if e.selected),
    })


def handle_auto(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    from api_serializers import send_json

    from repl_model_router import (
        load_selection, save_selection, set_auto_switch,
    )

    state = _state_root(handler)
    sel = load_selection(state)
    enabled = bool(body.get("enabled", True))
    sel = set_auto_switch(sel, enabled)
    save_selection(state, sel)
    send_json(handler, 200, {"ok": True, "auto_switch": enabled})
