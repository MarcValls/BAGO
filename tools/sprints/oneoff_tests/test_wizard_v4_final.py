"""test_wizard_v4_final.py — definitive test of project_wizard v4."""
import os, sys, io

# Setup paths
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat")
sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core")

import repl_wizard_project_v2 as wizard

class FakeRepl:
    base_path = r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"
    mgr = None


def run_wizard_test(stdin_data: str, label: str):
    """Simulate full wizard run with given stdin."""
    real_stdin = sys.stdin
    real_stdout = sys.stdout
    sys.stdin = io.StringIO(stdin_data)
    sys.stdout = io.StringIO()
    sys.stdin.isatty = lambda: True
    sys.stdout.isatty = lambda: True
    try:
        wizard.project_wizard(FakeRepl())
        output = sys.stdout.getvalue()
    finally:
        sys.stdin = real_stdin
        sys.stdout = real_stdout
    print(f"--- {label} ---")
    print(f"stdin: {stdin_data!r}")
    print(f"output length: {len(output)} chars")
    print(f"output first 400 chars: {output[:400]!r}")
    print(f"output contains '¿Qué quieres hacer?': {'¿Qué quieres hacer?' in output}")
    print(f"output contains 'Proyecto activo:': {'Proyecto activo:' in output}")
    print()


print("=== Test 1: User presses just Enter ===")
run_wizard_test("\n", "Enter default")

print("=== Test 2: User types '2' + Enter ===")
run_wizard_test("2\n", "Pick option 2")

print("=== Test 3: User types 'q' to cancel ===")
run_wizard_test("q\n", "Cancel")
