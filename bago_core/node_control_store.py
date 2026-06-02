#!/usr/bin/env python3
from __future__ import annotations

import getpass
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bago_core.node_control_ssot import DEFAULT_PIECE_CATALOG, PIECE_STORE_TYPES

@dataclass(frozen=True)
class RegistryPaths:
    root: Path
    installations: Path
    pieces: Path
    connectors: Path
    compatibility: Path
    evidence: Path
    exports: Path

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def slug(text: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    while "--" in clean:
        clean = clean.replace("--", "-")
    return clean.strip("-") or "item"

def json_read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def json_write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

def jsonl_append(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False))
        fh.write("\n")

def registry_paths(base_path: str | Path) -> RegistryPaths:
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

def piece_store_root() -> Path:
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "BAGO" / "pieces"

def piece_store_dirs() -> list[Path]:
    root = piece_store_root()
    return [root / name for name in PIECE_STORE_TYPES]

def installation_id(path: str | Path) -> str:
    norm = str(Path(path).resolve()).lower()
    digest = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]
    return f"inst-{digest}"

def piece_manifest(piece: dict[str, Any]) -> dict[str, Any]:
    return {
        "piece_id": piece["piece_id"],
        "type": piece["type"],
        "scope": piece["scope"],
        "version": piece["version"],
        "hash": piece["hash"],
        "store_path": piece["store_path"],
        "materialized_at": now(),
        "managed_by": "bago.node_control",
    }

def materialize_piece_store(pieces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root = piece_store_root()
    created: list[dict[str, Any]] = []
    root.mkdir(parents=True, exist_ok=True)
    for category_dir in piece_store_dirs():
        category_dir.mkdir(parents=True, exist_ok=True)

    for piece in pieces:
        piece_path = Path(piece["store_path"])
        piece_path.mkdir(parents=True, exist_ok=True)
        manifest_path = piece_path / "manifest.json"
        if not manifest_path.exists():
            json_write(manifest_path, piece_manifest(piece))
        created.append(
            {
                "piece_id": piece["piece_id"],
                "path": str(piece_path),
                "manifest": str(manifest_path),
                "exists": piece_path.exists(),
            }
        )
    return created

def derive_profile(install: dict[str, Any]) -> tuple[str, str]:
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

def fallback_installation(base_path: str | Path) -> dict[str, Any]:
    root = Path(base_path).resolve()
    return {
        "installation_id": installation_id(root),
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
        profile, channel = derive_profile(item)
        installs.append(
            {
                "installation_id": installation_id(path),
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
        installs.append(fallback_installation(base_path))
    else:
        root = str(Path(base_path).resolve())
        if not any(item["path"].lower() == root.lower() for item in installs):
            installs.append(fallback_installation(base_path))
    return installs

def load_default_piece_catalog() -> list[dict[str, Any]]:
    return list(DEFAULT_PIECE_CATALOG)

def record_evidence(paths: RegistryPaths, action: str, target: dict[str, Any], before: Any, after: Any, result: str) -> dict[str, Any]:
    entry = {
        "evidence_id": f"evi-{hashlib.sha1(f'{action}:{now()}'.encode('utf-8')).hexdigest()[:10]}",
        "action": action,
        "target": target,
        "before": before,
        "after": after,
        "result": result,
        "timestamp": now(),
        "actor": getpass.getuser(),
        "session": f"pid:{os.getpid()}",
    }
    jsonl_append(paths.evidence, entry)
    return entry
