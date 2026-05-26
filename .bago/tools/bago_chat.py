
#!/usr/bin/env python3
"""BAGO Orchestrator HUB — Entry point (thin glue)"""
import argparse
import os
import sys
from pathlib import Path

from bago.ollama_runtime import DEFAULT_BAGO_API_PORT, env_port

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

# Forzar UTF-8 para evitar crashes en consolas Windows con CP1252.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).parent))

from bago.chat.boot import resolve_session, run_startup_tasks
from bago.chat.repl import build_prompt_session, run_repl

BAGO_API_PORT = env_port("BAGO_API_PORT", "BAGO_PORT", default=DEFAULT_BAGO_API_PORT)


def main():
        p = argparse.ArgumentParser(description="BAGO Orchestrator HUB")
        p.add_argument("--provider", default="")
        p.add_argument("--model",    default="")
        p.add_argument("--task",     default="")
        p.add_argument("--api",      action="store_true", help="Arrancar con modo API activado")
        args = p.parse_args()

        # Detectar y arrancar API si --api
        if args.api:
            import subprocess, time
            from bago.api.bridge import set_mode
            proc = subprocess.Popen(
                [sys.executable, "-m", "bago.api.server"],
                cwd=str(Path(__file__).resolve().parent),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            print(f"  BAGO API arrancado (PID {proc.pid}, puerto {BAGO_API_PORT})")
            print(f"  Endpoints: http://127.0.0.1:{BAGO_API_PORT}/docs")
            time.sleep(2)
            set_mode("api")

        session = resolve_session(args)
        run_startup_tasks(session)
        pt = build_prompt_session(session)
        run_repl(session, pt)

if __name__ == "__main__":
    main()
