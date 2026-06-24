"""sync_bago_core.py — sync bago_core/ from orphan to 3 copies.

The .bago/core/ had state_root support but bago_core/versioning.py is also
missing. Sync the whole bago_core/ tree now.
"""
import filecmp
import shutil
from pathlib import Path

HUERFANA = Path(r"C:\Program Files\BAGO\bago_core")
COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\bago_core"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\bago_core"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\bago_core"),
]


def scan(root: Path) -> set[str]:
    paths = set()
    if not root.exists():
        return paths
    for p in root.rglob("*"):
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        rel = p.relative_to(root).as_posix()
        paths.add(rel)
    return paths


huerfana_files = scan(HUERFANA)
print(f"Orphan has {len(huerfana_files)} files in bago_core/ (no pycache)")

for copy in COPIES:
    name = copy.parent.parent.name if ".bago" in copy.parent.parent.name else copy.parent.name
    print(f"\n=== {name} ===")
    if not copy.exists():
        print(f"  copy does not exist, skipping")
        continue
    active = scan(copy)
    missing = sorted(huerfana_files - active)
    different = []
    for rel in active & huerfana_files:
        s = HUERFANA / rel
        d = copy / rel
        if s.is_file() and d.is_file() and not filecmp.cmp(s, d, shallow=False):
            different.append(rel)
    print(f"  missing: {len(missing)}")
    for rel in missing:
        s = HUERFANA / rel
        d = copy / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_file():
            shutil.copy2(s, d)
    if missing:
        print(f"  copied {len(missing)} new files")
    print(f"  different: {len(different)}")
    for rel in different:
        s = HUERFANA / rel
        d = copy / rel
        if s.is_file():
            shutil.copy2(s, d)
    if different:
        print(f"  updated {len(different)} existing files")
    # Clear pycache
    for sub in copy.rglob("__pycache__"):
        if sub.is_dir():
            shutil.rmtree(sub)
    for f in copy.rglob("*.pyc"):
        f.unlink()
