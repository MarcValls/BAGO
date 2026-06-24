"""test_wizard_realistic.py — print what the wizard does for real TTY.

This test mimics exactly what happens when BagoREPL._print_banner runs
and calls project_wizard(self).
"""
import os, sys
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")

# Force a TTY simulation
import io
real_stdin = sys.stdin
real_stdout = sys.stdout

class FakeTTY(io.StringIO):
    """A stdout that pretends to be a TTY."""
    def isatty(self):
        return True

class FakeStdinTTY(io.StringIO):
    """A stdin that pretends to be a TTY."""
    def isatty(self):
        return True

print("=== Test: simulate real TTY with user pressing Enter ===")
sys.stdin = FakeStdinTTY("\n")  # user just presses Enter
sys.stdout = FakeTTY()

# Now call the wizard directly
import repl_wizard_project_v2 as wizard

class FakeRepl:
    base_path = r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"
    mgr = None

repl = FakeRepl()
print("[output starts below]", file=real_stdout)
wizard.project_wizard(repl)
sys.stdout.flush()
print("[output ends above]", file=real_stdout)

# Get the output
sys.stdout = real_stdout
print()
print("Captured output from wizard:")
print("(see above)")
