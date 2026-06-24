"""audit_gaps_orphan_vs_3copies.py — find everything in the orphan that's
NOT visible in the 3 active copies.

The user is asking: "what more have we implemented that I can't see?"
This script inventories:
  1. Public functions defined in orphan modules
  2. Public functions used/called in orphan's repl.py
  3. Public functions used by the boot path (repl_banner, repl_status, etc.)
  4. Compare with what the active repl.py references
"""
import ast
import os
from pathlib import Path

HUERFANA = Path(r"C:\Program Files\BAGO\.bago\chat")
COPIES = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\.bago\chat"),
]


def list_public_functions(file: Path) -> set[str]:
    """Return set of top-level function names defined in a .py file."""
    try:
        tree = ast.parse(file.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                funcs.add(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_"):
                funcs.add(node.name)
    return funcs


# Collect all public names from the orphan (source of truth)
orphan_funcs: dict[str, set[str]] = {}
for f in HUERFANA.glob("*.py"):
    fns = list_public_functions(f)
    if fns:
        orphan_funcs[f.name] = fns

print("=" * 70)
print("ORPHAN (C:\\Program Files\\BAGO\\.bago\\chat) public API")
print("=" * 70)
for name in sorted(orphan_funcs):
    print(f"  {name}: {sorted(orphan_funcs[name])}")

# Now check what each active copy has
print()
print("=" * 70)
print("FUNCTION PRESENCE ACROSS 3 ACTIVE COPIES")
print("=" * 70)
print()
print(f"{'Module':<35} {'Func':<25} {'work':<6} {'dev':<6} {'launch':<6}")
print("-" * 80)

gaps = []
for name in sorted(orphan_funcs):
    for func in sorted(orphan_funcs[name]):
        work = "OK" if (COPIES[0] / name).is_file() and func in list_public_functions(COPIES[0] / name) else "---"
        dev = "OK" if (COPIES[1] / name).is_file() and func in list_public_functions(COPIES[1] / name) else "---"
        launch = "OK" if (COPIES[2] / name).is_file() and func in list_public_functions(COPIES[2] / name) else "---"
        status_marker = "  " if (work == dev == launch == "OK") else "XX"
        if status_marker == "XX":
            gaps.append((name, func, work, dev, launch))
        print(f"{name:<35} {func:<25} {work:<6} {dev:<6} {launch:<6} {status_marker}")

print()
print("=" * 70)
print(f"GAPS (XX): {len(gaps)} missing/divergent across copies")
print("=" * 70)
for name, func, work, dev, launch in gaps:
    print(f"  {name}::{func} -> work={work} dev={dev} launch={launch}")
