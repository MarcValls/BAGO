
from bago_utils import load_json, save_json, timestamp_iso

#!/usr/bin/env python3
"""BAGO Orchestrator HUB — Entry point (thin glue)"""
import argparse
import os
import sys
from pathlib import Path

from bago.ollama_runtime import DEFAULT_BAGO_API_PORT, env_port
from bago.ollama_models import ensure_ollama_models_env

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

sys.path.insert(0, str(Path(__file__).parent))

from bago.chat.boot import resolve_session, run_startup_tasks
from bago.chat.repl import build_prompt_session, run_repl
from bago.menus.config import _load_config

BAGO_API_PORT = env_port("BAGO_API_PORT", "BAGO_PORT", default=DEFAULT_BAGO_API_PORT)
ensure_ollama_models_env()


def main():
        p = argparse.ArgumentParser(description="BAGO Orchestrator HUB")
        p.add_argument("--provider", default="")
        p.add_argument("--model",    default="")
        p.add_argument("--task",     default="")
        p.add_argument("--local",    action="store_true", help="Fuerza modelo local (ollama-local)")
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

        # Cargar configuracion persistente antes de resolver sesion
        cfg = _load_config()
        if args.local and not args.provider and not args.model:
            args.provider = "local"
        args.single_model = cfg.get("single_model", False)
        session = resolve_session(args)
        # Aplicar configuracion guardada a la sesion
        session.autoroute = cfg.get("autoroute", True)
        session.single_model = cfg.get("single_model", False)
        session.autonomous = cfg.get("autonomous", False)
        session.auto_confirm = cfg.get("auto_confirm", "adaptativo")
        session.auto_max_iter = cfg.get("auto_max_iter", 10)
        session.orch_mode = cfg.get("orch_mode", "standard")
        session.sync_after = cfg.get("sync_after", "continuar")
        session.temp_mode = cfg.get("temp_mode", False)
        run_startup_tasks(session)
        pt = build_prompt_session(session)
        run_repl(session, pt)

if __name__ == "__main__":
    main()
