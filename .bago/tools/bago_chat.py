
#!/usr/bin/env python3
"""BAGO Orchestrator HUB — Entry point (thin glue)"""
import argparse
import sys
from pathlib import Path

# ── Activar VT/ANSI en Windows CMD lo antes posible ──────────────────────────
if sys.platform == "win32":
    try:
        import ctypes as _ct
        _k = _ct.windll.kernel32
        _h = _k.GetStdHandle(-11)
        _m = _ct.c_ulong(0)
        if _k.GetConsoleMode(_h, _ct.byref(_m)):
            _k.SetConsoleMode(_h, _m.value | 0x0004)
    except Exception:
        pass
# ─────────────────────────────────────────────────────────────────────────────

sys.path.insert(0, str(Path(__file__).parent))

from bago.chat.boot import resolve_session, run_startup_tasks
from bago.chat.repl import build_prompt_session, run_repl


def main():
    p = argparse.ArgumentParser(description="BAGO Orchestrator HUB")
    p.add_argument("--provider", default="")
    p.add_argument("--model",    default="")
    p.add_argument("--task",     default="")
    args = p.parse_args()

    session = resolve_session(args)
    run_startup_tasks(session)
    pt = build_prompt_session()
    run_repl(session, pt)


if __name__ == "__main__":
    main()
