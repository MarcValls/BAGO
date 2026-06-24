"""dump_full_boot.py — full boot sequence."""
import os, sys, io

os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")
sys.path.insert(0, r"bago_core")

for k in list(sys.modules.keys()):
    if k in ("repl", "repl_banner", "repl_status", "repl_navigation",
             "renderer", "version", "commands", "session_manager",
             "switch_engine", "session_provider", "state_paths",
             "system_prompt", "intent_engine", "intent_examples"):
        del sys.modules[k]

from repl import BagoREPL
import session_manager as sm_mod
import switch_engine as se_mod

repl = BagoREPL(
    provider="ollama-local",
    model="llama3.2:3b",
    system_prompt="",
    base_path=os.getcwd(),
)

out = io.StringIO()
sys.stdout = out
sys.stderr = out
try:
    repl._print_banner()
    repl._print_status()
    repl._print_init_warnings()
finally:
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

print("=" * 70)
print("FULL BOOT OUTPUT (banner + status + init_warnings)")
print("=" * 70)
result = out.getvalue()
print(result)
print("=" * 70)
print(f"len = {len(result)} chars")

# Check for the old header text
if "BAGO v" in result and "|" in result:
    print("FOUND old header style (BAGO vX | provider: ...)")
if "provider:" in result:
    print("FOUND 'provider:' string")
