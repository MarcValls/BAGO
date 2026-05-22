from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from bago_core.launcher._paths import (
    BAGO_ROOT, BAGO_CORE_DIR, TOOLS, CORE,
    GREEN, RED, YELLOW, CYAN, BOLD, DIM, default_user_home,
)
from bago_core.launcher._config import (
    load_bp, load_dispatcher, load_context, load_registry_mod,
    build_commands, build_deprecated_map, get_module_for_cmd,
    COMMANDS, DEPRECATED_MAP,
)


def _cmd_token_analytics(rest: list) -> None:
    import subprocess, sys as _sys
    analytics_path = CORE / "token_analytics.py"
    if not analytics_path.exists():
        print("  No se encuentra token_analytics.py")
        return
    subprocess.run([_sys.executable, str(analytics_path), "--bago-root", str(BAGO_ROOT.parent)] + rest, cwd=str(BAGO_ROOT.parent))


def _cmd_token_brake(rest: list) -> None:
    import subprocess, sys as _sys
    brake_path = TOOLS / "token_brake.py"
    if not brake_path.exists():
        print("  No se encuentra token_brake.py")
        return
    subprocess.run([_sys.executable, str(brake_path), "--bago-root", str(BAGO_ROOT.parent)] + rest, cwd=str(BAGO_ROOT.parent))


def _cmd_spiral_prompt(rest: list) -> None:
    import importlib.util, sys as _sys
    builder_path = CORE / "spiral_prompt_builder.py"
    if not builder_path.exists():
        print("  No se encuentra spiral_prompt_builder.py")
        return
    spec = importlib.util.spec_from_file_location("spiral_prompt_builder", str(builder_path))
    mod = importlib.util.module_from_spec(spec)
    if str(CORE) not in _sys.path:
        _sys.path.insert(0, str(CORE))
    spec.loader.exec_module(mod)
    builder = mod.SpiralPromptBuilder(str(BAGO_ROOT.parent))
    role_id = ""
    cycle = 1
    radius = 1.0
    task_type = ""
    for i, arg in enumerate(rest):
        if arg == "--role" and i + 1 < len(rest):
            role_id = rest[i + 1]
        elif arg == "--cycle" and i + 1 < len(rest):
            cycle = int(rest[i + 1])
        elif arg == "--radius" and i + 1 < len(rest):
            radius = float(rest[i + 1])
        elif arg == "--task-type" and i + 1 < len(rest):
            task_type = rest[i + 1]
    if not role_id:
        print("  Uso: bago spiral-prompt --role ROLE [--cycle N] [--radius R] [--task-type T]")
        return
    prompt = builder.build(role_id=role_id, cycle=cycle, radius=radius, task_type=task_type)
    print(prompt)


def _cmd_autonomous(rest: list) -> None:
    """bago autonomous [--dry-run] [--loop] [--unsafe] [--max-cycles N] [--verbose] [--json]"""
    import importlib.util, sys as _sys
    _loop_path = CORE / "autonomous_loop.py"
    if not _loop_path.exists():
        print("  ❌ No se encuentra autonomous_loop.py en .bago/core/")
        return
    spec = importlib.util.spec_from_file_location("autonomous_loop", str(_loop_path))
    mod  = importlib.util.module_from_spec(spec)
    if str(CORE) not in _sys.path:
        _sys.path.insert(0, str(CORE))
    spec.loader.exec_module(mod)

    if "--json" in rest:
        # JSON sense+plan snapshot
        from io import StringIO
        import json
        loop = mod.AutonomousLoop(
            dry_run    = "--dry-run" in rest,
            unsafe     = "--unsafe" in rest,
            max_cycles = int(rest[rest.index("--max-cycles") + 1]) if "--max-cycles" in rest else mod.MAX_CYCLES_DEFAULT,
            verbose    = "--verbose" in rest,
        )
        state = loop.sense()
        plan  = loop.plan(state)
        print(json.dumps({
            "state": {k: v for k, v in state.items() if k != "inbox_tasks"},
            "inbox_count": len(state.get("inbox_tasks", [])),
            "plan": [{"goal": g["goal"], "agent": g["agent"], "skip": g.get("skip", False),
                       "reason": g["reason"]} for g in plan],
        }, indent=2, ensure_ascii=False))
        return

    loop = mod.AutonomousLoop(
        dry_run    = "--dry-run" in rest,
        unsafe     = "--unsafe" in rest,
        max_cycles = int(rest[rest.index("--max-cycles") + 1]) if "--max-cycles" in rest else mod.MAX_CYCLES_DEFAULT,
        verbose    = "--verbose" in rest,
    )
    loop.run(loop_mode="--loop" in rest)


def _cmd_inbox_launcher(rest: list) -> None:
    """bago inbox [add <intent>] [list] [clear]"""
    import importlib.util, sys as _sys
    _loop_path = CORE / "autonomous_loop.py"
    if not _loop_path.exists():
        print("  ❌ No se encuentra autonomous_loop.py en .bago/core/")
        return
    spec = importlib.util.spec_from_file_location("autonomous_loop", str(_loop_path))
    mod  = importlib.util.module_from_spec(spec)
    if str(CORE) not in _sys.path:
        _sys.path.insert(0, str(CORE))
    spec.loader.exec_module(mod)
    mod.cmd_inbox(rest)


if __name__ == "__main__":
    main()





def _cmd_router(rest: list) -> None:
    """bago router [scan|route|default|status|tokens|serve] -- BAGO Model Router."""
    import subprocess, sys as _sys
    router_path = TOOLS / 'bago_model_router.py'
    if not router_path.exists():
        print('  No se encuentra bago_model_router.py')
        return
    subprocess.run([_sys.executable, str(router_path)] + rest, cwd=str(BAGO_ROOT.parent))
