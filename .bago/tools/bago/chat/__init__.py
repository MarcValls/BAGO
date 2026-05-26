"""bago.chat — submódulos del REPL de BAGO."""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .statusbar   import _bee_tick, _topbar_prompt, _bottom_bar, _prompt_indicator
from .startup_ui  import _startup_choice_curses, _chat_curses
from .recovery    import _ollama_recovery_flow, _cloud_recovery_flow
from .boot        import resolve_session, run_startup_tasks
from .repl        import run_repl

__all__ = [
    "_bee_tick", "_topbar_prompt", "_bottom_bar", "_prompt_indicator",
    "_startup_choice_curses", "_chat_curses",
    "_ollama_recovery_flow", "_cloud_recovery_flow",
    "resolve_session", "run_startup_tasks",
    "run_repl",
]
