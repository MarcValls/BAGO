#!/usr/bin/env python3
"""bago_core/node_control_connect.py -- live side-effects for connectors (R7).

Owns: ``connect``, ``disconnect``, ``set_mode``, ``export_bundle``. These are
the only operations that mutate the registry's connector / compatibility
data and write evidence rows; everything else is read-only and lives in
:mod:`bago_core.node_control_state`.

The per-mode policy tables (``_MODE_SYNC`` / ``_MODE_VISIBILITY``) live in
:mod:`bago_core.node_control_policy` as the R5 SSoT; this module imports
:func:`policy_dict_for_mode` from there.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from bago_core.node_control_ssot import ALLOWED_MODES
from bago_core.node_control_state import (
    _load_state,
    _persist_state,
    refresh_compatibility,
    status,
)
from bago_core.node_control_policy import (
    connector_id,
    find_connector,
    find_installation,
    find_piece,
    normalize_mode,
    policy_dict_for_mode,
    policy_for,
)
from bago_core.node_control_store import (
    json_write,
    now,
    record_evidence,
)


def connect(
    base_path: str | Path,
    installation_key: str,
    piece_key: str,
    mode: str = "connected",
) -> dict[str, Any]:
    paths, state = _load_state(base_path)
    install = find_installation(state, installation_key)
    piece = find_piece(state, piece_key)
    if install is None:
        raise ValueError(f"installation not found: {installation_key}")
    if piece is None:
        raise ValueError(f"piece not found: {piece_key}")

    normalized_mode = normalize_mode(mode)
    resolved = policy_for(install, piece)
    existing = find_connector(state, install["installation_id"], piece["piece_id"])
    before = dict(existing) if existing else None
    connector = dict(existing) if existing else {
        "connector_id": connector_id(install["installation_id"], piece["piece_id"]),
        "installation_id": install["installation_id"],
        "piece_id": piece["piece_id"],
        "created_at": now(),
    }
    connector["mode"] = normalized_mode
    connector["policy"] = policy_dict_for_mode(normalized_mode)
    connector["reason"] = resolved["reason"]
    connector["updated_at"] = now()
    if existing is None:
        state["connectors"].append(connector)
    else:
        existing.update(connector)
    refresh_compatibility(state)
    _persist_state(paths, state)
    record_evidence(
        paths,
        "connect",
        {"installation_id": install["installation_id"], "piece_id": piece["piece_id"]},
        before,
        connector,
        "ok",
    )
    return {"connector": connector, "state": status(base_path)}


def disconnect(
    base_path: str | Path,
    installation_key: str,
    piece_key: str,
) -> dict[str, Any]:
    paths, state = _load_state(base_path)
    install = find_installation(state, installation_key)
    piece = find_piece(state, piece_key)
    if install is None:
        raise ValueError(f"installation not found: {installation_key}")
    if piece is None:
        raise ValueError(f"piece not found: {piece_key}")
    connector = find_connector(state, install["installation_id"], piece["piece_id"])
    if connector is None:
        raise ValueError("connector not found")
    before = dict(connector)
    connector["mode"] = "detached"
    connector["policy"] = {
        "can_execute": False,
        "can_modify": False,
        "sync_mode": "none",
        "visibility": "detached",
    }
    connector["updated_at"] = now()
    refresh_compatibility(state)
    _persist_state(paths, state)
    record_evidence(
        paths,
        "disconnect",
        {"installation_id": install["installation_id"], "piece_id": piece["piece_id"]},
        before,
        connector,
        "ok",
    )
    return {"connector": connector, "state": status(base_path)}


def set_mode(
    base_path: str | Path,
    installation_key: str,
    piece_key: str,
    mode: str,
) -> dict[str, Any]:
    normalized_mode = normalize_mode(mode)
    if normalized_mode not in ALLOWED_MODES:
        raise ValueError(f"unsupported mode: {mode}")
    if normalized_mode == "detached":
        return disconnect(base_path, installation_key, piece_key)
    return connect(base_path, installation_key, piece_key, mode=normalized_mode)


def export_bundle(
    base_path: str | Path,
    output: str | Path | None = None,
) -> Path:
    paths, state = _load_state(base_path)
    if output:
        target = Path(output)
    else:
        target = paths.exports / f"node-control-{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
    payload = {
        "exported_at": now(),
        "status": status(base_path),
        "state": {
            "installations": state["installations"],
            "pieces": state["pieces"],
            "connectors": state["connectors"],
            "compatibility": state["compatibility"],
        },
    }
    json_write(target, payload)
    record_evidence(
        paths,
        "export",
        {"scope": "node-control", "output": str(target)},
        {"records": len(state["connectors"])},
        {"records": len(state["connectors"]), "output": str(target)},
        "ok",
    )
    return target
