"""promote_core_full.py — full .bago/core promotion from orphan to 3 copies.

Same strategy as promote_missing_only.py but for the .bago/core/ subdir
which has runtime dependencies (state_paths, learning_writer, etc.).
"""
import shutil
from pathlib import Path

HUERFANA = Path(r"C:\Program Files\BAGO\.bago\core")
COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\core"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\.bago\core"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\.bago\core"),
]

orphan_files = set(p.name for p in HUERFANA.glob("*.py"))
orphan_dirs = set(p.name for p in HUERFANA.iterdir() if p.is_dir())

print(f"Orphan has {len(orphan_files)} .py files and {len(orphan_dirs)} subdirs")
for copy in COPIES:
    name = copy.parent.parent.name
    print(f"\n=== {name} ===")
    active_files = set(p.name for p in copy.glob("*.py"))
    active_dirs = set(p.name for p in copy.iterdir() if p.is_dir())
    missing_files = sorted(orphan_files - active_files)
    missing_dirs = sorted(orphan_dirs - active_dirs)
    print(f"  MISSING .py files ({len(missing_files)}): {missing_files}")
    print(f"  MISSING subdirs ({len(missing_dirs)}): {missing_dirs}")
    for fname in missing_files:
        shutil.copy2(HUERFANA / fname, copy / fname)
    if missing_files:
        print(f"  copied {len(missing_files)} new .py files")
    for dname in missing_dirs:
        if (HUERFANA / dname).is_dir():
            dstdir = copy / dname
            if dstdir.exists():
                shutil.rmtree(dstdir)
            shutil.copytree(HUERFANA / dname, dstdir)
    if missing_dirs:
        print(f"  copied {len(missing_dirs)} new subdirs")
    # Clean pycache
    pc = copy / "__pycache__"
    if pc.is_dir():
        shutil.rmtree(pc)
    for sub in copy.rglob("__pycache__"):
        if sub.is_dir():
            shutil.rmtree(sub)

print("\n=== DONE ===")
