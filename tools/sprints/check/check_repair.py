import sys
import py_compile
sys.path.insert(0, r"C:\Program Files\BAGO\bago_core\codegen")
for m in ["repair_loop", "repair_loop_models", "repair_loop_helpers", "task_classifier"]:
    try:
        py_compile.compile(rf"C:\Program Files\BAGO\bago_core\codegen\{m}.py", doraise=True)
        print(f"  {m}: OK")
    except py_compile.PyCompileError as exc:
        print(f"  {m}: FAIL -- {exc}")
import repair_loop
print(f"RepairFeedback: {hasattr(repair_loop, 'RepairFeedback')}")
print(f"run_repair_loop: {callable(getattr(repair_loop, 'run_repair_loop', None))}")