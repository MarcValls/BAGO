"""test_wizard_v6.py — verify project_wizard v6 uses BagoREPL._navigate."""
import sys, io
from pathlib import Path

sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")

# Build a minimal BagoREPL mock that has _navigate
class FakeRepl:
    base_path = r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"
    mgr = None

    def _navigate(self, title, labels, hint=None):
        # Simulate user pressing Enter (selects first option = 0)
        print(f"[MOCK] _navigate called with title={title!r}")
        print(f"[MOCK] labels={labels}")
        return 0

repl = FakeRepl()

# Test 1: Wizard with default selection (Enter)
import repl_wizard_project_v6 as wizard

# Force TTY simulation
sys.stdin = io.StringIO("")
sys.stdout = io.StringIO()
sys.stdin.isatty = lambda: True
sys.stdout.isatty = lambda: True

print("=== Test: _navigate returns 0 (default) ===")
result = wizard.project_wizard(repl)
out = sys.stdout.getvalue()
print(f"returned: {result}")
print(f"output preview: {out[:200]!r}")
print(f"calls repl._navigate: {'MOCK' in out}")
print()

# Test 2: _navigate returns 2 (view status)
class FakeRepl2(FakeRepl):
    def _navigate(self, title, labels, hint=None):
        return 2

# Need to monkey-patch project_memory to not crash
import sys as _sys
_sys.modules["project_memory"] = type(_sys)("project_memory")
_sys.modules["project_memory"].status_data = lambda x: {"status": "ok"}
_sys.modules["project_memory"].format_status = lambda x: "Status: ok"

sys.stdin = io.StringIO("")
sys.stdout = io.StringIO()
sys.stdin.isatty = lambda: True
sys.stdout.isatty = lambda: True

print("=== Test: _navigate returns 2 (status) ===")
result = wizard.project_wizard(FakeRepl2())
out = sys.stdout.getvalue()
print(f"output: {out[:300]!r}")
print(f"contains 'Status: ok': {'Status: ok' in out}")

# Test 3: _navigate returns None (cancel)
class FakeRepl3(FakeRepl):
    def _navigate(self, title, labels, hint=None):
        return None

sys.stdin = io.StringIO("")
sys.stdout = io.StringIO()
sys.stdin.isatty = lambda: True
sys.stdout.isatty = lambda: True

print()
print("=== Test: _navigate returns None (cancel) ===")
result = wizard.project_wizard(FakeRepl3())
out = sys.stdout.getvalue()
print(f"output preview: {out[:200]!r}")
