"""promote_bago_full.py — full .bago/ promotion.

Same pattern but for the entire .bago/ tree.
"""
import shutil
from pathlib import Path

HUERFANA = Path(r"C:\Program Files\BAGO\.bago")
COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\.bago"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\.bago"),
]


def scan(root: Path) -> set[str]:
    """Return set of all paths relative to root (excluding pycache)."""
    paths = set()
    for p in root.rglob("*"):
        if "__pycache__" in p.parts:
            continue
        rel = p.relative_to(root).as_posix()
        paths.add(rel)
    return paths


orphan_paths = scan(HUERFANA)
print(f"Orphan has {len(orphan_paths)} files/dirs (excluding pycache)")

for copy in COPIES:
    name = copy.parent.parent.name if ".bago" in copy.parent.parent.name else copy.parent.name
    print(f"\n=== {name} ({copy}) ===")
    if not copy.exists():
        print(f"  copy does not exist, skipping")
        continue
    active = scan(copy)
    missing = sorted(orphan_paths - active)
    print(f"  missing: {len(missing)}")
    # Group by subdir
    by_dir: dict[str, list[str]] = {}
    for p in missing:
        subdir = p.split("/")[0] if "/" in p else "(root)"
        by_dir.setdefault(subdir, []).append(p)
    for subdir in sorted(by_dir):
        items = by_dir[subdir]
        print(f"    {subdir}: {len(items)} missing")
        for p in items[:5]:
            print(f"      {p}")
        if len(items) > 5:
            print(f"      ... and {len(items)-5} more")
    # Copy missing files (not directories — directories are handled by copying the files inside)
    copied = 0
    for rel in missing:
        src = HUERFANA / rel
        dst = copy / rel
        if not src.exists():
            continue
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
        elif src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
    print(f"  copied {copied} missing files")
    # Clean pycache in the copy
    for sub in copy.rglob("__pycache__"):
        if sub.is_dir():
            shutil.rmtree(sub)

print("\n=== DONE ===")
