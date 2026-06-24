"""test_full_boot.py — Simula el boot completo del REPL en la copia work."""
import os, sys

# Same cwd the launcher uses after resolve: work copy
os.chdir(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
sys.path.insert(0, r".bago\chat")

# Clear cached modules
for k in list(sys.modules.keys()):
    if k.startswith(("repl", "renderer", "version", "commands")):
        del sys.modules[k]

import renderer as R
print("VERSION:", R._BAGO_VERSION)
print()
print("=== BANNER ===")
print(R.banner())
print()
print("=== WELCOME ===")
print(R.info(f"Bienvenido a BAGO {R._BAGO_VERSION}. Escribe / para la paleta de comandos o pulsa Enter (Ctrl+M) para el menu."))
print(R.dim("El contexto de sesión sobrevive al cambio de provider."))
print()
print("=== END ===")
