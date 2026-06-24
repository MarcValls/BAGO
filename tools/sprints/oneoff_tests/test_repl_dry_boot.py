"""test_repl_dry_boot.py — simulate REPL boot without calling Ollama.

This instantiates BagoREPL, triggers _print_banner, and exits — to verify
the boot visual chain end-to-end. We monkey-patch SessionManager/SwitchEngine
to avoid actual provider calls.
"""
import os, sys, io
from unittest.mock import MagicMock

os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")

# Mock the core dependencies BEFORE importing repl
# (repl.py imports session_manager and switch_engine at module load)
sys.modules["session_manager"] = MagicMock()
sys.modules["switch_engine"] = MagicMock()

for k in list(sys.modules.keys()):
    if k in ("renderer", "version", "commands", "intent_engine", "system_prompt", "repl"):
        del sys.modules[k]

import repl as REPL_MOD

# Mock the SessionManager methods that boot needs
fake_session = MagicMock()
fake_session.status.return_value = {
    "provider": "ollama-local",
    "model": "llama3.2:3b",
    "total_tokens": 0,
    "health": {"ok": True, "detail": "ollama-local ok"},
    "session_id": "test",
    "modo_bago": "free",
    "agente": "default",
    "bridges": [],
    "messages": 0,
    "calls": 0,
    "switches": 0,
}

# Find the BagoREPL class
repl_cls = getattr(REPL_MOD, "BagoREPL", None)
if repl_cls is None:
    # search for the class
    for name in dir(REPL_MOD):
        obj = getattr(REPL_MOD, name)
        if isinstance(obj, type) and "REPL" in name:
            repl_cls = obj
            break
print(f"Found REPL class: {repl_cls.__name__ if repl_cls else None}")

if repl_cls:
    repl = repl_cls.__new__(repl_cls)
    repl.mgr = fake_session
    # Boot just the banner
    out = io.StringIO()
    sys.stdout = out
    try:
        repl._print_banner()
        repl._print_status()
        sys.stdout.write(repl.__class__.__name__ + " rendered boot OK\n")
    except Exception as e:
        import traceback
        sys.stdout.write(f"FAILED: {type(e).__name__}: {e}\n")
        traceback.print_exc(file=sys.stdout)
    finally:
        sys.stdout = sys.__stdout__
    print("=" * 70)
    print("DRY BOOT OUTPUT")
    print("=" * 70)
    print(out.getvalue())
