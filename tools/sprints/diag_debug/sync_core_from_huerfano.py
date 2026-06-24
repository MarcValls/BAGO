"""sync_core_from_huerfano.py — replace .bago/core/ files that differ.

For each of the 3 active copies, check every .py in .bago/core/ against
the orphan's .bago/core/, and copy if they differ. This eliminates the
"missing state_root argument" cascade.
"""
import filecmp
import shutil
from pathlib import Path

HUERFANA = Path(r"C:\Program Files\BAGO\.bago\core")
COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\core"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\.bago\core"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\.bago\core"),
]

huerfana_files = {p.name for p in HUERFANA.glob("*.py")}
print(f"Orphan has {len(huerfana_files)} .py files in .bago/core/")
print()

for copy in COPIES:
    print(f"\n=== {copy.parent.parent.name} ===")
    updated = 0
    for fname in huerfana_files:
        src = HUERFANA / fname
        dst = copy / fname
        if not dst.is_file():
            shutil.copy2(src, dst)
            print(f"  + new: {fname}")
            updated += 1
            continue
        if not filecmp.cmp(src, dst, shallow=False):
            shutil.copy2(src, dst)
            print(f"  ~ updated: {fname}")
            updated += 1
    if updated == 0:
        print("  (already in sync)")
    # Clear pycache
    pc = copy / "__pycache__"
    if pc.is_dir():
        shutil.rmtree(pc)

print("\n=== DONE ===")
