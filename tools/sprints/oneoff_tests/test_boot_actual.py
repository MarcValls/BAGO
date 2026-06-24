"""test_boot_actual.py — verifies the actual boot of the live REPL."""
import sys, os
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")

os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")

for k in list(sys.modules.keys()):
    if k in ("repl", "repl_banner", "repl_status", "repl_hook_on_boot",
             "repl_layout", "renderer", "version", "session_manager",
             "switch_engine", "session_provider", "state_paths"):
        del sys.modules[k]

from repl import BagoREPL

repl = BagoREPL(
    provider="ollama-local",
    model="llama3.2:3b",
    system_prompt="",
    base_path=os.getcwd(),
)

print("--- _print_banner ---")
repl._print_banner()
print("--- _print_status ---")
repl._print_status()
print("--- _print_chat_prompt ---")
repl._print_chat_prompt()
print()
print("=== END ===")
