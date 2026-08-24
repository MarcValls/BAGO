"""Versioned key/value integration API backed by the canonical state root."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from api_serializers import send_json
from api_state import resolve_state_root


_LOCK = threading.RLock()


def _store_path(handler) -> Path:
    return resolve_state_root(handler) / "integrations" / "kv-v1.json"


def _load(handler) -> dict[str, dict]:
    path = _store_path(handler)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("almacén KV corrupto: se esperaba un objeto")
    validated: dict[str, dict] = {}
    for key, value in data.items():
        if not isinstance(value, dict):
            raise ValueError(f"almacén KV corrupto: entrada inválida para {key}")
        normalized = _entry(value)
        if normalized["key"] != key:
            raise ValueError(f"almacén KV corrupto: key interna no coincide para {key}")
        validated[str(key)] = dict(value)
    return validated


def _save(handler, data: dict[str, dict]) -> None:
    path = _store_path(handler)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _entry(body: dict) -> dict:
    key = str(body.get("key", "")).strip()
    value = body.get("value")
    if not key or len(key) > 240 or any(char in key for char in "\r\n\0"):
        raise ValueError("key inválida")
    if not isinstance(value, str):
        raise ValueError("value debe ser texto")
    tags = body.get("tags", [])
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        raise ValueError("tags debe ser una lista de textos")
    return {"key": key, "value": value, "tags": tags}


def handle_list(handler) -> None:
    try:
        prefix = parse_qs(urlparse(handler.path).query).get("prefix", [""])[0]
        with _LOCK:
            entries = [value for key, value in sorted(_load(handler).items()) if key.startswith(prefix)]
        send_json(handler, 200, entries)
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"kb read failed: {exc}"})


def handle_get(handler, key: str) -> None:
    try:
        decoded = unquote(key)
        with _LOCK:
            entry = _load(handler).get(decoded)
        if entry is None:
            send_json(handler, 404, {"ok": False, "error": "key not found"})
            return
        send_json(handler, 200, entry)
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"kb read failed: {exc}"})


def handle_set(handler, body: dict) -> None:
    try:
        entry = _entry(body)
    except ValueError as exc:
        send_json(handler, 400, {"ok": False, "error": str(exc)})
        return
    try:
        with _LOCK:
            data = _load(handler)
            created = entry["key"] not in data
            data[entry["key"]] = entry
            _save(handler, data)
        send_json(handler, 201 if created else 200, {"ok": True, "entry": entry, "created": created})
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"kb write failed: {exc}"})


def handle_put(handler, key: str, body: dict) -> None:
    payload = dict(body or {})
    payload["key"] = unquote(key)
    handle_set(handler, payload)


def handle_delete(handler, key: str) -> None:
    try:
        decoded = unquote(key)
        with _LOCK:
            data = _load(handler)
            if decoded not in data:
                send_json(handler, 404, {"ok": False, "error": "key not found"})
                return
            del data[decoded]
            _save(handler, data)
        send_json(handler, 200, {"ok": True, "deleted": decoded})
    except Exception as exc:
        send_json(handler, 500, {"ok": False, "error": f"kb delete failed: {exc}"})
