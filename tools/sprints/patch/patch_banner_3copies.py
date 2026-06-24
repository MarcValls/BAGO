#!/usr/bin/env python3
"""patch_banner_3copies.py — replica el fix del banner a las 3 copias activas.

Para cada copia:
  1. Sustituye `def banner()` en .bago/chat/renderer.py por la versión
     con bloques B-A-G-O (single source of truth en bago_logo_text).
  2. Añade `bago_logo_text()` si no existe.
  3. Añade `_resolve_bago_version()` y la asignación de `_BAGO_VERSION`
     si no existen (o las reescribe para no hardcodear fallback).
  4. Alinea release_version.txt → 4.7.0 si está por debajo.
  5. Borra .bago/chat/__pycache__/*.pyc para que la próxima ejecución
     use el .py fresco.

Idempotente: si una copia ya está parcheada, la deja igual.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch"),
]
TARGET_VERSION = "4.7.0"

# ─── Snippets que se inyectan en renderer.py ──────────────────────────────

# Just the logo + banner replacement. The renderer already loads
# `_BAGO_VERSION` from `core/version.py` via the existing
# `from version import CURRENT as _BAGO_VERSION` at module top, so we
# don't need to redefine version resolution.

LOGO_AND_BANNER_BLOCK = r'''
# ─── BAGO logo (single source of truth for the B-A-G-O block letters) ───
def bago_logo_text() -> str:
    """B-A-G-O block letters as plain text. 5 rows, equal widths per row."""
    B = [
        "█████",
        "█   █",
        "█████",
        "█   █",
        "█████",
    ]
    A = [
        " ███ ",
        "█   █",
        "█████",
        "█   █",
        "█   █",
    ]
    G = [
        " ████",
        "█    ",
        "█ ███",
        "█   █",
        " ████",
    ]
    O = [
        " ███ ",
        "█   █",
        "█   █",
        "█   █",
        " ███ ",
    ]
    return chr(10).join(" ".join([B[r], A[r], G[r], O[r]]) for r in range(5))


def banner() -> str:
    """Banner de inicio. Bloques B-A-G-O centrados + version + tagline.

    No usamos caja box() porque los bloques ya tienen su propia forma y
    el resultado quedaba con lineas del logo que se salian del marco
    (user feedback 2026-06-24: "NO POR LA VERSION, POR LA ESTETICA").

    Never raises: si algo falla, devuelve un mini-bloque visible con
    el error para que el REPL nunca arranque con prompt silencioso.
    """
    import traceback as _tb
    try:
        import shutil as _sh
        accent = Color.BRIGHT_CYAN
        dim = Color.DIM
        cols = _sh.get_terminal_size((100, 20)).columns

        # Logo: 5 lineas de bloques B-A-G-O. Cada linea mide 25 chars visibles.
        logo_lines = bago_logo_text().splitlines()
        logo_w = max(len(line) for line in logo_lines)  # 25

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
    except Exception as exc:
        return (
            chr(0x250c) + chr(0x2500) + " BAGO (banner error) " + chr(0x2500) + chr(0x2510) + chr(10)
            + "| " + str(_BAGO_VERSION) + " " + chr(0x2014) + " " + type(exc).__name__ + ": " + str(exc) + " |" + chr(10)
            + chr(0x2514) + chr(0x2500)*23 + chr(0x2518) + chr(10)
            + "  " + _tb.format_exc()
        )


'''


OLD_BANNER_RE = re.compile(
    r"def banner\(\) -> str:.*?(?=\ndef |\nclass |\Z)",
    re.DOTALL,
)


def patch_renderer(renderer_path: Path) -> str:
    """Patch .bago/chat/renderer.py to add helpers + replace banner().

    Returns a short status string for logging.
    """
    src = renderer_path.read_text(encoding="utf-8")

    already_patched = "BAGO logo (single source of truth" in src
    if already_patched:
        return "skip (already patched)"

    # Replace the OLD banner() implementation (ASCII art B-A-G-O with
    # mismatched widths) with the new safe wrapper that uses
    # bago_logo_text() as the single source of truth.
    new_src, n = OLD_BANNER_RE.subn(
        LOGO_AND_BANNER_BLOCK + "# (end of patched block)\n\n",
        src,
        count=1,
    )
    if n == 0:
        # Couldn't match — append the new block at end of file.
        new_src = src.rstrip() + "\n\n" + LOGO_AND_BANNER_BLOCK

    renderer_path.write_text(new_src, encoding="utf-8")
    return "patched"


def align_release_version(root: Path) -> str:
    """Set release_version.txt AND versions.json:current to TARGET_VERSION."""
    out = []
    rv = root / "release_version.txt"
    if rv.is_file():
        cur = rv.read_text(encoding="utf-8").strip()
        if cur != TARGET_VERSION:
            rv.write_text(TARGET_VERSION + "\n", encoding="utf-8")
            out.append(f"release_version.txt {cur} -> {TARGET_VERSION}")
        else:
            out.append(f"release_version.txt already {TARGET_VERSION}")

    vj = root / "versions.json"
    if vj.is_file():
        import json as _json
        data = _json.loads(vj.read_text(encoding="utf-8"))
        cur = data.get("current", "")
        if cur != TARGET_VERSION:
            data["current"] = TARGET_VERSION
            vj.write_text(_json.dumps(data, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")
            out.append(f"versions.json current {cur} -> {TARGET_VERSION}")
        else:
            out.append(f"versions.json current already {TARGET_VERSION}")

    return ", ".join(out) if out else "no version files"


def clear_pycache(root: Path) -> str:
    pc = root / ".bago" / "chat" / "__pycache__"
    if not pc.is_dir():
        return "no pycache"
    n = 0
    for p in pc.glob("*.pyc"):
        try:
            p.unlink()
            n += 1
        except OSError:
            pass
    return f"removed {n} .pyc"


def main() -> int:
    ok = True
    for root in COPIES:
        rp = root / ".bago" / "chat" / "renderer.py"
        print(f"\n=== {root} ===")
        if not rp.is_file():
            print(f"  renderer.py NOT FOUND at {rp}")
            ok = False
            continue
        try:
            status = patch_renderer(rp)
            print(f"  renderer.py: {status}")
        except Exception as e:
            print(f"  renderer.py: FAILED -> {e}")
            ok = False
        print(f"  release_version.txt: {align_release_version(root)}")
        print(f"  pycache: {clear_pycache(root)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
