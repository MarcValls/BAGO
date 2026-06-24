"""restore_v472_official.py — apply release v4.7.2 official to 3 copies.

The user asked to 'continue' — restore everything to release v4.7.2 state
without my huérfano additions. Keep ONLY what the release ships.

Strategy:
1. For each target, WIPE the directories the release would fully
   replace (.bago/chat/, .bago/core/, bago_core/, .bago/tools/, etc.)
2. Copy release's .bago/, bago_core/, scripts/ over the targets.
3. Sync release_version.txt and versions.json.
4. Clean pycache everywhere.
"""
import shutil
from pathlib import Path

RELEASE = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\Temp\bago_v4.7.2\BAGO-4.7.2")
TARGETS = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch"),
]

# These top-level dirs/files exist in release and should replace target's
SUBDIRS = [
    ".bago",
    "bago_core",
]
TOPLEVEL_FILES = [
    "release_version.txt",
    "versions.json",
]


def wipe_and_copy(target: Path, sub: str) -> int:
    src = RELEASE / sub
    dst = target / sub
    if not src.exists():
        return 0
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    n = sum(1 for _ in dst.rglob("*.py"))
    return n


def sync_file(target: Path, fname: str) -> bool:
    src = RELEASE / fname
    dst = target / fname
    if not src.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


for target in TARGETS:
    print(f"\n=== {target.parent.parent.name} ({target}) ===")
    if not target.exists():
        print(f"  target does not exist; skipping")
        continue
    for sub in SUBDIRS:
        n = wipe_and_copy(target, sub)
        print(f"  wiped+copied {sub}/ ({n} .py files)")
    for f in TOPLEVEL_FILES:
        if sync_file(target, f):
            print(f"  synced {f}")
    # Clean pycache
    for sub in target.rglob("__pycache__"):
        if sub.is_dir():
            shutil.rmtree(sub)
    print(f"  cleared pycache")

print("\n=== DONE: 3 copies now match release v4.7.2 ===")
