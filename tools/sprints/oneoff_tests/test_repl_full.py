"""test_repl_full.py — simulate full REPL run with print_message trace."""
import sys, os
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")

# Force fresh imports
for k in list(sys.modules.keys()):
    if k in ("repl", "repl_chat", "repl_banner", "repl_status",
             "repl_hook_on_boot", "repl_layout", "renderer", "version",
             "session_manager", "switch_engine", "session_provider",
             "state_paths", "commands"):
        del sys.modules[k]

import renderer as R

# Monkey-patch print_message_qwen to print to stderr too
orig_pmq = R.print_message_qwen
def traced_print_message_qwen(role, content, state="static", provider="", model=""):
    sys.stderr.write(f"[TRACE print_message_qwen] role={role!r} content={content!r} state={state!r}\n")
    sys.stderr.flush()
    return orig_pmq(role, content, state=state, provider=provider, model=model)
R.print_message_qwen = traced_print_message_qwen
print("Monkey-patch applied", flush=True)

from repl import BagoREPL
repl = BagoREPL(provider="ollama-local", model="llama3.2:3b", system_prompt="", base_path=os.getcwd())

# Manually simulate the user echo + handle_chat
sys.stderr.write("[SIM] printing user message via print_message_qwen\n")
sys.stderr.flush()
traced_print_message_qwen("user", "HOLA", state="sent")
sys.stderr.write("[SIM] calling handle_chat\n")
sys.stderr.flush()
repl._handle_chat("HOLA")
sys.stderr.write("[SIM] handle_chat returned\n")
sys.stderr.flush()
