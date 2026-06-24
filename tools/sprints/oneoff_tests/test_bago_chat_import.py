"""test_bago_chat_import.py — verify the import chain for bago chat REPL."""
import os, sys, traceback

os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")
sys.path.insert(0, r"bago_core")

# Load the same modules bago chat would load
try:
    print("importing repl...")
    from repl import BagoREPL
    print(f"  BagoREPL: {BagoREPL}")
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("importing cmd_chat...")
    from bago_core.commands.cmd_chat import cmd_chat
    print(f"  cmd_chat: {cmd_chat}")
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)

# Try to instantiate BagoREPL like cmd_chat would
print("instantiating BagoREPL...")
try:
    repl = BagoREPL(
        provider="ollama-local",
        model="llama3.2:3b",
        system_prompt="",
        base_path=os.getcwd(),
        active_bridges=None,
    )
    print(f"  repl created: {repl.__class__.__name__}")
    print(f"  has _layout: {hasattr(repl, '_layout')}")
except Exception as e:
    print(f"FAIL: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\nOK - all imports work, BagoREPL can be instantiated")
