"""test_wizard.py — verifies project_wizard works with realistic stdin.

We test:
  1. Empty stdin → returns default (option 0).
  2. "1\\n" → returns option 0 (analyze).
  3. "q" → returns None (cancel).
  4. "5\\n" → returns option 4 (change dir).

Uses sys.stdin replacement so we don't need an actual TTY.
"""
import sys, io
from pathlib import Path

# Force-import the wizard module
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")

# Create a fake repl object that doesn't need a real session
class FakeRepl:
    base_path = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
    mgr = None  # No session manager

from repl_wizard_project_v2 import _wizard_tty_ok, _ask_choice, project_wizard


def test(name, stdin_data, expected, n_choices):
    """Run _ask_choice with given stdin and check the result."""
    saved_stdin = sys.stdin
    saved_stdout = sys.stdout
    sys.stdin = io.StringIO(stdin_data)
    sys.stdout = io.StringIO()
    try:
        result = _ask_choice("→ ", n_choices)
    finally:
        sys.stdin = saved_stdin
        sys.stdout = saved_stdout
    status = "OK" if result == expected else "FAIL"
    print(f"  {status}  {name!r:30} → {result!r:6} (expected {expected!r})")
    return result == expected


print("Testing _ask_choice():")
n = 5
ok = True
ok &= test("Enter only (empty)", "\n", 0, n)
ok &= test("Enter only (\\r\\n)", "\r\n", 0, n)
ok &= test("Number 1", "1\n", 0, n)         # 1-1 = 0
ok &= test("Number 2", "2\n", 1, n)         # 2-1 = 1
ok &= test("Number 5", "5\n", 4, n)         # 5-1 = 4
ok &= test("Number 9 (out of range)", "9\n", None, n)
ok &= test("Letter q (cancel)", "q\n", None, n)
ok &= test("Letter Q (cancel)", "Q\n", None, n)
ok &= test("Letter a (invalid)", "a\n", None, n)
ok &= test("Empty string", "", None, n)

print()
print("Result:", "ALL PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
