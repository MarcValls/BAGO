from __future__ import annotations

import importlib.util
from pathlib import Path


def load_tool_module(module_name: str, file_name: str):
    here = Path(__file__).resolve()
    path = here.with_name(file_name)
    if not path.exists():
        tools_dir = here.parents[1] / "tools" / file_name
        if tools_dir.exists():
            path = tools_dir
    spec = importlib.util.spec_from_file_location(f"bago.chat.{module_name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {file_name}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_args(args: list[str]) -> tuple[list[str], dict[str, str | bool]]:
    positional: list[str] = []
    flags: dict[str, str | bool] = {}
    for arg in args:
        if arg.startswith("--"):
            if "=" in arg:
                key, val = arg[2:].split("=", 1)
                flags[key] = val
            else:
                flags[arg[2:]] = True
        else:
            positional.append(arg)
    return positional, flags


def parse_project_args(args: list[str]) -> tuple[str, str]:
    actions = {"analyze", "status", "init", "link", "seed", "sync"}
    if not args:
        return "analyze", ""
    first = args[0].lower()
    if first in actions:
        return first, (args[1] if len(args) > 1 else "")
    root = args[0]
    action = args[1].lower() if len(args) > 1 and args[1].lower() in actions else "analyze"
    return action, root
