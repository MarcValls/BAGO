"""Replace the first 25 lines of each affected file with a clean header."""
from pathlib import Path

for path, new_header in [
    (
        r"C:\Program Files\BAGO\bago_core\codegen\repair_loop.py",
        '"""repair_loop.py - thin facade.\n\n'
        'Dataclasses live in repair_loop_models.py.\n'
        'Helpers live in repair_loop_helpers.py.\n'
        'Public entry point `run_repair_loop` stays here.\n"""\n\n'
    ),
    (
        r"C:\Program Files\BAGO\bago_core\codegen\task_classifier.py",
        '"""task_classifier.py - thin facade.\n\n'
        'CodeTaskClassification + helpers live in task_classifier_models.py.\n'
        'Public entry point `classify_code_request` stays here.\n"""\n\n'
    ),
]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    lines = text.split("\n")
    # Find the first line that is a real code line (not blank, not docstring,
    # not comment) AND it's NOT `from __future__`. After the duplicate
    # `from __future__` block, we have the original code. We replace from
    # line 0 up to (but not including) the first occurrence of `def ` or
    # `class ` from the original content.
    body_start = None
    for i, line in enumerate(lines):
        if line.startswith("def ") or line.startswith("class "):
            body_start = i
            break
    if body_start is None:
        print(f"  no body in {p.name}")
        continue
    new_text = new_header + "\n".join(lines[body_start:])
    p.write_text(new_text, encoding="utf-8")
    print(f"fixed: {p.name}")