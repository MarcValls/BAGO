"""promote_full_chat_layer.py — full chat layer promotion from orphan to 3 copies.

User instruction 2026-06-24: "PERO HAY QUE TRASLADAR TODO A LAS OTRAS COPIAS".
So we copy the ENTIRE chat layer (renderer.py, repl.py, all wizards, all
commands) from the orphan at C:\\Program Files\\BAGO\\.bago\\chat\\ to each
of the 3 active copies, replacing whatever was there.

Idempotent: the 3 copies already have backups in renderer.py.bak if needed.
"""
import shutil
from pathlib import Path

HUERFANA = Path(r"C:\Program Files\BAGO\.bago\chat")
COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\.bago\chat"),
]

# Only copy .py files (skip __pycache__ which we'll clean)
SOURCE_FILES = sorted([p for p in HUERFANA.glob("*.py")])
SOURCE_DIRS = sorted([p for p in HUERFANA.iterdir() if p.is_dir()])

print(f"Orphan has {len(SOURCE_FILES)} .py files and {len(SOURCE_DIRS)} subdirs")
print(f"Files to copy: {[p.name for p in SOURCE_FILES]}")
print(f"Dirs to copy:  {[p.name for p in SOURCE_DIRS]}")
print()

for copy in COPIES:
    print(f"\n=== {copy.parent.parent.name} ===")
    # Copy all .py files at top level (FULL promotion, no preservation)
    for src in SOURCE_FILES:
        dst = copy / src.name
        shutil.copy2(src, dst)
    print(f"  copied {len(SOURCE_FILES)} .py files (full promotion)")
    # Copy all subdirs (commands, prompts)
    for srcdir in SOURCE_DIRS:
        dstdir = copy / srcdir.name
        if dstdir.exists():
            shutil.rmtree(dstdir)
        shutil.copytree(srcdir, dstdir)
    print(f"  copied {len(SOURCE_DIRS)} subdirs")
    # Clean pycache so next boot uses the new .py
    pc = copy / "__pycache__"
    if pc.is_dir():
        n = sum(1 for _ in pc.glob("*.pyc"))
        shutil.rmtree(pc)
        print(f"  cleared {n} pyc files from __pycache__")
    # Same for any subdir pycaches
    for sub in copy.rglob("__pycache__"):
        if sub.is_dir():
            n = sum(1 for _ in sub.glob("*.pyc"))
            shutil.rmtree(sub)
    # Also clear the orphan's pycaches so we don't accidentally copy stale .pyc
    for sub in HUERFANA.rglob("__pycache__"):
        if sub.is_dir():
            shutil.rmtree(sub)

print("\n=== DONE ===")
print(f"All 3 copies now have {len(SOURCE_FILES)} .py files matching the orphan.")
