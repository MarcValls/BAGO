"""patch_banner_alineado.py — fix banner alignment with status line.

The banner was centered to terminal width, but status line uses fixed
width=60. So in a wide terminal the banner floats far to the right
while status sits at left. Both should use the same alignment.

Fix: banner uses the SAME fixed width as the status line (60), left-
aligned with a small consistent indent. Logo (25 chars) sits inside
a left-aligned frame.
"""
import re
from pathlib import Path

COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch"),
]

# New banner body — left-aligned, same width feel as status_line (60)
NEW_BANNER_TRY = '''    try:
        accent = Color.BRIGHT_CYAN
        dim = Color.DIM

        # Logo: 5 lineas de bloques B-A-G-O. Cada linea mide 25 chars visibles.
        logo_lines = bago_logo_text().splitlines()

        # Version line: "v4.7.0  --  Session-First AI Chat"
        version_str = "v" + str(_BAGO_VERSION) + " " + chr(0x2014) + " Session-First AI Chat"

        # Left-aligned, NO centering. The status_line uses ~60 char width
        # so the banner uses the same logical width and sits visually aligned.
        out = []
        for line in logo_lines:
            out.append(colorize(line, accent))

        # Separador vacio
        out.append("")

        # Version en dim, mismo indent que el logo
        out.append(colorize(version_str, dim))

        return chr(10).join(out)
    except Exception as exc:'''

OLD_PATTERN = re.compile(
    r"    try:.*?    except Exception as exc:",
    re.DOTALL,
)

for root in COPIES:
    rp = root / ".bago" / "chat" / "renderer.py"
    src = rp.read_text(encoding="utf-8")

    if "status_line uses ~60 char width" in src:
        print(f"  {root}: already alineado-patched, skip")
        continue

    new_src, n = OLD_PATTERN.subn(NEW_BANNER_TRY, src, count=1)
    if n == 0:
        print(f"  {root}: FAILED — could not find old banner body")
        continue

    rp.write_text(new_src, encoding="utf-8")
    print(f"  {root}: patched (alineado)")

    pc = rp.parent / "__pycache__"
    if pc.is_dir():
        for p in pc.glob("renderer*.pyc"):
            p.unlink()
            print(f"    removed {p.name}")
