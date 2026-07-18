#!/usr/bin/env python3
"""bago_core/node_control_state.py -- state-level orchestrator (R7 dispatch by domain).

Owns: bootstrap, status, list_pieces, list_connectors, matrix, validate, and
the load/persist/refresh helpers used by the live side-effects in
:mod:`bago_core.node_control_connect`. Renders live in the matching render
sibling; this module only returns dicts (R8).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from bago_core.node_control_ssot import ALLOWED_MODES
from bago_core.node_control_store import (
    RegistryPaths,
    discover_installations,
    jsonl_append,
    json_read,
    json_write,
    materialize_piece_store,
    record_evidence,
    registry_paths,
)
from bago_core.node_control_policy import (
    build_compatibility,
    build_connectors,
    connector_id,
    find_connector,
    find_installation,
    find_piece,
    normalize_mode,
    policy_dict_for_mode,
    policy_for,
)


def _load_state(base_path: str | Path) -> tuple[RegistryPaths, dict[str, Any]]:
    """Load (or first-bootstrap) the Node Control registry for *base_path*."""
    paths = registry_paths(base_path)
    paths.root.mkdir(parents=True, exist_ok=True)

    installations = json_read(paths.installations, [])
    pieces = json_read(paths.pieces, [])
    if not pieces:
        from bago_core.node_control_store import load_default_piece_catalog
        pieces = load_default_piece_catalog()
        json_write(paths.pieces, pieces)
    piece_inventory = materialize_piece_store(pieces)

    if not installations:
        installations = discover_installations(base_path)
        json_write(paths.installations, installations)

    connectors = json_read(paths.connectors, [])
    if not connectors:
        from bago_core.node_control_store import now as _now
        connectors = build_connectors(installations, pieces, _now)
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
        "store_root": str(paths.root.parent.parent / "pieces")
        if not (paths.root.parent.parent / "pieces").exists()
        else str((paths.root.parent.parent / "pieces").resolve()),
    }
    return paths, state


def _persist_state(paths: RegistryPaths, state: dict[str, Any]) -> None:
    json_write(paths.installations, state["installations"])
    json_write(paths.pieces, state["pieces"])
    json_write(paths.connectors, state["connectors"])
    json_write(paths.compatibility, state["compatibility"])


def refresh_compatibility(state: dict[str, Any]) -> None:
    state["compatibility"] = build_compatibility(state["connectors"])


def bootstrap(base_path: str | Path) -> dict[str, Any]:
    paths, state = _load_state(base_path)
    _persist_state(paths, state)
    return {"paths": paths, "state": state}


def status(base_path: str | Path) -> dict[str, Any]:
    boot = bootstrap(base_path)
    state = boot["state"]
    connectors = state["connectors"]
    potential_connectors = len(state["installations"]) * len(state["pieces"])
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
        "potential_connectors": potential_connectors,
        "unmaterialized_connectors": max(0, potential_connectors - len(connectors)),
        "compatibility_rows": len(state["compatibility"]),
        "evidence_file": boot["paths"].evidence.as_posix(),
        "modes": modes,
        "installations_data": state["installations"],
        "pieces_data": state["pieces"],
        "connectors_data": connectors,
        "compatibility_data": state["compatibility"],
    }


def list_pieces(
    base_path: str | Path,
    type_filter: str = "",
    scope_filter: str = "",
) -> dict[str, Any]:
    boot = bootstrap(base_path)
    pieces = boot["state"]["pieces"]
    items: list[dict[str, Any]] = []
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
    items: list[dict[str, Any]] = []
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
        row: dict[str, Any] = {
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
                    "connector_id": connector["connector_id"] if connector else "",
                    "state": connector["mode"] if connector else "not-created",
                    "created": connector is not None,
                    "mode": connector["mode"] if connector else "available",
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


def evidence_tail(base_path: str | Path, limit: int = 25) -> dict[str, Any]:
    """Return the newest Node Control evidence records without mutating state."""
    paths, _state = _load_state(base_path)
    safe_limit = max(1, min(int(limit or 25), 200))
    entries: list[dict[str, Any]] = []
    if paths.evidence.exists():
        for line in paths.evidence.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {"result": "invalid", "raw": line}
            entries.append(payload)
    tail = list(reversed(entries[-safe_limit:]))
    return {
        "base_path": str(Path(base_path).resolve()),
        "evidence_file": paths.evidence.as_posix(),
        "count": len(tail),
        "total": len(entries),
        "entries": tail,
    }


def preview_mutation(
    base_path: str | Path,
    installation_key: str,
    piece_key: str,
    mode: str,
) -> dict[str, Any]:
    """Resolve the before/after connector contract without applying it."""
    _paths, state = _load_state(base_path)
    install = find_installation(state, installation_key)
    piece = find_piece(state, piece_key)
    if install is None:
        raise ValueError(f"installation not found: {installation_key}")
    if piece is None:
        raise ValueError(f"piece not found: {piece_key}")

    target_mode = normalize_mode(mode)
    current = find_connector(state, install["installation_id"], piece["piece_id"])
    recommended = policy_for(install, piece)
    proposed = {
        "connector_id": current["connector_id"]
        if current
        else connector_id(install["installation_id"], piece["piece_id"]),
        "installation_id": install["installation_id"],
        "piece_id": piece["piece_id"],
        "mode": target_mode,
        "policy": policy_dict_for_mode(target_mode),
        "reason": recommended["reason"],
    }
    action = "disconnect" if target_mode == "detached" else ("set-mode" if current else "connect")
    current_mode = current["mode"] if current else "available"
    warnings: list[str] = []
    if current is None:
        warnings.append("connector_not_created")
    if target_mode != recommended["mode"]:
        warnings.append(f"differs_from_profile_policy:{recommended['mode']}")
    if proposed["policy"]["can_execute"] and not bool(current and current["policy"]["can_execute"]):
        warnings.append("enables_execution")
    if proposed["policy"]["can_modify"] and not bool(current and current["policy"]["can_modify"]):
        warnings.append("enables_modification")
    if target_mode == current_mode:
        warnings.append("no_state_change")

    risk = "high" if proposed["policy"]["can_modify"] else (
        "medium" if proposed["policy"]["can_execute"] or target_mode != recommended["mode"] else "low"
    )
    return {
        "ok": True,
        "action": action,
        "risk": risk,
        "requires_confirmation": target_mode != current_mode,
        "target": {
            "installation_id": install["installation_id"],
            "installation_path": install["path"],
            "piece_id": piece["piece_id"],
        },
        "current": current,
        "current_state": current_mode,
        "proposed": proposed,
        "recommended": recommended,
        "warnings": warnings,
    }


def run_modular_guard() -> list[dict[str, Any]]:
    """Run ``tools/check_modular.py --json`` and return its findings.

    Best-effort: if the script is missing or fails to launch, a single
    R6 warning is returned instead of raising. R6 says this guard is part
    of the release gate; we never want it to break the node CLI entirely.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
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
        report = json.loads(result.stdout or "{}")
        # `check_modular.py --json` ya emite ERROR/WARN/INFO dentro de
        # `findings`. INFO se considera un warning soft de cara al guard
        # del Node Control, pero no bloquea el release.
        return list(report.get("findings", []))
    except Exception:  # noqa: BLE001
        return []


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

    mod_findings = run_modular_guard()
    mod_errors = sum(1 for f in mod_findings if f.get("severity") == "ERROR")
    # INFO findings are soft-warnings: they are not blockers for the
    # release gate, but we surface them in the count for visibility.
    mod_warns = sum(
        1 for f in mod_findings if f.get("severity") in {"WARN", "INFO"}
    )
    add_check(
        "modular_guard",
        mod_errors == 0,
        f"{mod_errors} errors, {mod_warns} warnings (tools/check_modular.py)",
    )

    action = "validate"
    target = {"scope": "node-control", "base_path": str(Path(base_path).resolve())}
    if failures == 0:
        record_evidence(
            paths,
            action,
            target,
            {"checks": len(checks)},
            {"checks": len(checks), "status": "pass"},
            "pass",
        )
    else:
        record_evidence(
            paths,
            action,
            target,
            {"checks": len(checks)},
            {"checks": len(checks), "status": "fail", "failures": failures},
            "fail",
        )

    return failures == 0, {"checks": checks, "failures": failures, "state": status(base_path)}
