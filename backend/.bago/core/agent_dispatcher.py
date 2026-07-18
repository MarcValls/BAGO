#!/usr/bin/env python3
"""
agent_dispatcher.py — BAGO v3.0 Agent Dispatcher

Routes BAGO commands to their responsible agents (informational dispatch).
Provides env-var injection, structured logging, and before/after events.

This is metadata dispatch — no LLM calls. Each command declares its
"home agent" via ToolEntry.agent. The dispatcher logs the assignment,
injects BAGO_AGENT into the subprocess environment, and emits events.

Future: when BAGO_AGENT_LLM=1, dispatch can delegate to an LLM-backed
agent that reasons about the command before/after execution.

Lives at: .bago/core/agent_dispatcher.py
Usage from bago launcher:
    from agent_dispatcher import prepare_dispatch, finalize_dispatch
    env_patch = prepare_dispatch(ctx, cmd, entry)
    # ... run subprocess with env_patch merged into os.environ ...
    finalize_dispatch(ctx, cmd, entry.agent, returncode)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from bago_context import BagoContext

# ── Fallback default agent ─────────────────────────────────────────────────────
_DEFAULT_AGENT = "ORGANIZADOR"

# ── Role file search root ──────────────────────────────────────────────────────
_THIS_FILE = Path(__file__).resolve()
_ROOT      = Path(os.environ.get("BAGO_PADRE_PATH") or _THIS_FILE.parents[2])
_ROLES_DIR = _ROOT / ".bago" / "roles"


# ── Agent resolution ───────────────────────────────────────────────────────────

def resolve_agent(entry: Any) -> str:
    """
    Return the agent name from a ToolEntry (or fallback if not set).
    Works on any object with an .agent attribute or dict with "agent" key.
    """
    if hasattr(entry, "agent"):
        return entry.agent or _DEFAULT_AGENT
    if isinstance(entry, dict):
        return entry.get("agent") or _DEFAULT_AGENT
    return _DEFAULT_AGENT


def agent_file(agent_name: str) -> Path | None:
    """Return the .md role file for *agent_name* (searches all role subdirs)."""
    for md in _ROLES_DIR.rglob(f"{agent_name}.md"):
        return md
    return None


# ── Dispatch lifecycle ─────────────────────────────────────────────────────────

def prepare_dispatch(ctx: "BagoContext", cmd: str, entry: Any, verbose: bool = False) -> dict[str, str]:
    """
    Prepare agent dispatch for a command BEFORE running the subprocess.

    Actions:
    - Resolves the responsible agent
    - Logs dispatch → [AGENT] `bago <cmd>`
    - Optionally prints to stderr (verbose mode)
    - Emits dispatch:before event (via ctx.emit)

    Returns a dict of env vars to merge into the subprocess environment.
    The subprocess receives:
        BAGO_AGENT    = agent name
        BAGO_CMD      = command
        BAGO_ROOT     = framework root path
        BAGO_VERSION  = current version
    """
    agent = resolve_agent(entry)

    ctx.log("info", f"dispatch → [{agent}] `bago {cmd}`", tool="dispatcher")

    if verbose:
        role_path = agent_file(agent)
        role_hint = f" ({role_path.relative_to(_ROOT)})" if role_path else ""
        print(f"  🎯 [{agent}]{role_hint} → bago {cmd}", file=sys.stderr)

    ctx.emit("dispatch:before", {
        "cmd":   cmd,
        "agent": agent,
        "ts":    datetime.now(timezone.utc).isoformat(),
    })

    return {
        "BAGO_AGENT":   agent,
        "BAGO_CMD":     cmd,
        "BAGO_ROOT":    str(ctx.root),
        "BAGO_VERSION": ctx.version,
    }


def finalize_dispatch(ctx: "BagoContext", cmd: str, agent: str, returncode: int) -> None:
    """
    Finalize agent dispatch AFTER the subprocess exits.

    Actions:
    - Logs result
    - Emits dispatch:after event
    - Flushes any events written by the tool subprocess (from events.jsonl)
    """
    status = "ok" if returncode == 0 else "error"
    level  = "info" if returncode == 0 else "warn"

    ctx.log(level, f"dispatch ← [{agent}] `bago {cmd}` → {status} (rc={returncode})", tool="dispatcher")

    ctx.emit("dispatch:after", {
        "cmd":        cmd,
        "agent":      agent,
        "returncode": returncode,
        "status":     status,
        "ts":         datetime.now(timezone.utc).isoformat(),
    })

    # Process any events emitted by the tool subprocess
    ctx.flush_events()


# ── Query API ──────────────────────────────────────────────────────────────────

def list_agent_commands(registry: dict) -> dict[str, list[str]]:
    """
    Return a mapping of {agent_name: [cmd1, cmd2, ...]} from the full registry.
    Useful for `bago dispatch --list` (future command).
    """
    result: dict[str, list[str]] = {}
    for cmd, entry in registry.items():
        agent = resolve_agent(entry)
        result.setdefault(agent, []).append(cmd)
    return {k: sorted(v) for k, v in sorted(result.items())}


# ── Self-test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Add core to path so we can import bago_context
    sys.path.insert(0, str(_THIS_FILE.parent))
    from bago_context import get_context  # noqa: E402 (local import for test)

    ctx = get_context()
    print(f"BAGO_ROOT  : {ctx.root}")
    print(f"ROLES_DIR  : {_ROLES_DIR} (exists={_ROLES_DIR.exists()})")

    # Simulate a dispatch cycle with a mock entry
    class MockEntry:
        agent = "VALIDADOR"

    entry = MockEntry()
    env = prepare_dispatch(ctx, "health", entry, verbose=True)
    print(f"env_patch  : {env}")
    finalize_dispatch(ctx, "health", entry.agent, returncode=0)

    # List by agent (uses real registry)
    sys.path.insert(0, str(ctx.tools_dir))
    try:
        import tool_registry as _reg
        mapping = list_agent_commands(_reg.REGISTRY)
        total = sum(len(v) for v in mapping.values())
        print(f"\nAgent dispatch map ({total} commands across {len(mapping)} agents):")
        for agent_name, cmds in mapping.items():
            print(f"  {agent_name:30s}: {', '.join(cmds)}")
    except Exception as exc:
        print(f"Registry load skipped: {exc}")

    print("\n✅ agent_dispatcher self-test passed")
