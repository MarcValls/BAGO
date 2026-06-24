"""dump_boot.py — capture full REPL boot output (banner, welcome, status,
prompt) by calling print_banner directly with the actual session state.
"""
import os, sys, io
from unittest.mock import MagicMock

os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")
sys.path.insert(0, r"bago_core")

# Clear cached modules
for k in list(sys.modules.keys()):
    if k in ("repl", "repl_banner", "renderer", "version", "commands",
             "session_manager", "switch_engine", "session_provider",
             "state_paths"):
        del sys.modules[k]

import renderer as R
from repl import BagoREPL
import session_manager as sm_mod
import switch_engine as se_mod
import session_provider as sp_mod

print("=" * 70, flush=True)
print("DUMP: ACTIVE BOOT PATH", flush=True)
print("=" * 70, flush=True)

# Build a realistic REPL like cmd_chat does
mgr = sm_mod.SessionManager(
    provider="ollama-local",
    model="llama3.2:3b",
    base_path=os.getcwd(),
)
engine = se_mod.SwitchEngine(mgr.adapters)

repl = BagoREPL(
    provider="ollama-local",
    model="llama3.2:3b",
    system_prompt="",
    base_path=os.getcwd(),
    active_bridges=None,
)
print(f"repl._layout = {getattr(repl, '_layout', '<missing>')}")
print(f"repl._BAGO_VERSION = {R._BAGO_VERSION}")
print(f"repl.base_path = {repl.base_path}")
print(f"repl.mgr.provider = {repl.mgr.provider}")
print(f"repl.mgr.model = {repl.mgr.model}")
print()

# Call print_banner and capture
out = io.StringIO()
sys.stdout = out
try:
    from repl_banner import print_banner
    print_banner(repl)
finally:
    sys.stdout = sys.__stdout__

print("=" * 70)
print("OUTPUT FROM print_banner(repl):")
print("=" * 70)
print(out.getvalue())
