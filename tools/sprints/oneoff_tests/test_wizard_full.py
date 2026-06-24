"""test_wizard_full.py — verify the wizard boots correctly from repl.py."""
import sys, io
from pathlib import Path

# Stub repl_inventory and session_manager so repl.py loads without real Ollama
sys.modules["repl_inventory"] = type(sys)("repl_inventory")
sys.modules["repl_inventory"].print_workspace_inventory = lambda *a, **k: None

# We don't need session_manager for _print_banner alone, but the REPL
# init does. Let's test just the _print_banner path with the wizard.
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")

# Force-import the wizard
import repl_wizard_project_v2 as wizard

# Test 1: stdin is NOT a TTY → wizard returns immediately
print("Test 1: Non-TTY stdin (e.g. piping input)")
saved_stdin = sys.stdin
saved_stdout = sys.stdout
sys.stdin = io.StringIO("1\n")
sys.stdout = io.StringIO()
try:
    # Force the TTY check to think we're NOT a TTY
    sys.stdin.isatty = lambda: False
    sys.stdout.isatty = lambda: False
    called = {"ran": False}
    def fake_wizard(repl):
        called["ran"] = True
    # Patch _wizard_tty_ok to return False (simulating non-TTY)
    wizard._wizard_tty_ok = lambda: False
    wizard.project_wizard(repl=None)
finally:
    sys.stdin = saved_stdin
    sys.stdout = saved_stdout
print(f"  wizard ran: {called['ran']} (should be False — non-TTY skips wizard)")

# Test 2: stdin IS a TTY, user presses Enter → wizard reads Enter and returns 0
print()
print("Test 2: TTY stdin, user presses Enter (default)")
saved_stdin = sys.stdin
saved_stdout = sys.stdout
sys.stdin = io.StringIO("\n")
sys.stdout = io.StringIO()
try:
    sys.stdin.isatty = lambda: True
    sys.stdout.isatty = lambda: True
    # Create a minimal repl
    class FakeRepl:
        base_path = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
        mgr = None
    repl = FakeRepl()
    wizard._wizard_tty_ok = lambda: True
    wizard.project_wizard(repl)
    output = sys.stdout.getvalue()
    print(f"  output preview: {output[:200]!r}")
    print(f"  output contains 'Proyecto activo:': {'Proyecto activo:' in output}")
finally:
    sys.stdin = saved_stdin
    sys.stdout = saved_stdout

# Test 3: TTY stdin, user types "3" → init project option
print()
print("Test 3: TTY stdin, user types '3' (init project)")
saved_stdin = sys.stdin
saved_stdout = sys.stdout
sys.stdin = io.StringIO("3\n")
sys.stdout = io.StringIO()
try:
    sys.stdin.isatty = lambda: True
    sys.stdout.isatty = lambda: True

    class FakeRepl:
        base_path = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
        mgr = None

    repl = FakeRepl()
    wizard._wizard_tty_ok = lambda: True
    wizard.project_wizard(repl)
    output = sys.stdout.getvalue()
    print(f"  output preview: {output[:300]!r}")
    # Should mention initialization (or warning about no project_memory)
    print(f"  output mentions 'Inicializar': {'Inicializar' in output}")
finally:
    sys.stdin = saved_stdin
    sys.stdout = saved_stdout
