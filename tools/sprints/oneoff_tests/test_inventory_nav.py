"""test_inventory_nav.py — test the inventory browser without TTY."""
import sys, io
from pathlib import Path

sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\tools")

# Fake repl with _navigate that simulates user picking options in order
class FakeRepl:
    base_path = r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"
    call_count = 0
    def _navigate(self, title, labels, hint=None):
        # Simulate: first call pick "tools" (first group), then pick item 0,
        # then pick action 2 (JSON dump).
        FakeRepl.call_count += 1
        print(f"[FAKE NAV #{FakeRepl.call_count}] title={title!r}")
        print(f"[FAKE NAV #{FakeRepl.call_count}] labels ({len(labels)}): {labels[:3]}{'...' if len(labels)>3 else ''}")
        if FakeRepl.call_count == 1:
            return 0   # first group
        elif FakeRepl.call_count == 2:
            return 0   # first item
        elif FakeRepl.call_count == 3:
            return 2   # JSON dump action
        else:
            return 4  # cancel

# Patch stdin's read(1) to return newline so the "Press Enter to continue" works
sys.stdin = io.StringIO("\n\n\n\n")
sys.stdin.isatty = lambda: True
sys.stdout.isatty = lambda: True
sys.stdout = io.StringIO()
sys.stdin.isatty = lambda: True
sys.stdout.isatty = lambda: True

import repl_inventory_nav as browser
print("[CALLING browser.inventory_browser(FakeRepl())]")
browser.inventory_browser(FakeRepl())

out = sys.stdout.getvalue()
sys.stdout = sys.__stdout__
print("=== browser output ===")
print(out)
