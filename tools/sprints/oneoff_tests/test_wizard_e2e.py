"""test_wizard_e2e.py — run the actual bago REPL with simulated input.

This test runs bago chat the same way you would, but feeds stdin via
a pipe with newline-terminated text, and captures stdout to verify
the wizard printed and the chosen option was selected.
"""
import subprocess, sys

PYTHON = r"C:\Python314\python.exe"
BAGO_LAUNCHER = r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago.ps1"

# The flow: we send '2\n' to pick option 2 (analyze), then 'q\n' to quit the REPL
test_input = b"2\nq\n"

print("=== Running: bago chat --no-monitor with stdin='2\\nq\\n' ===")
result = subprocess.run(
    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
     f"& '{BAGO_LAUNCHER}' chat --no-monitor"],
    input=test_input,
    capture_output=True,
    timeout=30,
)

print(f"\nreturn code: {result.returncode}")
print(f"stdout len: {len(result.stdout)} bytes")
print(f"stderr len: {len(result.stderr)} bytes")

# Look for the menu in stdout (encoded as UTF-16 in PowerShell)
try:
    stdout_text = result.stdout.decode("utf-16-le")
except UnicodeDecodeError:
    stdout_text = result.stdout.decode("utf-8", errors="replace")

# Also try stderr
try:
    stderr_text = result.stderr.decode("utf-16-le")
except UnicodeDecodeError:
    stderr_text = result.stderr.decode("utf-8", errors="replace")

# Check what the wizard produced
print()
print("=== Checking stdout for wizard output ===")
checks = [
    ("'Que quieres hacer?' in output", "Que quieres hacer?" in stdout_text),
    ("'Proyecto activo:' in output", "Proyecto activo:" in stdout_text),
    ("'Analizar este directorio' in output", "Analizar este directorio" in stdout_text),
    ("'Opcion 2 seleccionada' in output", "Opcion 2 seleccionada" in stdout_text),
    ("'Bienvenido a BAGO' in output", "Bienvenido a BAGO" in stdout_text),
    ("'👋 Bienvenido' in output", "👋 Bienvenido" in stdout_text),
]
for label, ok in checks:
    print(f"  [{'OK' if ok else 'NO '}] {label}")

print()
print("=== Output preview (last 1500 chars) ===")
print(stdout_text[-1500:])
