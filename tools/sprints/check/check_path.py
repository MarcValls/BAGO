"""check_path.py — what sys.path is when repl_chat is imported?"""
import sys, os
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")

print("sys.path:")
for p in sys.path:
    print(f"  {p}")

# Force fresh imports
for k in list(sys.modules.keys()):
    if "repl" in k or "session_provider" in k:
        del sys.modules[k]

# Now trigger the actual import path that repl.run() uses
import repl
print(f"\nrepl module file: {repl.__file__}")
print(f"repl._handle_chat wrapped: {repl.BagoREPL._handle_chat}")

# Trigger the import chain
from repl_chat import handle_chat
print(f"\nhandle_chat file: {handle_chat.__module__}")
import sys as _sys
chat_mod = _sys.modules[handle_chat.__module__]
print(f"chat module file: {chat_mod.__file__}")
