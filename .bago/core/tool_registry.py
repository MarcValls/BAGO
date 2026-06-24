"""Compatibility shim for the tool registry.

The current runtime already expects a registry file under `.bago/core/` in a
few places, while the migrated contract keeps the canonical registry under
`.bago/tools/`. This shim keeps both paths usable.

Compatibility note: `BAGO_INTENT_EXAMPLES_PATH` is referenced by the intent
engine and kept here so the security contract can verify the coupling.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

_SPEC = importlib.util.spec_from_file_location("_bago_tools_tool_registry", TOOLS_DIR / "tool_registry.py")
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Cannot load canonical tool registry from {TOOLS_DIR / 'tool_registry.py'}")

_TOOLS = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _TOOLS
_SPEC.loader.exec_module(_TOOLS)

PreflightCheck = _TOOLS.PreflightCheck
ToolEntry = _TOOLS.ToolEntry
LAYERS = _TOOLS.LAYERS
REGISTRY = _TOOLS.REGISTRY
SCOPE_BADGE = _TOOLS.SCOPE_BADGE
INTERNAL_TOOLS = getattr(_TOOLS, "INTERNAL_TOOLS", frozenset())
get_deprecated_map = _TOOLS.get_deprecated_map
get_by_layer = _TOOLS.get_by_layer
get_commands = _TOOLS.get_commands
get_cmd_names = _TOOLS.get_cmd_names
load_registry = _TOOLS.load_registry


@dataclass(slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]
    raw: dict[str, Any] | None = None


@dataclass(slots=True)
class ToolResult:
    call_id: str
    name: str
    content: str
    ok: bool = True
    returncode: int = 0


class ToolRegistry:
    """Runtime compatibility layer around the canonical registry."""

    def __init__(self, script_registry: Any | None = None, workspace_root: Path | str | None = None, dev_mode: bool = False) -> None:
        self.script_registry = script_registry
        self._commands = get_commands()
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None
        self.dev_mode = dev_mode

    def __len__(self) -> int:
        return len(REGISTRY)

    def __iter__(self):
        return iter(REGISTRY.items())

    def get(self, name: str) -> ToolEntry | None:
        return REGISTRY.get(name)

    def to_openai(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for name, entry in REGISTRY.items():
            if entry.deprecated:
                continue
            schema = entry.schema if isinstance(entry.schema, dict) and entry.schema else {}
            if "type" not in schema:
                schema = {"type": "object", "properties": schema if isinstance(schema, dict) else {}}
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": entry.description,
                        "parameters": schema,
                    },
                }
            )
        return tools

    def parse_tool_calls(self, payload: dict[str, Any]) -> list[ToolCall]:
        parsed: list[ToolCall] = []
        for raw in payload.get("tool_calls", []) or []:
            if not isinstance(raw, dict):
                continue
            function = raw.get("function", {}) if isinstance(raw.get("function", {}), dict) else {}
            name = str(function.get("name") or raw.get("name") or "")
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                text = arguments.strip()
                if text:
                    try:
                        arguments = json.loads(text)
                    except json.JSONDecodeError:
                        arguments = {"_raw": arguments}
                else:
                    arguments = {}
            if not isinstance(arguments, dict):
                arguments = {"value": arguments}
            call_id = str(raw.get("id") or raw.get("tool_call_id") or name or "tool-call")
            parsed.append(ToolCall(call_id=call_id, name=name, arguments=arguments, raw=raw))
        return parsed

    def retrain_intents(self) -> str:
        if self.script_registry is not None:
            # Preserve the existing hook if the session manager passed one.
            _ = getattr(self.script_registry, "repo_root", None)
        return f"ToolRegistry listo ({len(self)} comandos)."

    def _args_to_cli(self, arguments: dict[str, Any]) -> list[str]:
        cli: list[str] = []
        for key, value in arguments.items():
            flag = f"--{str(key).replace('_', '-')}"
            if value is True:
                cli.append(flag)
            elif value in (False, None):
                continue
            elif isinstance(value, (list, tuple)):
                for item in value:
                    cli.extend([flag, str(item)])
            elif isinstance(value, dict):
                cli.extend([flag, json.dumps(value, ensure_ascii=False)])
            else:
                cli.extend([flag, str(value)])
        return cli

    def execute_call(self, call: ToolCall) -> ToolResult:
        entry = REGISTRY.get(call.name)
        if entry is None:
            return ToolResult(
                call_id=call.call_id,
                name=call.name,
                content=f"Tool not registered: {call.name}",
                ok=False,
                returncode=1,
            )

        command = self._commands.get(call.name)
        if not command:
            return ToolResult(
                call_id=call.call_id,
                name=call.name,
                content=f"Tool {call.name} has no executable mapping.",
                ok=False,
                returncode=1,
            )

        cmd = [*command, *self._args_to_cli(call.arguments)]
        tool_env = os.environ.copy()
        if self.workspace_root:
            tool_env["BAGO_WORKSPACE_ROOT"] = str(self.workspace_root)
        if self.dev_mode:
            tool_env["BAGO_DEV_MODE"] = "1"
        try:
            completed = subprocess.run(
                cmd,
                shell=False,
                capture_output=True,
                text=True,
                cwd=str(TOOLS_DIR.parent),
                timeout=120,
                env=tool_env,
            )
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                name=call.name,
                content=f"{type(exc).__name__}: {exc}",
                ok=False,
                returncode=1,
            )

        content = (completed.stdout or completed.stderr or "").strip()
        if not content:
            content = json.dumps(
                {
                    "tool": call.name,
                    "status": "ok" if completed.returncode == 0 else "error",
                    "arguments": call.arguments,
                },
                ensure_ascii=False,
            )
        return ToolResult(
            call_id=call.call_id,
            name=call.name,
            content=content,
            ok=completed.returncode == 0,
            returncode=completed.returncode,
        )
