"""Operation-bound execution interface for commands dispatched by agents."""
from __future__ import annotations

import hashlib
import shlex
import sys
from pathlib import Path
from typing import Any


def execute_agent_command(
    argv: list[str], *, intent: str, manager: Any, timeout: int = 30,
) -> dict[str, Any]:
    """Run one exact BAGO CLI argv after a direct TTY Permit is consumed."""
    if manager is None:
        raise RuntimeError("Agent command requires the active SessionManager")
    if not sys.stdin.isatty():
        raise RuntimeError("Agent command execution requires direct TTY approval")
    if not isinstance(argv, list) or not argv or len(argv) > 64:
        raise ValueError("Agent command argv is invalid")
    clean_argv = [str(value) for value in argv]
    if any(not value or "\x00" in value or len(value) > 4096 for value in clean_argv):
        raise ValueError("Agent command argv contains an invalid argument")

    framework_root = Path(str(getattr(manager, "framework_root", "") or "")).expanduser().resolve(strict=True)
    launcher = framework_root / "bago_core" / "launcher.py"
    if not launcher.is_file():
        raise RuntimeError("Active BAGO launcher is unavailable")
    cwd = Path(str(getattr(manager, "base_path", "") or "")).expanduser().resolve(strict=True)
    session_id = str(getattr(manager, "session_id", "") or "").strip()
    if not cwd.is_dir() or not session_id:
        raise RuntimeError("Active SessionManager identity is incomplete")

    from execution_request import build_execution_request
    from bago_core.cli_execution import execute_cli_effect

    command_text = "bago " + shlex.join(clean_argv)
    request = build_execution_request(
        effect_id="process.execute", actor_kind="user",
        principal_id="interactive-local-user", session_id=session_id,
        source_surface="cli.agent.dispatch",
        target={
            "python_module": "bago_core.launcher",
            "python_root": str(framework_root),
            "python_module_sha256": hashlib.sha256(launcher.read_bytes()).hexdigest(),
            "cwd": str(cwd),
            "timeout_seconds": min(max(int(timeout), 1), 1800),
        },
        arguments={"argv": clean_argv}, scope="workspace",
    )
    result, authorization = execute_cli_effect(
        request,
        confirmation_text=f"agente {intent}: {command_text} (workspace {cwd})",
        manager=manager,
    )
    if not isinstance(authorization, dict) or authorization.get("state") != "consumed":
        raise RuntimeError("ExecutionGateway did not return consumed authorization")
    if not isinstance(result, dict) or result.get("executed") is not True:
        raise RuntimeError("ExecutionGateway returned no process execution receipt")
    return result
