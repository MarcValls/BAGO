"""test_handle_chat.py — call _handle_chat directly and dump everything."""
import sys, os, traceback
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")
os.environ["BAGO_NO_SPLIT_SCREEN"] = "1"
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")

for k in list(sys.modules.keys()):
    if k in ("repl", "repl_banner", "repl_chat", "repl_status",
             "repl_hook_on_boot", "repl_layout", "renderer", "version",
             "session_manager", "switch_engine", "session_provider",
             "state_paths"):
        del sys.modules[k]

from repl import BagoREPL
repl = BagoREPL(
    provider="ollama-local",
    model="llama3.2:3b",
    system_prompt="",
    base_path=os.getcwd(),
)

repl._print_banner()
repl._print_status()
repl._print_chat_prompt()
print("=== CALLING handle_chat('hola') ===", flush=True)
try:
    repl._handle_chat("hola")
    print("=== handle_chat returned OK ===", flush=True)
except Exception as e:
    print(f"=== handle_chat EXCEPTION: {type(e).__name__}: {e} ===", flush=True)
    traceback.print_exc()
print("=== END ===", flush=True)
