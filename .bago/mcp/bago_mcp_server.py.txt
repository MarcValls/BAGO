#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bago_mcp_server.py — MCP readonly bridge for BAGO.

Transport:
  STDIO JSON-RPC, one JSON message per line.

Purpose:
  Expose a safe BAGO control plane to GitHub Copilot:
  status, health, validate, context, secrets, review, risk, why, scope, audit.

Security posture:
  - Readonly by default.
  - No dangerous commands.
  - No arbitrary shell.
  - No wildcard passthrough.
  - Mutating/dangerous commands require explicit env opt-in, but this server
    intentionally does not expose them in DEFAULT_TOOLS.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Encoding hardening
# ---------------------------------------------------------------------------

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

try:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()

# Expected path:
#   <repo>/.bago/mcp/bago_mcp_server.py
DEFAULT_REPO_ROOT = _THIS_FILE.parents[2]

REPO_ROOT = Path(
    os.environ.get("BAGO_ROOT")
    or os.environ.get("BAGO_PADRE_PATH")
    or str(DEFAULT_REPO_ROOT)
).resolve()

BAGO_DIR = REPO_ROOT / ".bago"
TOOLS_DIR = BAGO_DIR / "tools"
CORE_DIR = BAGO_DIR / "core"
BAGO_BIN = REPO_ROOT / "bago"
REGISTRY_PATH = TOOLS_DIR / "tool_registry.py"

MAX_OUTPUT_CHARS = int(os.environ.get("BAGO_MCP_MAX_OUTPUT_CHARS", "24000"))

READONLY_MODE = os.environ.get("BAGO_MCP_MODE", "readonly").strip().lower() != "write"
ALLOW_MUTATING = os.environ.get("BAGO_ALLOW_MUTATING", "0").strip() == "1"
ALLOW_DANGEROUS = os.environ.get("BAGO_ALLOW_DANGEROUS", "0").strip() == "1"


# ---------------------------------------------------------------------------
# Tool policy
# ---------------------------------------------------------------------------

# MCP tool name -> BAGO command.
# Keep this small. This is the control-plane surface.
DEFAULT_TOOLS: dict[str, dict[str, Any]] = {
    "bago_status": {
        "cmd": "status",
        "description": "Estado actual de BAGO: flujo activo, tarea pendiente y salud del sistema.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "bago_health": {
        "cmd": "health",
        "description": "Salud del framework BAGO. Modo opcional: score, report, stability, efficiency, consistency, sincerity.",
        "schema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["", "score", "report", "stability", "efficiency", "consistency", "sincerity"],
                    "default": "",
                }
            },
            "additionalProperties": False,
        },
    },
    "bago_validate": {
        "cmd": "validate",
        "description": "Validación readonly del pack BAGO.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "bago_context": {
        "cmd": "context",
        "description": "Contexto del workspace. Modo opcional: detect, map, git, stale.",
        "schema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["", "detect", "map", "git", "stale"],
                    "default": "",
                }
            },
            "additionalProperties": False,
        },
    },
    "bago_secrets": {
        "cmd": "secrets",
        "description": "Escaneo de secretos/credenciales expuestas.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "bago_review": {
        "cmd": "review",
        "description": "Code review automatizado BAGO en modo seguro.",
        "schema": {
            "type": "object",
            "properties": {
                "ci": {"type": "boolean", "default": False},
                "json": {"type": "boolean", "default": False},
                "changed_only": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        },
    },
    "bago_risk": {
        "cmd": "risk",
        "description": "Matriz de riesgo del proyecto.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "bago_why": {
        "cmd": "why",
        "description": "Explica qué hace un comando BAGO y cuándo usarlo.",
        "schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Nombre de comando BAGO. Ejemplo: health, audit, review, context.",
                }
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
    "bago_scope": {
        "cmd": "scope",
        "description": "Detecta scope framework/project/both de scripts Python por análisis estático.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "bago_audit": {
        "cmd": "audit",
        "description": "Auditoría BAGO readonly. Solo modos permitidos: quality, purity, scan, pack.",
        "schema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["", "quality", "purity", "scan", "pack"],
                    "default": "",
                }
            },
            "additionalProperties": False,
        },
    },
    "bago_registry": {
        "cmd": None,
        "description": "Lista los comandos BAGO visibles para este servidor MCP y su clasificación.",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}

SAFE_BAGO_COMMANDS = {
    "status",
    "health",
    "validate",
    "context",
    "secrets",
    "review",
    "risk",
    "why",
    "scope",
    "audit",
}

BLOCKED_BAGO_COMMANDS = {
    "auto",
    "autonomous",
    "cabinet",
    "db",
    "install",
    "orchestrate",
    "peer",
    "siembra",
    "deactivate",
    "heal",
    "sync",
    "version",
    "project",
    "learn",
    "promote",
}


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def _load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {}

    try:
        spec = importlib.util.spec_from_file_location("_bago_tool_registry", str(REGISTRY_PATH))
        if spec is None or spec.loader is None:
            return {}

        mod = importlib.util.module_from_spec(spec)
        sys.modules["_bago_tool_registry"] = mod
        spec.loader.exec_module(mod)
        registry = getattr(mod, "REGISTRY", {})
        return registry if isinstance(registry, dict) else {}
    except Exception:
        return {}


def _entry_to_dict(name: str, entry: Any) -> dict[str, Any]:
    return {
        "cmd": getattr(entry, "cmd", name),
        "module": getattr(entry, "module", ""),
        "description": getattr(entry, "description", ""),
        "stability": getattr(entry, "stability", "unknown"),
        "risk": getattr(entry, "risk", "unknown"),
        "layer": getattr(entry, "layer", ""),
        "scope": getattr(entry, "scope", ""),
        "agent": getattr(entry, "agent", ""),
        "deprecated": bool(getattr(entry, "deprecated", False)),
        "supports_dry_run": bool(getattr(entry, "supports_dry_run", False)),
    }


def _registry_snapshot() -> str:
    registry = _load_registry()
    exposed: list[dict[str, Any]] = []

    for mcp_name, meta in DEFAULT_TOOLS.items():
        cmd = meta.get("cmd")
        if cmd is None:
            exposed.append({
                "mcp_tool": mcp_name,
                "bago_cmd": None,
                "description": meta["description"],
                "source": "mcp",
            })
            continue

        entry = registry.get(cmd)
        if entry is not None:
            row = _entry_to_dict(cmd, entry)
        else:
            row = {
                "cmd": cmd,
                "description": meta["description"],
                "stability": "unknown",
                "risk": "unknown",
            }

        row["mcp_tool"] = mcp_name
        row["bago_cmd"] = cmd
        exposed.append(row)

    payload = {
        "server": "bago-mcp",
        "repo_root": str(REPO_ROOT),
        "readonly_mode": READONLY_MODE,
        "allow_mutating": ALLOW_MUTATING,
        "allow_dangerous": ALLOW_DANGEROUS,
        "exposed_tools": exposed,
        "blocked_commands": sorted(BLOCKED_BAGO_COMMANDS),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# BAGO execution
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    if not text:
        return ""

    # Avoid protocol confusion: MCP stdio messages are one JSON object per line.
    # Tool output is embedded as JSON string, so newlines are safe after json.dumps.
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if len(text) > MAX_OUTPUT_CHARS:
        text = text[:MAX_OUTPUT_CHARS] + f"\n\n[truncated at {MAX_OUTPUT_CHARS} chars]"
    return text


def _validate_bago_command(cmd: str) -> None:
    if cmd in BLOCKED_BAGO_COMMANDS:
        raise ValueError(f"Blocked BAGO command for MCP readonly server: {cmd}")

    if cmd not in SAFE_BAGO_COMMANDS:
        raise ValueError(f"Command not exposed by BAGO MCP policy: {cmd}")

    registry = _load_registry()
    entry = registry.get(cmd)

    if entry is None:
        # Allow execution anyway if launcher knows it, but keep policy strict.
        return

    risk = getattr(entry, "risk", "safe")
    stability = getattr(entry, "stability", "experimental")

    if stability == "dangerous" and not ALLOW_DANGEROUS:
        raise ValueError(f"Dangerous command blocked: {cmd}")

    if risk == "mutating" and (READONLY_MODE or not ALLOW_MUTATING):
        raise ValueError(f"Mutating command blocked in readonly mode: {cmd}")

    if risk == "dangerous" and not ALLOW_DANGEROUS:
        raise ValueError(f"Dangerous command blocked: {cmd}")


def _launcher_command(cmd: str, args: list[str]) -> list[str]:
    if BAGO_BIN.exists():
        return [sys.executable, str(BAGO_BIN), cmd, *args]

    registry = _load_registry()
    entry = registry.get(cmd)

    if entry is None:
        raise FileNotFoundError(f"No BAGO launcher found at {BAGO_BIN} and command not in registry: {cmd}")

    module = getattr(entry, "module", "")
    if not module:
        raise FileNotFoundError(f"Registry entry for {cmd} has no module")

    tool_path = TOOLS_DIR / f"{module}.py"
    core_path = CORE_DIR / f"{module}.py"

    if tool_path.exists():
        return [sys.executable, str(tool_path), *args]
    if core_path.exists():
        return [sys.executable, str(core_path), *args]

    raise FileNotFoundError(f"No module file found for BAGO command {cmd}: {module}.py")


def _run_bago(cmd: str, args: list[str] | None = None, timeout: int = 90) -> tuple[int, str]:
    args = args or []
    _validate_bago_command(cmd)

    env = os.environ.copy()
    env["BAGO_ROOT"] = str(REPO_ROOT)
    env["BAGO_PADRE_PATH"] = str(REPO_ROOT)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    command = _launcher_command(cmd, args)

    try:
        proc = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            input="",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, _clean_text(output)
    except subprocess.TimeoutExpired:
        return -1, f"Timeout ejecutando BAGO command: {cmd}"
    except Exception as exc:
        return -1, f"Error ejecutando BAGO command {cmd}: {exc}"


# ---------------------------------------------------------------------------
# MCP tool calls
# ---------------------------------------------------------------------------

_CMD_RE = re.compile(r"^[a-z][a-z0-9_-]{0,64}$")


def _args_for_tool(tool_name: str, params: dict[str, Any]) -> tuple[str | None, list[str]]:
    meta = DEFAULT_TOOLS[tool_name]
    cmd = meta.get("cmd")

    if cmd is None:
        return None, []

    if tool_name == "bago_health":
        mode = str(params.get("mode", "") or "").strip()
        return cmd, [mode] if mode else []

    if tool_name == "bago_context":
        mode = str(params.get("mode", "") or "").strip()
        return cmd, [mode] if mode else []

    if tool_name == "bago_audit":
        mode = str(params.get("mode", "") or "").strip()
        # Never allow audit heal/push/doctor through MCP.
        if mode not in {"", "quality", "purity", "scan", "pack"}:
            raise ValueError(f"Audit mode not allowed through MCP: {mode}")
        return cmd, [mode] if mode else []

    if tool_name == "bago_review":
        args: list[str] = []
        if bool(params.get("ci", False)):
            args.append("--ci")
        if bool(params.get("json", False)):
            args.append("--json")
        if bool(params.get("changed_only", False)):
            args.append("--changed-only")
        return cmd, args

    if tool_name == "bago_why":
        command = str(params.get("command", "") or "").strip()
        if not _CMD_RE.match(command):
            raise ValueError("Invalid BAGO command name for bago_why")
        if command in BLOCKED_BAGO_COMMANDS:
            raise ValueError(f"bago_why blocked for dangerous/mutating command: {command}")
        return cmd, [command]

    return cmd, []


def _call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in DEFAULT_TOOLS:
        return {
            "content": [{"type": "text", "text": f"Unknown MCP tool: {name}"}],
            "isError": True,
        }

    arguments = arguments or {}

    try:
        cmd, args = _args_for_tool(name, arguments)

        if cmd is None:
            text = _registry_snapshot()
            return {"content": [{"type": "text", "text": text}], "isError": False}

        rc, output = _run_bago(cmd, args)

        if not output.strip():
            output = f"BAGO command finished with exit code {rc}: bago {cmd} {' '.join(args)}"

        prefix = f"$ bago {cmd} {' '.join(args)}".strip()
        text = f"{prefix}\n\n{output}"

        return {
            "content": [{"type": "text", "text": text}],
            "isError": rc != 0,
        }

    except Exception as exc:
        return {
            "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
            "isError": True,
        }


# ---------------------------------------------------------------------------
# JSON-RPC / MCP
# ---------------------------------------------------------------------------

def _write(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _result(msg_id: Any, result: Any) -> None:
    _write({"jsonrpc": "2.0", "id": msg_id, "result": result})


def _error(msg_id: Any, code: int, message: str, data: Any | None = None) -> None:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if data is not None:
        payload["error"]["data"] = data
    _write(payload)


def _tools_list() -> dict[str, Any]:
    tools = []
    for name, meta in DEFAULT_TOOLS.items():
        tools.append({
            "name": name,
            "description": meta["description"],
            "inputSchema": meta["schema"],
        })
    return {"tools": tools}


def _handle_request(message: dict[str, Any]) -> None:
    msg_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    # Notifications have no id. Do not respond.
    is_notification = "id" not in message

    try:
        if method == "initialize":
            if is_notification:
                return
            _result(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "bago",
                    "version": "0.1.0",
                },
            })
            return

        if method == "notifications/initialized":
            return

        if method == "ping":
            if not is_notification:
                _result(msg_id, {})
            return

        if method == "tools/list":
            if not is_notification:
                _result(msg_id, _tools_list())
            return

        if method == "tools/call":
            if is_notification:
                return

            name = params.get("name")
            arguments = params.get("arguments") or {}

            if not isinstance(name, str):
                _error(msg_id, -32602, "tools/call requires params.name")
                return

            if not isinstance(arguments, dict):
                _error(msg_id, -32602, "tools/call params.arguments must be an object")
                return

            _result(msg_id, _call_tool(name, arguments))
            return

        # Return empty optional surfaces to keep clients calm.
        if method == "resources/list":
            if not is_notification:
                _result(msg_id, {"resources": []})
            return

        if method == "prompts/list":
            if not is_notification:
                _result(msg_id, {"prompts": []})
            return

        if method == "logging/setLevel":
            if not is_notification:
                _result(msg_id, {})
            return

        if not is_notification:
            _error(msg_id, -32601, f"Method not found: {method}")

    except Exception as exc:
        if not is_notification:
            _error(
                msg_id,
                -32603,
                f"Internal error: {exc}",
                traceback.format_exc(limit=8),
            )


def main() -> int:
    if "--self-test" in sys.argv:
        print("BAGO MCP self-test")
        print(f"REPO_ROOT={REPO_ROOT}")
        print(f"BAGO_BIN={BAGO_BIN} exists={BAGO_BIN.exists()}")
        print(f"REGISTRY_PATH={REGISTRY_PATH} exists={REGISTRY_PATH.exists()}")
        print(f"TOOLS={', '.join(DEFAULT_TOOLS.keys())}")
        return 0

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError as exc:
            _error(None, -32700, f"Parse error: {exc}")
            continue

        if not isinstance(message, dict):
            _error(None, -32600, "Invalid Request: JSON-RPC message must be an object")
            continue

        _handle_request(message)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())