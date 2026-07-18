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

# Minimal guaranteed tools exposed even when tools.manifest.json is absent.
_FALLBACK_TOOLS: dict = {
    "file-write": {
        "cmd": "file-write",
        "file": "file_write.py",
        "description": "Write or create a file inside the active workspace. Required args: path (relative), content (string).",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path, e.g. prueba.md"},
                "content": {"type": "string", "description": "Text content to write"},
            },
            "required": ["path", "content"],
        },
    },
    "file-read": {
        "cmd": "file-read",
        "file": "file_read.py",
        "description": "Read a file from the active workspace. Required arg: path (relative).",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path to read"},
            },
            "required": ["path"],
        },
    },
    "dir-list": {
        "cmd": "dir-list",
        "file": "dir_list.py",
        "description": "List files and directories inside a workspace path.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative directory path (default: workspace root)"},
            },
            "required": [],
        },
    },
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

# Start with fallback tools, then overlay whatever the manifest declares.
_merged_tools: dict = dict(_FALLBACK_TOOLS)
_merged_tools.update(_tools)

REGISTRY: dict[str, ToolEntry] = {}
for _name, _payload in _merged_tools.items():
    _cmd = str(_payload.get("cmd", _name)).strip()
    if not _cmd or _cmd in _EXCLUDED_CMDS:
        continue
    # Only register if the backing .py file actually exists (skip on missing tool files)
    _module_stem = Path(str(_payload.get("file", f"{_cmd}.py"))).stem
    if not (TOOLS_DIR / f"{_module_stem}.py").exists():
        continue
    REGISTRY[_cmd] = _entry_from_manifest(_cmd, _payload if isinstance(_payload, dict) else {})


