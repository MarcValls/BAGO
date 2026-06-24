"""test_module_kind.py — distinguish real modules from partial scripts."""
import ast
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\tools")
from bago_inventory import gather_inventory

root = Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO")
data = gather_inventory(root)


def classify(path: Path) -> str:
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except Exception:
        return "BROKEN"
    has_main_guard = False
    has_callable = False
    top_level_stmts = 0
    for node in tree.body:
        if isinstance(node, ast.If):
            try:
                test = node.test
                if isinstance(test, ast.Compare):
                    left = test.left
                    if isinstance(left, ast.Name) and left.id == "__name__":
                        has_main_guard = True
            except Exception:
                pass
            top_level_stmts += 1
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            has_callable = True
        elif isinstance(node, (ast.Expr, ast.Assign)):
            top_level_stmts += 1
    if has_main_guard:
        return "MODULE"
    if has_callable and top_level_stmts > 0:
        return "MIXED"
    if has_callable:
        return "PARTIAL"
    if top_level_stmts > 0:
        return "SCRIPT"
    return "EMPTY"


tools = [(root / t["path"], "tool") for t in data["tools"]]
agents = [(root / a["path"], "agent") for a in data["agents"]]
modules = [(root / m["path"], "module") for m in data["modules"]]

counts = {"MODULE": 0, "PARTIAL": 0, "SCRIPT": 0, "MIXED": 0, "EMPTY": 0, "BROKEN": 0}
by_kind = {"tool": dict(counts), "agent": dict(counts), "module": dict(counts)}

for path, kind in tools + agents + modules:
    if not path.exists():
        continue
    cls = classify(path)
    counts[cls] += 1
    by_kind[kind][cls] += 1

print("=== Classification of .py files in inventory ===")
print()
print(f"  {'kind':<10} {'MODULE':>8} {'PARTIAL':>8} {'SCRIPT':>8} {'MIXED':>8} {'EMPTY':>8} {'BROKEN':>8}")
for k in ("tool", "agent", "module"):
    row = by_kind[k]
    print(f"  {k:<10} {row['MODULE']:>8} {row['PARTIAL']:>8} {row['SCRIPT']:>8} {row['MIXED']:>8} {row['EMPTY']:>8} {row['BROKEN']:>8}")

print()
print("Total:")
print(f"  MODULE  (real runnable): {counts['MODULE']}")
print(f"  PARTIAL (library/class): {counts['PARTIAL']}")
print(f"  SCRIPT  (statements):    {counts['SCRIPT']}")
print(f"  MIXED   (both):          {counts['MIXED']}")
print(f"  EMPTY:                   {counts['EMPTY']}")
print(f"  BROKEN:                  {counts['BROKEN']}")

print()
print("=== Sample classifications ===")
for path, kind in tools[:3]:
    cls = classify(path)
    print(f"  [{kind}] {path.name} -> {cls}")
for path, kind in agents[:3]:
    cls = classify(path)
    print(f"  [{kind}] {path.name} -> {cls}")
for path, kind in modules[:5]:
    cls = classify(path)
    print(f"  [{kind}] {path.name} -> {cls}")
