"""patch_banner_estetica.py — solo reemplaza el body de banner() en las 3 copias.

El script anterior detecto "already patched" pero dejo la version rota
de banner() (la que usa box() y rompe con multi-linea). Este nuevo
script solo cambia el body dentro del try/except, dejando intacto el
resto.
"""
import re
from pathlib import Path

COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch"),
]

# New banner body — sin caja box(), solo bloques centrados + version
NEW_BANNER_TRY = '''    try:
        import shutil as _sh
        accent = Color.BRIGHT_CYAN
        dim = Color.DIM
        cols = _sh.get_terminal_size((100, 20)).columns

        # Logo: 5 lineas de bloques B-A-G-O. Cada linea mide 25 chars visibles.
        logo_lines = bago_logo_text().splitlines()

        # Version line: "v4.7.0  --  Session-First AI Chat"
        version_str = "v" + str(_BAGO_VERSION) + " " + chr(0x2014) + " Session-First AI Chat"

        # Centrar cada linea al ancho del terminal.
        out = []
        for line in logo_lines:
            pad = max(0, (cols - len(line)) // 2)
            out.append(colorize(" " * pad + line, accent))

        # Separador vacio
        out.append("")

        # Version centrada, en dim
        vpad = max(0, (cols - len(version_str)) // 2)
        out.append(colorize(" " * vpad + version_str, dim))

        return chr(10).join(out)
    except Exception as exc:'''

# Pattern to match the old banner body inside try/except
OLD_PATTERN = re.compile(
    r"    try:.*?    except Exception as exc:",
    re.DOTALL,
)

for root in COPIES:
    rp = root / ".bago" / "chat" / "renderer.py"
    src = rp.read_text(encoding="utf-8")

    if "Centrar cada linea al ancho" in src:
        print(f"  {root}: already estetica-patched, skip")
        continue

    new_src, n = OLD_PATTERN.subn(NEW_BANNER_TRY, src, count=1)
    if n == 0:
        print(f"  {root}: FAILED — could not find old banner body")
        continue

    rp.write_text(new_src, encoding="utf-8")
    print(f"  {root}: patched (estetica)")

    # Clean pycache
    pc = rp.parent / "__pycache__"
    if pc.is_dir():
        for p in pc.glob("renderer*.pyc"):
            p.unlink()
            print(f"    removed {p.name}")
