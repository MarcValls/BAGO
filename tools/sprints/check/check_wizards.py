import sys
sys.path.insert(0, r"C:\Program Files\BAGO\.bago\chat")
import py_compile

for mod in ["repl_menu", "repl_wizard_switch", "repl_wizard_agent", "repl_wizard_load",
            "repl_wizard_project", "repl_wizard_feedback", "repl_wizard_tools",
            "repl_wizard_welcome", "repl_wizard_quick", "repl_wizard_memory_delete",
            "repl_wizard_credential", "repl", "renderer"]:
    try:
        py_compile.compile(rf"C:\Program Files\BAGO\.bago\chat\{mod}.py", doraise=True)
        print(f"  {mod}: OK")
    except py_compile.PyCompileError as exc:
        print(f"  {mod}: FAIL -- {exc}")

print()
try:
    import repl
    print(f"repl.run: {hasattr(repl.BagoREPL, 'run')}")
    print(f"_switch_wizard: {hasattr(repl.BagoREPL, '_switch_wizard')}")
    print(f"_agent_wizard: {hasattr(repl.BagoREPL, '_agent_wizard')}")
    print(f"_credential_wizard: {hasattr(repl.BagoREPL, '_credential_wizard')}")
except Exception as exc:
    print(f"  repl FAIL -- {exc}")

# Count wizard modules
import importlib
importlib.invalidate_caches()
n = 0
from pathlib import Path
for p in Path(r"C:\Program Files\BAGO\.bago\chat").glob("repl_wizard_*.py"):
    n += 1
print(f"wizard modules: {n}")