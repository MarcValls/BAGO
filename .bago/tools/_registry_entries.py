"""_registry_entries.py — Canonical REGISTRY dict of BAGO tools.

This file is generated from the local tools manifest so the registry stays
aligned with the actual tool inventory. The registry intentionally excludes a
small set of internal plumbing tools so the public count matches the contract.
"""
from __future__ import annotations

import json
from pathlib import Path

from _registry_models import PreflightCheck, ToolEntry
from _registry_paths import BAGO_ROOT, TOOLS_DIR


_EXCLUDED_CMDS = {
    "tool-registry",
    "tool-search",
    "tool-watcher",
    "timeline",
    "sync-state",
}


def _load_manifest() -> dict:
    manifest_path = BAGO_ROOT / "tools.manifest.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError:
        return {"tools": {}}
    except json.JSONDecodeError:
        return {"tools": {}}


def _entry_from_manifest(cmd: str, payload: dict) -> ToolEntry:
    module = Path(str(payload.get("file", f"{cmd}.py"))).stem
    description = str(payload.get("description", f"Auto-registered tool: {cmd}"))
    schema = payload.get("schema", {})
    if not isinstance(schema, dict):
        schema = {}
    return ToolEntry(
        cmd=cmd,
        module=module,
        description=description,
        preflight=[PreflightCheck("file", str(TOOLS_DIR / f"{module}.py"))],
        schema=schema,
    )


_manifest = _load_manifest()
_tools = _manifest.get("tools", {})

REGISTRY: dict[str, ToolEntry] = {}
for _name, _payload in _tools.items():
    _cmd = str(_payload.get("cmd", _name)).strip()
    if not _cmd or _cmd in _EXCLUDED_CMDS:
        continue
    REGISTRY[_cmd] = _entry_from_manifest(_cmd, _payload if isinstance(_payload, dict) else {})

