"""check_mod.py — verify repl_chat module loaded from disk."""
import sys, os
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")

# Force fresh import
for k in list(sys.modules.keys()):
    if "repl_chat" in k or "session_provider" in k:
        del sys.modules[k]

import repl_chat
print(f"Module file: {repl_chat.__file__}")
import inspect
src = inspect.getsource(repl_chat)
print(f"Length: {len(src)}")
import re
for m in re.finditer(r'resolve_provider_model', src):
    print(f"  match at {m.start()}: ...{src[max(0,m.start()-20):m.end()+20]}...")
