"""creation_mode — BAGO Creation Mode: motor de trabajo con capas arquitectónicas.

Puede usarse como:
  • App standalone:  python -m creation_mode
  • Plugin BAGO:     from creation_mode.engine import main; main()
  • Librería:        from creation_mode.renderer import build_layout
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

__version__ = "1.0.0"

from .engine import main, render_once, run_interactive
from .renderer import build_layout
from .data import (
    load_global_state, load_recent_sessions, load_agents, load_tools_count,
    load_active_task, load_project, load_projects, load_issues,
)
from .layers import LAYERS, matches_layer
from .git_tools import preview_file, run_command, git_status_lines, git_file_tree
from .commands import save_milestone

__all__ = [
    "main", "render_once", "run_interactive", "build_layout",
    "load_global_state", "load_recent_sessions", "load_agents", "load_tools_count",
    "load_active_task", "load_project", "load_projects", "load_issues",
    "LAYERS", "matches_layer",
    "preview_file", "run_command", "git_status_lines", "git_file_tree",
    "save_milestone",
]
