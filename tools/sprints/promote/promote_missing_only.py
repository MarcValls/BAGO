"""promote_missing_only.py — copy ONLY files from orphan NOT in active copies.

Per user instruction 2026-06-24: "TODO EL BAGO CHAT Y DEMAS COSAS QUE NO
TENGAN LAS OTRAS COPIAS". This means: identify the files in the orphan
that don't exist in the active copy, and copy just those. Files that
already exist (even if older) are NOT replaced.
"""
import shutil
from pathlib import Path

HUERFANA = Path(r"C:\Program Files\BAGO\.bago\chat")
COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\.bago\chat"),
]

# Files in orphan (top-level .py + subdirs)
orphan_files = set(p.name for p in HUERFANA.glob("*.py"))
orphan_dirs = set(p.name for p in HUERFANA.iterdir() if p.is_dir())

print(f"Orphan has {len(orphan_files)} .py files and {len(orphan_dirs)} subdirs")
print()

for copy in COPIES:
    name = copy.parent.parent.name
    print(f"\n=== {name} ===")
    active_files = set(p.name for p in copy.glob("*.py"))
    active_dirs = set(p.name for p in copy.iterdir() if p.is_dir())

    missing_files = sorted(orphan_files - active_files)
    missing_dirs = sorted(orphan_dirs - active_dirs)
    print(f"  active has {len(active_files)} .py files, {len(active_dirs)} subdirs")
    print(f"  MISSING .py files ({len(missing_files)}): {missing_files}")
    print(f"  MISSING subdirs ({len(missing_dirs)}): {missing_dirs}")

    # Copy missing top-level files
    for fname in missing_files:
        shutil.copy2(HUERFANA / fname, copy / fname)
    if missing_files:
        print(f"  copied {len(missing_files)} new .py files")

    # Copy missing subdirs entirely
    for dname in missing_dirs:
        shutil.copytree(HUERFANA / dname, copy / dname)
    if missing_dirs:
        print(f"  copied {len(missing_dirs)} new subdirs")

    # Clean pycache so the new files take effect on next boot
    pc = copy / "__pycache__"
    if pc.is_dir():
        n = sum(1 for _ in pc.glob("*.pyc"))
        shutil.rmtree(pc)
        print(f"  cleared {n} pyc files")

    # Same for any subdir pycaches
    for sub in copy.rglob("__pycache__"):
        if sub.is_dir():
            shutil.rmtree(sub)

print("\n=== DONE ===")
