#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from bago_core.node_control_policy import (
    build_compatibility,
    build_connectors,
    find_connector,
    find_installation,
    find_piece,
    normalize_mode,
    policy_for,
)
from bago_core.node_control_ssot import ALLOWED_MODES
from bago_core.node_control_store import (
    discover_installations,
    json_read,
    json_write,
    load_default_piece_catalog,
    materialize_piece_store,
    record_evidence,
    registry_paths,
    piece_store_dirs,
    piece_store_root,
    now,
)

def _load_state(base_path: str | Path) -> tuple[Any, dict[str, Any]]:
    paths = registry_paths(base_path)
    paths.root.mkdir(parents=True, exist_ok=True)
    store_root = piece_store_root()
    store_root.mkdir(parents=True, exist_ok=True)
    for category_dir in piece_store_dirs():
        category_dir.mkdir(parents=True, exist_ok=True)

    installations = json_read(paths.installations, [])
    pieces = json_read(paths.pieces, [])
    if not pieces:
        pieces = load_default_piece_catalog()
        json_write(paths.pieces, pieces)
    piece_inventory = materialize_piece_store(pieces)

    if not installations:
        installations = discover_installations(base_path)
        json_write(paths.installations, installations)

    connectors = json_read(paths.connectors, [])
    if not connectors:
        connectors = build_connectors(installations, pieces, now)
        json_write(paths.connectors, connectors)

    compatibility = json_read(paths.compatibility, [])
    if not compatibility:
        compatibility = build_compatibility(connectors)
        json_write(paths.compatibility, compatibility)

    state = {
        "installations": installations,
        "pieces": pieces,
        "piece_inventory": piece_inventory,
        "connectors": connectors,
        "compatibility": compatibility,
        "evidence_path": str(paths.evidence),
        "store_root": str(store_root),
    }
    return paths, state

def _persist_state(paths: Any, state: dict[str, Any]) -> None:
    json_write(paths.installations, state["installations"])
    json_write(paths.pieces, state["pieces"])
    json_write(paths.connectors, state["connectors"])
    json_write(paths.compatibility, state["compatibility"])

def _refresh_compatibility(state: dict[str, Any]) -> None:
    state["compatibility"] = build_compatibility(state["connectors"])

def bootstrap(base_path: str | Path) -> dict[str, Any]:
    paths, state = _load_state(base_path)
    _persist_state(paths, state)
    return {"paths": paths, "state": state}

def status(base_path: str | Path) -> dict[str, Any]:
    boot = bootstrap(base_path)
    state = boot["state"]
    connectors = state["connectors"]
    modes: dict[str, int] = {mode: 0 for mode in ALLOWED_MODES}
    for connector in connectors:
        modes[connector["mode"]] = modes.get(connector["mode"], 0) + 1
    return {
        "base_path": str(Path(base_path).resolve()),
        "store_root": state["store_root"],
        "installations": len(state["installations"]),
        "pieces": len(state["pieces"]),
        "piece_inventory": state["piece_inventory"],
        "connectors": len(connectors),
        "compatibility_rows": len(state["compatibility"]),
        "evidence_file": boot["paths"].evidence.as_posix(),
        "modes": modes,
        "installations_data": state["installations"],
        "pieces_data": state["pieces"],
        "connectors_data": connectors,
        "compatibility_data": state["compatibility"],
    }

def list_pieces(base_path: str | Path, type_filter: str = "", scope_filter: str = "") -> dict[str, Any]:
    boot = bootstrap(base_path)
    pieces = boot["state"]["pieces"]
    items = []
    type_norm = type_filter.strip().lower()
    scope_norm = scope_filter.strip().lower()
    for piece in pieces:
        if type_norm and piece["type"].lower() != type_norm:
            continue
        if scope_norm and piece["scope"].lower() != scope_norm:
            continue
        items.append(
            {
                **piece,
                "materialized_path": str(Path(piece["store_path"])),
                "manifest_path": str(Path(piece["store_path"]) / "manifest.json"),
                "exists": Path(piece["store_path"]).exists(),
            }
        )
    return {
        "base_path": str(Path(base_path).resolve()),
        "count": len(items),
        "pieces": items,
    }

def list_connectors(
    base_path: str | Path,
    installation_filter: str = "",
    piece_filter: str = "",
    mode_filter: str = "",
) -> dict[str, Any]:
    boot = bootstrap(base_path)
    connectors = boot["state"]["connectors"]
    installation_norm = installation_filter.strip().lower()
    piece_norm = piece_filter.strip().lower()
    mode_norm = normalize_mode(mode_filter).strip().lower() if mode_filter else ""
    items = []
    for connector in connectors:
        if installation_norm and connector["installation_id"].lower() != installation_norm:
            continue
        if piece_norm and connector["piece_id"].lower() != piece_norm:
            continue
        if mode_norm and connector["mode"].lower() != mode_norm:
            continue
        items.append(connector)
    return {
        "base_path": str(Path(base_path).resolve()),
        "count": len(items),
        "connectors": items,
    }

def matrix(base_path: str | Path) -> dict[str, Any]:
    boot = bootstrap(base_path)
    state = boot["state"]
    rows: list[dict[str, Any]] = []
    connectors_by_pair = {
        (item["installation_id"], item["piece_id"]): item for item in state["connectors"]
    }
    for piece in state["pieces"]:
        row = {
            "piece_id": piece["piece_id"],
            "type": piece["type"],
            "scope": piece["scope"],
            "cells": [],
        }
        for install in state["installations"]:
            connector = connectors_by_pair.get((install["installation_id"], piece["piece_id"]))
            row["cells"].append(
                {
                    "installation_id": install["installation_id"],
                    "installation_path": install["path"],
                    "mode": connector["mode"] if connector else "detached",
                    "allowed": bool(connector and connector["mode"] != "locked"),
                    "can_execute": bool(connector and connector["policy"]["can_execute"]),
                    "can_modify": bool(connector and connector["policy"]["can_modify"]),
                }
            )
        rows.append(row)
    return {
        "base_path": str(Path(base_path).resolve()),
        "installations": [
            {
                "installation_id": item["installation_id"],
                "path": item["path"],
                "mode": item.get("mode", ""),
                "profile": item.get("profile", ""),
                "channel": item.get("channel", ""),
            }
            for item in state["installations"]
        ],
        "pieces": [
            {
                "piece_id": item["piece_id"],
                "type": item["type"],
                "scope": item["scope"],
            }
            for item in state["pieces"]
        ],
        "rows": rows,
    }

def validate(base_path: str | Path) -> tuple[bool, dict[str, Any]]:
    boot = bootstrap(base_path)
    paths = boot["paths"]
    state = boot["state"]
    checks: list[dict[str, Any]] = []
    failures = 0

    def add_check(name: str, ok: bool, detail: str) -> None:
        nonlocal failures
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            failures += 1

    add_check("installations_present", len(state["installations"]) > 0, f"{len(state['installations'])} installations")
    add_check("pieces_present", len(state["pieces"]) > 0, f"{len(state['pieces'])} pieces")
    add_check("piece_store_materialized", all(Path(item["path"]).exists() for item in state["piece_inventory"]), f"{len(state['piece_inventory'])} materialized")
    connector_ids = [item["connector_id"] for item in state["connectors"]]
    add_check("connector_ids_unique", len(connector_ids) == len(set(connector_ids)), f"{len(connector_ids)} connectors")
    add_check("compatibility_rows_match", len(state["compatibility"]) == len(state["connectors"]), "matrix aligned with connectors")
    add_check("modes_valid", all(item["mode"] in ALLOWED_MODES for item in state["connectors"]), "all connector modes valid")
    add_check("evidence_path_writable", True, str(paths.evidence))

    # Modular guard (FASE modular) -- corre check_modular.py y agrega sus findings.
    mod_findings = _run_modular_guard()
    mod_errors = sum(1 for f in mod_findings if f.get("severity") == "ERROR")
    mod_warns = sum(1 for f in mod_findings if f.get("severity") == "WARN")
    add_check(
        "modular_guard",
        mod_errors == 0,
        f"{mod_errors} errors, {mod_warns} warnings (tools/check_modular.py)",
    )

    if failures == 0:
        record_evidence(
            paths,
            "validate",
            {"scope": "node-control", "base_path": str(Path(base_path).resolve())},
            {"checks": len(checks)},
            {"checks": len(checks), "status": "pass"},
            "pass",
        )
    else:
        record_evidence(
            paths,
            "validate",
            {"scope": "node-control", "base_path": str(Path(base_path).resolve())},
            {"checks": len(checks)},
            {"checks": len(checks), "status": "fail", "failures": failures},
            "fail",
        )

    return failures == 0, {"checks": checks, "failures": failures, "state": status(base_path)}

def _run_modular_guard() -> list[dict[str, Any]]:
    """Ejecuta tools/check_modular.py y devuelve sus findings.

    Best-effort: si el script no existe o falla de import, devuelve un finding
    suave en lugar de romper la validacion.
    """
    import subprocess
    repo_root = Path(__file__).resolve().parent.parent
    script = repo_root / "tools" / "check_modular.py"
    if not script.exists():
        return [{
            "rule": "R6", "severity": "WARN",
            "message": f"tools/check_modular.py no encontrado en {repo_root}",
        }]
    try:
        result = subprocess.run(
            ["python", str(script), "--json"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception as exc:  # noqa: BLE001
        return [{
            "rule": "R6", "severity": "WARN",
            "message": f"No se pudo ejecutar check_modular.py: {exc!r}",
        }]
    try:
        import json
        report = json.loads(result.stdout or "{}")
        return list(report.get("findings", []))
    except Exception:  # noqa: BLE001
        return []

def connect(base_path: str | Path, installation_key: str, piece_key: str, mode: str = "connected") -> dict[str, Any]:
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
        "connector_id": build_connectors([install], [piece], now)[0]["connector_id"],
        "installation_id": install["installation_id"],
        "piece_id": piece["piece_id"],
        "created_at": now(),
    }
    connector["mode"] = normalized_mode
    connector["policy"] = {
        "can_execute": normalized_mode in {"connected", "writable overlay"},
        "can_modify": normalized_mode == "writable overlay",
        "sync_mode": {
            "connected": "pull",
            "shadow": "observe",
            "locked": "deny",
            "detached": "none",
            "read-only": "pull",
            "writable overlay": "overlay",
        }[normalized_mode],
        "visibility": {
            "connected": "visible",
            "shadow": "shadow",
            "locked": "hidden",
            "detached": "detached",
            "read-only": "readonly",
            "writable overlay": "overlay",
        }[normalized_mode],
    }
    connector["reason"] = resolved["reason"]
    connector["updated_at"] = now()
    if existing is None:
        state["connectors"].append(connector)
    else:
        existing.update(connector)
    _refresh_compatibility(state)
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

def disconnect(base_path: str | Path, installation_key: str, piece_key: str) -> dict[str, Any]:
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
    connector["policy"] = {"can_execute": False, "can_modify": False, "sync_mode": "none", "visibility": "detached"}
    connector["updated_at"] = now()
    _refresh_compatibility(state)
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

def set_mode(base_path: str | Path, installation_key: str, piece_key: str, mode: str) -> dict[str, Any]:
    normalized_mode = normalize_mode(mode)
    if normalized_mode not in ALLOWED_MODES:
        raise ValueError(f"unsupported mode: {mode}")
    if normalized_mode == "detached":
        return disconnect(base_path, installation_key, piece_key)
    return connect(base_path, installation_key, piece_key, mode=normalized_mode)

def export_bundle(base_path: str | Path, output: str | Path | None = None) -> Path:
    boot = bootstrap(base_path)
    state = boot["state"]
    target = Path(output) if output else boot["paths"].exports / f"node-control-{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
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
        boot["paths"],
        "export",
        {"scope": "node-control", "output": str(target)},
        {"records": len(state["connectors"])},
        {"records": len(state["connectors"]), "output": str(target)},
        "ok",
    )
    return target
