"""promote_huerfana_to_3copias.py — copy selectivos from orphan to 3 active copies.

The orphan at C:\\Program Files\\BAGO\\.bago\\chat\\ has the Qwen-skin
4.8.0 era improvements:
  - renderer_box.py  : _qwen_box, the multi-line-aware framed box
  - renderer_text.py : _visible_width, _wrap_line
  - repl_layout.py   : SplitLayout (persistent top header + bottom prompt)
  - repl_banner.py   : print_banner(repl) — entrypoint used by repl.py:82
  - session_provider.py : resolve_provider_model (canonical provider/model)
  - session_context.py  : boot context loader

The 3 active copies (work, dev, launch) only have the legacy 4.6.2
chat layer. Copy the 6 files above to each, and rewrite their
banner() in renderer.py to use _qwen_box.
"""
import shutil
from pathlib import Path

HUERFANA = Path(r"C:\Program Files\BAGO\.bago\chat")
COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\.bago\chat"),
]

FILES = [
    "renderer_box.py",
    "renderer_text.py",
    "repl_layout.py",
    "repl_banner.py",
    "session_provider.py",
    "session_context.py",
]

for copy in COPIES:
    print(f"\n=== {copy.parent.parent.name} ===")
    for f in FILES:
        src = HUERFANA / f
        dst = copy / f
        if not src.is_file():
            print(f"  SKIP {f} (not in orphan)")
            continue
        # Also copy __pycache__ so the imports work
        shutil.copy2(src, dst)
        print(f"  COPIED {f}")
    # Clean pycache for the chat layer
    pc = copy / "__pycache__"
    if pc.is_dir():
        n = 0
        for p in pc.glob("*.pyc"):
            p.unlink()
            n += 1
        print(f"  cleared {n} pyc files")
