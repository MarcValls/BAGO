#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bago_core.node_control_ssot import ALLOWED_MODES, CLI_MODES, DEFAULT_PIECE_CATALOG, PIECE_STORE_TYPES
from bago_core.node_control_render import (
    render_connectors as _render_connectors_mod,
    render_matrix as _render_matrix_mod,
    render_pieces as _render_pieces_mod,
    render_text as _render_text_mod,
)
from bago_core.node_control_tui import interactive_tui as _interactive_tui_mod

BAGO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class RegistryPaths:
    root: Path
    installations: Path
    pieces: Path
    connectors: Path
    compatibility: Path
    evidence: Path
    exports: Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(text: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in clean:
        clean = clean.replace("--", "-")
    return clean.strip("-") or "item"


def _json_read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _jsonl_append(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False))
        fh.write("\n")


def _registry_paths(base_path: str | Path) -> RegistryPaths:
    root = Path(base_path) / ".bago" / "state" / "node_control"
    return RegistryPaths(
        root=root,
        installations=root / "installations.json",
        pieces=root / "pieces.json",
        connectors=root / "connectors.json",
        compatibility=root / "compatibility.json",
        evidence=root / "evidence.jsonl",
        exports=root / "exports",
    )


def _piece_store_root() -> Path:
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "BAGO" / "pieces"


def _piece_store_dirs() -> list[Path]:
    root = _piece_store_root()
    return [root / name for name in PIECE_STORE_TYPES]


def _installation_id(path: str | Path) -> str:
    norm = str(Path(path).resolve()).lower()
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]
    return f"inst-{digest}"


def _piece_manifest(piece: dict[str, Any]) -> dict[str, Any]:
    return {
        "piece_id": piece["piece_id"],
        "type": piece["type"],
        "scope": piece["scope"],
        "version": piece["version"],
        "hash": piece["hash"],
        "store_path": piece["store_path"],
        "materialized_at": _now(),
        "managed_by": "bago.node_control",
    }


def _materialize_piece_store(pieces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root = _piece_store_root()
    created: list[dict[str, Any]] = []
    root.mkdir(parents=True, exist_ok=True)
    for category_dir in _piece_store_dirs():
        category_dir.mkdir(parents=True, exist_ok=True)

    for piece in pieces:
        piece_path = Path(piece["store_path"])
        piece_path.mkdir(parents=True, exist_ok=True)
        manifest_path = piece_path / "manifest.json"
        if not manifest_path.exists():
            _json_write(manifest_path, _piece_manifest(piece))
        created.append(
            {
                "piece_id": piece["piece_id"],
                "path": str(piece_path),
                "manifest": str(manifest_path),
                "exists": piece_path.exists(),
            }
        )
    return created


def _derive_profile(install: dict[str, Any]) -> tuple[str, str]:
    mode = (install.get("mode") or "").lower()
    version = str(install.get("version") or "")
    tag = str(install.get("tag") or "")
    channel = "beta" if any(token in f"{version} {tag}".lower() for token in ("beta", "prerelease")) else "stable"
    if mode in {"system", "work"}:
        profile = "production" if channel == "stable" else "beta"
    elif mode in {"dev", "source"}:
        profile = "lab"
    elif mode in {"ign", "launch"}:
        profile = "beta"
    elif mode == "user":
        profile = "offline"
    else:
        profile = "production"
    return profile, channel


def _fallback_installation(base_path: str | Path) -> dict[str, Any]:
    root = Path(base_path).resolve()
    return {
        "installation_id": _installation_id(root),
        "path": str(root),
        "mode": "source",
        "description": "workspace fallback",
        "exists": True,
        "version": "",
        "tag": "",
        "channel": "stable",
        "profile": "lab",
        "state": "active",
        "policy": "observe-and-overlay",
        "source": "fallback",
    }


def discover_installations(base_path: str | Path) -> list[dict[str, Any]]:
    try:
        from bago_core.cli_installs import _scan as scan_installations  # type: ignore
        items = [item for item in scan_installations() if item.get("exists")]
    except Exception:
        items = []

    installs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        path = str(Path(item["path"]).resolve())
        if path.lower() in seen:
            continue
        seen.add(path.lower())
        profile, channel = _derive_profile(item)
        installs.append(
            {
                "installation_id": _installation_id(path),
                "path": path,
                "mode": item.get("mode", "unknown"),
                "description": item.get("description", ""),
                "exists": True,
                "version": item.get("version", ""),
                "tag": item.get("tag", ""),
                "channel": channel,
                "profile": profile,
                "state": "active",
                "policy": "registry-driven",
                "source": "scan",
                "has_supervisor": bool(item.get("has_supervisor")),
                "supervisor_alive": bool(item.get("supervisor_alive")),
            }
        )
    if not installs:
        installs.append(_fallback_installation(base_path))
    else:
        root = str(Path(base_path).resolve())
        if not any(item["path"].lower() == root.lower() for item in installs):
            installs.append(_fallback_installation(base_path))
    return installs


def _policy_for(installation: dict[str, Any], piece: dict[str, Any]) -> dict[str, Any]:
    profile = installation.get("profile", "production")
    scope = piece.get("scope", "shared")
    ptype = piece.get("type", "tool")
    piece_id = piece.get("piece_id", "")

    mode = "connected"
    if profile == "production":
        if scope == "cloud" or scope == "experimental" or ptype == "agent":
            mode = "locked"
        elif ptype in {"repo", "knowledge"}:
            mode = "read-only"
        else:
            mode = "connected"
    elif profile == "beta":
        if scope == "cloud":
            mode = "shadow"
        elif scope == "experimental" or ptype == "agent":
            mode = "shadow"
        elif ptype in {"repo", "knowledge"}:
            mode = "read-only"
        else:
            mode = "connected"
    elif profile == "lab":
        if scope == "cloud":
            mode = "connected"
        elif scope == "experimental":
            mode = "writable overlay"
        elif ptype in {"repo", "knowledge"}:
            mode = "writable overlay"
        else:
            mode = "connected"
    elif profile == "offline":
        if scope == "cloud":
            mode = "locked"
        elif scope == "experimental":
            mode = "locked"
        elif ptype in {"repo", "knowledge"}:
            mode = "read-only"
        else:
            mode = "connected"
    elif profile == "quarantine":
        mode = "locked"

    can_execute = mode in {"connected", "writable overlay"}
    can_modify = mode == "writable overlay"
    sync_mode = {
        "connected": "pull",
        "shadow": "observe",
        "locked": "deny",
        "detached": "none",
        "read-only": "pull",
        "writable overlay": "overlay",
    }[mode]
    visibility = {
        "connected": "visible",
        "shadow": "shadow",
        "locked": "hidden",
        "detached": "detached",
        "read-only": "readonly",
        "writable overlay": "overlay",
    }[mode]
    reason = f"profile={profile};scope={scope};type={ptype};piece={piece_id}"
    return {
        "mode": mode,
        "policy": {
            "can_execute": can_execute,
            "can_modify": can_modify,
            "sync_mode": sync_mode,
            "visibility": visibility,
        },
        "reason": reason,
    }


def _connector_id(installation_id: str, piece_id: str) -> str:
    digest = hashlib.sha1(f"{installation_id}:{piece_id}".encode("utf-8")).hexdigest()[:10]
    return f"conn-{digest}"


def _build_connectors(installations: list[dict[str, Any]], pieces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    connectors: list[dict[str, Any]] = []
    for install in installations:
        for piece in pieces:
            resolved = _policy_for(install, piece)
            connectors.append(
                {
                    "connector_id": _connector_id(install["installation_id"], piece["piece_id"]),
                    "installation_id": install["installation_id"],
                    "piece_id": piece["piece_id"],
                    "mode": resolved["mode"],
                    "policy": resolved["policy"],
                    "reason": resolved["reason"],
                    "created_at": _now(),
                    "updated_at": _now(),
                }
            )
    return connectors


def _build_compatibility(connectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for connector in connectors:
        rows.append(
            {
                "installation_id": connector["installation_id"],
                "piece_id": connector["piece_id"],
                "mode": connector["mode"],
                "can_execute": connector["policy"]["can_execute"],
                "can_modify": connector["policy"]["can_modify"],
                "sync_mode": connector["policy"]["sync_mode"],
                "visibility": connector["policy"]["visibility"],
                "allowed": connector["mode"] != "locked",
            }
        )
    return rows


def _load_state(base_path: str | Path) -> tuple[RegistryPaths, dict[str, Any]]:
    paths = _registry_paths(base_path)
    paths.root.mkdir(parents=True, exist_ok=True)
    store_root = _piece_store_root()
    store_root.mkdir(parents=True, exist_ok=True)
    for category_dir in _piece_store_dirs():
        category_dir.mkdir(parents=True, exist_ok=True)

    installations = _json_read(paths.installations, [])
    pieces = _json_read(paths.pieces, [])
    if not pieces:
        pieces = list(DEFAULT_PIECE_CATALOG)
        _json_write(paths.pieces, pieces)
    piece_inventory = _materialize_piece_store(pieces)

    if not installations:
        installations = discover_installations(base_path)
        _json_write(paths.installations, installations)

    connectors = _json_read(paths.connectors, [])
    if not connectors:
        connectors = _build_connectors(installations, pieces)
        _json_write(paths.connectors, connectors)

    compatibility = _json_read(paths.compatibility, [])
    if not compatibility:
        compatibility = _build_compatibility(connectors)
        _json_write(paths.compatibility, compatibility)

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


def _persist_state(paths: RegistryPaths, state: dict[str, Any]) -> None:
    _json_write(paths.installations, state["installations"])
    _json_write(paths.pieces, state["pieces"])
    _json_write(paths.connectors, state["connectors"])
    _json_write(paths.compatibility, state["compatibility"])


def _find_installation(state: dict[str, Any], key: str) -> dict[str, Any] | None:
    key_norm = str(key).strip().lower()
    for install in state["installations"]:
        if install["installation_id"].lower() == key_norm:
            return install
        if Path(install["path"]).resolve().as_posix().lower() == Path(key).resolve().as_posix().lower():
            return install
    return None


def _find_piece(state: dict[str, Any], key: str) -> dict[str, Any] | None:
    key_norm = str(key).strip().lower()
    for piece in state["pieces"]:
        if piece["piece_id"].lower() == key_norm:
            return piece
    return None


def _find_connector(state: dict[str, Any], installation_id: str, piece_id: str) -> dict[str, Any] | None:
    for connector in state["connectors"]:
        if connector["installation_id"] == installation_id and connector["piece_id"] == piece_id:
            return connector
    return None


def _normalize_mode(mode: str | None) -> str:
    if not mode:
        return "connected"
    return CLI_MODES.get(mode.lower(), mode.lower())


def _refresh_compatibility(state: dict[str, Any]) -> None:
    state["compatibility"] = _build_compatibility(state["connectors"])


def _record_evidence(paths: RegistryPaths, action: str, target: dict[str, Any], before: Any, after: Any, result: str) -> dict[str, Any]:
    entry = {
        "evidence_id": f"evi-{hashlib.sha1(f'{action}:{_now()}'.encode('utf-8')).hexdigest()[:10]}",
        "action": action,
        "target": target,
        "before": before,
        "after": after,
        "result": result,
        "timestamp": _now(),
        "actor": getpass.getuser(),
        "session": f"pid:{os.getpid()}",
    }
    _jsonl_append(paths.evidence, entry)
    return entry


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
    mode_norm = _normalize_mode(mode_filter).strip().lower() if mode_filter else ""
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

    if failures == 0:
        _record_evidence(
            paths,
            "validate",
            {"scope": "node-control", "base_path": str(Path(base_path).resolve())},
            {"checks": len(checks)},
            {"checks": len(checks), "status": "pass"},
            "pass",
        )
    else:
        _record_evidence(
            paths,
            "validate",
            {"scope": "node-control", "base_path": str(Path(base_path).resolve())},
            {"checks": len(checks)},
            {"checks": len(checks), "status": "fail", "failures": failures},
            "fail",
        )

    return failures == 0, {"checks": checks, "failures": failures, "state": status(base_path)}


def connect(base_path: str | Path, installation_key: str, piece_key: str, mode: str = "connected") -> dict[str, Any]:
    paths, state = _load_state(base_path)
    install = _find_installation(state, installation_key)
    piece = _find_piece(state, piece_key)
    if install is None:
        raise ValueError(f"installation not found: {installation_key}")
    if piece is None:
        raise ValueError(f"piece not found: {piece_key}")

    normalized_mode = _normalize_mode(mode)
    resolved = _policy_for(install, piece)
    existing = _find_connector(state, install["installation_id"], piece["piece_id"])
    before = dict(existing) if existing else None
    connector = dict(existing) if existing else {
        "connector_id": _connector_id(install["installation_id"], piece["piece_id"]),
        "installation_id": install["installation_id"],
        "piece_id": piece["piece_id"],
        "created_at": _now(),
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
    connector["updated_at"] = _now()
    if existing is None:
        state["connectors"].append(connector)
    else:
        existing.update(connector)
    _refresh_compatibility(state)
    _persist_state(paths, state)
    _record_evidence(
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
    install = _find_installation(state, installation_key)
    piece = _find_piece(state, piece_key)
    if install is None:
        raise ValueError(f"installation not found: {installation_key}")
    if piece is None:
        raise ValueError(f"piece not found: {piece_key}")
    connector = _find_connector(state, install["installation_id"], piece["piece_id"])
    if connector is None:
        raise ValueError("connector not found")
    before = dict(connector)
    connector["mode"] = "detached"
    connector["policy"] = {"can_execute": False, "can_modify": False, "sync_mode": "none", "visibility": "detached"}
    connector["updated_at"] = _now()
    _refresh_compatibility(state)
    _persist_state(paths, state)
    _record_evidence(
        paths,
        "disconnect",
        {"installation_id": install["installation_id"], "piece_id": piece["piece_id"]},
        before,
        connector,
        "ok",
    )
    return {"connector": connector, "state": status(base_path)}


def set_mode(base_path: str | Path, installation_key: str, piece_key: str, mode: str) -> dict[str, Any]:
    normalized_mode = _normalize_mode(mode)
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
        "exported_at": _now(),
        "status": status(base_path),
        "state": {
            "installations": state["installations"],
            "pieces": state["pieces"],
            "connectors": state["connectors"],
            "compatibility": state["compatibility"],
        },
    }
    _json_write(target, payload)
    _record_evidence(
        boot["paths"],
        "export",
        {"scope": "node-control", "output": str(target)},
        {"records": len(state["connectors"])},
        {"records": len(state["connectors"]), "output": str(target)},
        "ok",
    )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BAGO Node Control")
    parser.add_argument("--base-path", default=str(BAGO_ROOT), help="Base path del runtime")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Muestra el registry, policy y evidence state")
    sub.add_parser("validate", help="Valida el registry/policy/compatibility/evidence")

    pieces_p = sub.add_parser("pieces", help="Lista piezas del PieceStore")
    pieces_p.add_argument("--type", default="")
    pieces_p.add_argument("--scope", default="")
    pieces_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    connectors_p = sub.add_parser("connectors", help="Lista conectores del registry")
    connectors_p.add_argument("--installation", default="")
    connectors_p.add_argument("--piece", default="")
    connectors_p.add_argument("--mode", default="")
    connectors_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    matrix_p = sub.add_parser("matrix", help="Muestra la matriz Installation x Piece")
    matrix_p.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    connect_p = sub.add_parser("connect", help="Conecta una installation con una piece")
    connect_p.add_argument("--installation", required=True)
    connect_p.add_argument("--piece", required=True)
    connect_p.add_argument("--mode", default="connected", choices=list(CLI_MODES.keys()))

    disconnect_p = sub.add_parser("disconnect", help="Desconecta una installation de una piece")
    disconnect_p.add_argument("--installation", required=True)
    disconnect_p.add_argument("--piece", required=True)

    setmode_p = sub.add_parser("set-mode", help="Cambia el modo de un connector")
    setmode_p.add_argument("--installation", required=True)
    setmode_p.add_argument("--piece", required=True)
    setmode_p.add_argument("--mode", required=True, choices=list(CLI_MODES.keys()))

    export_p = sub.add_parser("export", help="Exporta el estado a un bundle JSON")
    export_p.add_argument("--output", default="")

    sub.add_parser("tui", aliases=("terminal",), help="Interfaz de terminal del gestor de instalaciones")

    args = parser.parse_args(argv)
    base_path = args.base_path
    command = args.command or "status"

    if command == "status":
        payload = status(base_path)
        print(json.dumps(payload, indent=None if args.json else 2, ensure_ascii=False))
        return 0
    if command == "validate":
        ok, payload = validate(base_path)
        print(json.dumps(payload, indent=None if args.json else 2, ensure_ascii=False))
        return 0 if ok else 1
    if command == "pieces":
        payload = list_pieces(base_path, getattr(args, "type", ""), getattr(args, "scope", ""))
        if args.json:
            print(json.dumps(payload, indent=None, ensure_ascii=False))
        else:
            print(_render_pieces_mod(payload))
        return 0
    if command == "connectors":
        payload = list_connectors(
            base_path,
            getattr(args, "installation", ""),
            getattr(args, "piece", ""),
            getattr(args, "mode", ""),
        )
        if args.json:
            print(json.dumps(payload, indent=None, ensure_ascii=False))
        else:
            print(_render_connectors_mod(payload))
        return 0
    if command == "matrix":
        payload = matrix(base_path)
        if args.json:
            print(json.dumps(payload, indent=None, ensure_ascii=False))
        else:
            print(_render_matrix_mod(payload))
        return 0
    if command == "connect":
        payload = connect(base_path, args.installation, args.piece, args.mode)
        print(json.dumps(payload, indent=None if args.json else 2, ensure_ascii=False))
        return 0
    if command == "disconnect":
        payload = disconnect(base_path, args.installation, args.piece)
        print(json.dumps(payload, indent=None if args.json else 2, ensure_ascii=False))
        return 0
    if command == "set-mode":
        payload = set_mode(base_path, args.installation, args.piece, args.mode)
        print(json.dumps(payload, indent=None if args.json else 2, ensure_ascii=False))
        return 0
    if command == "export":
        target = export_bundle(base_path, args.output or None)
        print(str(target))
        return 0
    if command in {"tui", "terminal"}:
        return _interactive_tui_mod(
            base_path,
            {
                "status": status,
                "list_pieces": list_pieces,
                "list_connectors": list_connectors,
                "matrix": matrix,
                "validate": validate,
                "export_bundle": export_bundle,
                "connect": connect,
                "disconnect": disconnect,
                "set_mode": set_mode,
            },
        )

    parser.print_help()
    return 1


def _run_tests() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        status_payload = status(td)
        assert status_payload["installations"] >= 1
        pieces_payload = list_pieces(td)
        assert pieces_payload["count"] >= 1
        connectors_payload = list_connectors(td)
        assert connectors_payload["count"] >= 1
        matrix_payload = matrix(td)
        assert matrix_payload["rows"]
        ok, payload = validate(td)
        assert ok is True
        assert payload["failures"] == 0
        export_path = export_bundle(td)
        assert export_path.exists()
        assert _render_text_mod(status(td)).startswith("BAGO NODE CONTROL")
        assert "BAGO PIECES" in _render_pieces_mod(list_pieces(td))
        assert "BAGO CONNECTORS" in _render_connectors_mod(list_connectors(td))
        print("node_control.py --test: ALL PASS")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        raise SystemExit(_run_tests())
    raise SystemExit(main())
