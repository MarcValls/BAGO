# -*- coding: utf-8 -*-
"""tool_runner.py — Ejecuta herramientas BAGO como subprocess y devuelve resultado estructurado."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parents[3] / "tools"
BAGO_ROOT = TOOLS_DIR.parent


def _resolve_read_target(raw: str) -> str:
    target = (raw or "").strip()
    if not target:
        return target
    p = Path(target)
    if p.exists():
        return str(p)
    if "/path/to/" in target or "\\path\\to\\" in target or target.startswith("/path/to/"):
        candidate_name = p.name or target.split("/")[-1] or target.split("\\")[-1]
    else:
        candidate_name = p.name or target
    if not candidate_name:
        return target
    matches = []
    try:
        for m in BAGO_ROOT.rglob(candidate_name):
            if m.is_file():
                matches.append(m)
    except Exception:
        return target
    if matches:
        return str(matches[0])
    return target


def run_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta una herramienta BAGO y devuelve resultado estructurado."""
    cmd = [sys.executable, str(TOOLS_DIR / f"{name}.py")]

    if name == "bago_search":
        cmd.extend([arguments.get("keyword", "")])
        if arguments.get("directory"):
            cmd.append(arguments["directory"])
        if arguments.get("synonyms"):
            cmd.append("--synonyms")
        if arguments.get("metaphors"):
            cmd.append("--metaphors")

    elif name == "bago_list":
        if arguments.get("directory"):
            cmd.append(arguments["directory"])
        for flag in ("tree", "git", "sizes", "json"):
            if arguments.get(flag):
                cmd.append(f"--{flag}")

    elif name == "bago_read":
        cmd.append(_resolve_read_target(arguments.get("filepath", "")))
        if arguments.get("lines"):
            cmd.extend(["--lines", str(arguments["lines"])])
        if arguments.get("context") and arguments["context"] != "none":
            cmd.extend(["--context", arguments["context"]])

    elif name == "bago_call_search":
        cmd.append(arguments.get("query", ""))
        if arguments.get("lang") and arguments["lang"] != "all":
            cmd.extend(["--lang", arguments["lang"]])
        if arguments.get("def"):
            cmd.append("--def")

    elif name == "bago_grep_smart":
        cmd.append(arguments.get("pattern", ""))
        for flag in ("def", "call", "import"):
            if arguments.get(flag):
                cmd.append(f"--{flag}")
        if arguments.get("ext"):
            cmd.extend(["--ext", arguments["ext"]])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            cwd=str(BAGO_ROOT.parent)
        )
        stdout = result.stdout[:8000]
        stderr = result.stderr[:2000]
        return {
            "tool": name,
            "arguments": arguments,
            "exit_code": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "success": result.returncode == 0
        }
    except Exception as exc:
        return {
            "tool": name,
            "arguments": arguments,
            "exit_code": -1,
            "error": str(exc),
            "success": False
        }
