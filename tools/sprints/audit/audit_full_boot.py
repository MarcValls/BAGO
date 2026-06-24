"""audit_full_boot.py — captura TODO lo que el usuario ve durante el boot y operación.

Busca problemas de:
  - Alineación (columnas distintas en cajas multi-línea)
  - Hardcoded visual (anchos fijos que no se adaptan al terminal)
  - Caracteres rotos o widths incorrectos
  - Estética inconsistente entre elementos
"""
import os, sys, re
import shutil

ROOT = r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"
os.chdir(ROOT)
sys.path.insert(0, r".bago\chat")
for k in list(sys.modules.keys()):
    if k in ("renderer", "version"):
        del sys.modules[k]

import renderer as R

# Force a reasonable terminal width for testing
cols = shutil.get_terminal_size((100, 20)).columns
print(f"Terminal width: {cols}")
print()

# 1. BANNER (current state)
print("=" * cols)
print("1. BANNER (current — broken box)")
print("=" * cols)
b = R.banner()
print(b)
print()

# 2. STATUS LINE (lo que aparece entre banner y prompt)
print("=" * cols)
print("2. STATUS LINE")
print("=" * cols)
print(R.dim("─" * 60))
print(R.status_line("ollama-local", "llama3.2:3b", 0, True))
print(R.dim("─" * 60))
print()

# 3. PROMPT
print("=" * cols)
print("3. PROMPT")
print("=" * cols)
# Look at what repl.py does for the prompt
import importlib
repl = importlib.import_module("repl")
src_path = r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat\repl.py"
with open(src_path, encoding="utf-8") as f:
    src = f.read()
# Find prompt line
m = re.search(r'print\(R\.accent\("bago"\).*?flush=True\)', src)
if m:
    print(f"   Code: {m.group(0)}")
    print(f"   Visual: {R.accent('bago') + R.bright_black(' ❯ ')}")
print()

# 4. SWITCH NOTIFICATION
print("=" * cols)
print("4. SWITCH NOTIFICATION (success)")
print("=" * cols)
R.print_switch_notification({
    "ok": True,
    "old_provider": "ollama-local", "old_model": "llama3.2:3b",
    "new_provider": "ollama-local", "new_model": "qwen2.5:14b",
    "warnings": [],
})
print()

# 5. AUTO-EVOLUTION MESSAGE
print("=" * cols)
print("5. AUTO-EVOLUTION MESSAGE")
print("=" * cols)
print(R.info("🧬 Autoevolución: aprendiendo de tu historial…"))
print(R.dim("Autoevolución completada — 60 ejemplos (chat:15 · review:15 · execute:15 · work:15)"))
print(R.dim("Política BC entrenada — 925 muestras (fuente: transition_log, loss: 1.024)"))
print()

# 6. Check available colors
print("=" * cols)
print("6. SAMPLE COLORS (visible/working)")
print("=" * cols)
print(f"  accent (cyan):       {R.accent('texto accent')}")
print(f"  bright_white:        {R.bright_black('texto bright_black')}")
print(f"  dim:                 {R.dim('texto dim')}")
print(f"  info (bright blue):  {R.info('texto info')}")
print(f"  ok (bright green):   {R.ok('texto ok')}")
print(f"  warn (bright yellow):{R.warn('texto warn')}")
print(f"  error (bright red):  {R.error('texto error')}")
print()

# 7. Check welcome + divider widths
print("=" * cols)
print("7. WELCOME + DIVIDER")
print("=" * cols)
print(R.dim("─" * 60))
print(R.info(f"Bienvenido a BAGO {R._BAGO_VERSION}. Escribe / para la paleta de comandos o pulsa Enter (Ctrl+M) para el menu."))
print(R.dim("El contexto de sesión sobrevive al cambio de provider."))
print(R.dim("─" * 60))
print()

# 8. Test the box() function with multi-line content
print("=" * cols)
print("8. box() with multi-line (the bug source)")
print("=" * cols)
test_lines = [
    "█████  ███   ████  ███ ",
    "█   █ █   █ █     █   █",
    "█████ █████ █ ███ █   █",
    "█   █ █   █ █   █ █   █",
    "█████ █   █  ████  ███ ",
    "    v4.7.0 — Session-First AI Chat",
]
print(R.box("BAGO", test_lines, width=70))
