"""audit_commands.py — test what /status and /help show the user."""
import sys, os
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")
for k in list(sys.modules.keys()):
    if k in ("renderer", "version", "commands"):
        del sys.modules[k]

import renderer as R
import commands

print("=" * 70)
print("/help output")
print("=" * 70)
# Try common help function names
for fname in ("help_text", "show_help", "cmd_help", "print_help", "help"):
    if hasattr(commands, fname):
        f = getattr(commands, fname)
        print(f"--- {fname}() ---")
        try:
            r = f()
            print(r)
        except Exception as e:
            print(f"call failed: {e}")
        break
else:
    print("No help function found by common names")

print()
print("=" * 70)
print("imported help_text() exists:", hasattr(commands, "help_text"))
print("imported cmd_status exists:", hasattr(commands, "cmd_status"))

# Try to call cmd_status with a fake mgr+engine
try:
    from unittest.mock import MagicMock
    mgr = MagicMock()
    engine = MagicMock()
    result = commands.cmd_status(mgr, engine, [])
    print()
    print("=" * 70)
    print("/status output (mocked)")
    print("=" * 70)
    print(result)
except Exception as e:
    print(f"cmd_status failed: {type(e).__name__}: {e}")
