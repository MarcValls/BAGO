"""Verify both splits compile and re-exports work."""
import sys
sys.path.insert(0, r"C:\Program Files\BAGO\bago_core\codegen")
import py_compile

for m in ["repair_loop", "repair_loop_models", "repair_loop_helpers",
         "task_classifier", "task_classifier_models"]:
    try:
        py_compile.compile(rf"C:\Program Files\BAGO\bago_core\codegen\{m}.py", doraise=True)
        print(f"  {m}: OK")
    except py_compile.PyCompileError as exc:
        print(f"  {m}: FAIL -- {exc}")

# Smoke import + symbol surface check.
try:
    import repair_loop
    print(f"repair_loop.RepairFeedback: {hasattr(repair_loop, 'RepairFeedback')}")
    print(f"repair_loop.RepairAttempt: {hasattr(repair_loop, 'RepairAttempt')}")
    print(f"repair_loop.RepairVerdict: {hasattr(repair_loop, 'RepairVerdict')}")
    print(f"repair_loop.run_repair_loop: {callable(getattr(repair_loop, 'run_repair_loop', None))}")
except Exception as exc:
    print(f"repair_loop import: FAIL -- {exc}")

try:
    import task_classifier
    print(f"task_classifier.CodeTaskClassification: {hasattr(task_classifier, 'CodeTaskClassification')}")
    print(f"task_classifier.classify_code_request: {callable(getattr(task_classifier, 'classify_code_request', None))}")
except Exception as exc:
    print(f"task_classifier import: FAIL -- {exc}")