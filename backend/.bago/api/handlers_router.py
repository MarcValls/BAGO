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
    from api_state import resolve_state_root
    return resolve_state_root(handler)


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
    from event_bus import emit

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
    selected_count = sum(1 for e in sel.entries if e.selected)
    send_json(handler, 200, {
        "ok": True,
        "key": key,
        "selected_count": selected_count,
    })
    emit("router.toggled", {
        "key": key,
        "selected_count": selected_count,
    })


def handle_auto(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    from api_serializers import send_json
    from event_bus import emit

    from repl_model_router import (
        load_selection, save_selection, set_auto_switch,
    )

    state = _state_root(handler)
    sel = load_selection(state)
    enabled = bool(body.get("enabled", True))
    sel = set_auto_switch(sel, enabled)
    save_selection(state, sel)
    send_json(handler, 200, {"ok": True, "auto_switch": enabled})
    emit("router.auto_changed", {"enabled": enabled})


def _policy_payload(handler) -> dict:
    from repl_model_router import discover_models, load_selection

    state = _state_root(handler)
    sel = load_selection(state)
    mgr = getattr(handler, "session_mgr", None)
    if not sel.entries:
        sel = sel.__class__(entries=discover_models(mgr), auto_switch=sel.auto_switch)
    entries = [
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
    return {
        "ok": True,
        "state_root": str(state),
        "auto_switch": sel.auto_switch,
        "selected_count": sum(1 for e in sel.entries if e.selected),
        "entries": entries,
        "selected": [e["key"] for e in entries if e["selected"]],
    }


def handle_policy(handler: "BaseHTTPRequestHandler") -> None:
    from api_serializers import send_json

    send_json(handler, 200, _policy_payload(handler))


# ── Session model override ────────────────────────────────────────────────────

_SESSION_OVERRIDE_FILE = ".bago_session_model.json"
_SESSION_OVERRIDE_DIR = "session-models"


def _override_path(state: "Path", session_id: str = "") -> "Path":
    if not session_id:
        return Path(state) / _SESSION_OVERRIDE_FILE
    from session_registry import validate_session_id
    return Path(state) / _SESSION_OVERRIDE_DIR / f"{validate_session_id(session_id)}.json"


def restore_session_model(mgr) -> dict:
    """Restore a persisted session override and rebuild its live adapter."""
    import json

    if mgr is None:
        return {"ok": False, "restored": False, "reason": "manager_unavailable"}
    state = Path(mgr.state_root)
    path = _override_path(state, str(getattr(mgr, "session_id", "legacy")))
    legacy_path = _override_path(state)
    if not path.exists() and legacy_path.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.replace(path)
        except OSError:
            path = legacy_path
    if not path.exists():
        return {"ok": True, "restored": False, "reason": "no_override"}
    try:
        model_key = str(json.loads(path.read_text(encoding="utf-8")).get("model") or "").strip()
        if not model_key:
            return {"ok": True, "restored": False, "reason": "empty_override"}
        parts = model_key.split("/", 1)
        provider = parts[0] if len(parts) == 2 else mgr.provider
        model = parts[1] if len(parts) == 2 else parts[0]
        if mgr.provider == provider and mgr.model == model:
            return {"ok": True, "restored": False, "reason": "already_active", "model": model_key}
        result = mgr.switch(provider, model, force=True)
        return {**result, "restored": bool(result.get("ok")), "model": model_key}
    except Exception as exc:
        return {"ok": False, "restored": False, "reason": str(exc)}


def handle_session_model(handler: "BaseHTTPRequestHandler", body: dict) -> None:
    """POST /router/session-model — override the model for this session.

    body = {"model": "ollama-local/llama3.2:3b"} or {"model": null} to clear.
    """
    from api_serializers import send_json
    from event_bus import emit
    import json, os

    state = _state_root(handler)
    model_key = body.get("model")  # None means clear override

    mgr = getattr(handler, "session_mgr", None)
    override_path = _override_path(state, str(getattr(mgr, "session_id", "")))

    if model_key is None or model_key == "":
        # Clear override
        if override_path.exists():
            override_path.unlink()
        send_json(handler, 200, {"ok": True, "session_model": None, "cleared": True})
        emit("router.session_model_cleared", {})
        return

    # Apply through SessionManager so the adapter is rebuilt. Mutating only
    # provider/model leaves the previous adapter alive (for example Ollama
    # answering after the user selected Copilot).
    if mgr is not None:
        try:
            parts = str(model_key).split("/", 1)
            if len(parts) == 2:
                switch_result = mgr.switch(parts[0], parts[1], force=True)
            else:
                switch_result = mgr.switch(mgr.provider, str(model_key), force=True)
            if not switch_result.get("ok"):
                send_json(handler, 400, {"ok": False, "error": switch_result.get("error") or "No se pudo activar el modelo"})
                return
        except Exception as exc:
            send_json(handler, 400, {"ok": False, "error": f"No se pudo activar el modelo: {exc}"})
            return

    override = {"model": str(model_key)}
    tmp = override_path.with_suffix(".tmp")
    override_path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(override, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(override_path))

    # Buffer cleaner: prepara Ollama para el modelo nuevo.
    # Solo aplica si el provider es local (ollama). No rompe nada si
    # Ollama no responde.
    buffer_report = None
    try:
        if mgr is not None and mgr.provider == "ollama-local":
            from model_buffer import get_model_buffer
            buf = get_model_buffer()
            buffer_report = buf.prepare_for(mgr.model, policy="LRU")
    except Exception as exc:
        buffer_report = {"error": str(exc)}

    response_body: dict = {"ok": True, "session_model": model_key}
    if buffer_report is not None:
        response_body["buffer"] = {
            "target": getattr(buffer_report, "target", model_key),
            "policy": getattr(buffer_report, "policy", "LRU"),
            "unloaded": getattr(buffer_report, "unloaded", []),
            "kept": getattr(buffer_report, "kept", []),
            "freed_gb": getattr(buffer_report, "freed_gb", 0.0),
            "elapsed_ms": getattr(buffer_report, "elapsed_ms", 0.0),
        }

    send_json(handler, 200, response_body)
    emit("router.session_model_changed", {"model": model_key})


def handle_session_model_get(handler: "BaseHTTPRequestHandler") -> None:
    """GET /router/session-model — current session model override."""
    from api_serializers import send_json
    import json

    state = _state_root(handler)
    mgr = getattr(handler, "session_mgr", None)
    override_path = _override_path(state, str(getattr(mgr, "session_id", "")))
    restore_report = restore_session_model(mgr)

    if override_path.exists():
        try:
            data = json.loads(override_path.read_text(encoding="utf-8"))
            send_json(handler, 200, {
                "ok": bool(restore_report.get("ok", True)),
                "session_model": data.get("model"),
                "effective_provider": getattr(mgr, "provider", None),
                "effective_model": getattr(mgr, "model", None),
                "restored": bool(restore_report.get("restored")),
            })
            return
        except Exception:
            pass

    send_json(handler, 200, {"ok": True, "session_model": None})
