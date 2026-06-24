"""check_handle.py — verify handle_chat sees the right function."""
import sys, os, inspect
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")

# Force fresh imports
for k in list(sys.modules.keys()):
    if "repl" in k or "session_provider" in k or "session_manager" in k:
        del sys.modules[k]

from repl_chat import handle_chat
print(f"handle_chat from: {handle_chat.__module__}")
print(f"handle_chat file: {sys.modules[handle_chat.__module__].__file__}")

src = inspect.getsource(handle_chat)
print(f"\nsource length: {len(src)}")
print("\nlines containing 'resolve_provider_model':")
for i, line in enumerate(src.split("\n"), 1):
    if "resolve_provider_model" in line:
        print(f"  L{i}: {line}")

print("\nLooking for '_resolve_provider_model':")
for i, line in enumerate(src.split("\n"), 1):
    if "_resolve_provider_model" in line:
        print(f"  L{i}: {line}")
print("(none found if empty above)")
