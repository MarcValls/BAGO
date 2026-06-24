"""Split repl_menu.py: extract each wizard method into its own repl_wizard_*.py."""
import re
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\repl_menu.py")
text = P.read_text(encoding="utf-8")


def extract_method(text: str, name: str) -> tuple:
    pat = re.compile(r"    def " + re.escape(name) + r"\b.*?\n", re.DOTALL)
    m = pat.search(text)
    if not m:
        return None, None
    start = m.start()
    # Find end: next "    def " or "class " or end-of-class.
    rest = text[start + 4:]
    end_m = re.search(r"\n    (def |class )", rest)
    if end_m:
        end = start + 4 + end_m.start() + 1
    else:
        end = len(text)
    return start, text[start:end].rstrip()


def reindent_wizard(body: str, method_name: str) -> str:
    """Convert `    def _foo(self):\n        ...` -> `def foo(repl):\n    ...`."""
    lines = body.split("\n")
    out = []
    in_method = False
    method_indent = None
    for line in lines:
        stripped = line.lstrip()
        if not in_method:
            if stripped.startswith("def " + method_name):
                in_method = True
                method_indent = len(line) - len(stripped)
                # Replace `def _foo(self):` with `def foo(repl):`.
                rest = stripped[len("def "):]
                rest = re.sub(r"^" + re.escape(method_name) + r"\(self\)",
                              method_name[len("_"):] + "(repl)", rest, count=1)
                rest = re.sub(r"^" + re.escape(method_name) + r"\(self,",
                              method_name[len("_"):] + "(repl,", rest, count=1)
                out.append("def " + rest)
                continue
            out.append(line)
        else:
            if line == "":
                out.append("")
                continue
            leading = len(line) - len(stripped)
            if leading < method_indent:
                in_method = False
                method_indent = None
                out.append(line)
                continue
            new_indent = max(0, leading - method_indent)
            out.append(" " * new_indent + stripped)
    return "\n".join(out)


wizards = [
    "_switch_wizard", "_agent_wizard", "_load_wizard", "_project_wizard",
    "_feedback_wizard", "_tools_wizard", "_welcome_wizard", "_quick_wizard",
    "_memory_delete_wizard", "_credential_wizard",
]

spans = []
for wiz in wizards:
    s, body = extract_method(text, wiz)
    if s is None:
        print(f"  warn: {wiz} not found")
        continue
    # Generate the new module.
    module_name = "repl_wizard_" + wiz[len("_"):].removesuffix("_wizard")
    target = P.parent / f"{module_name}.py"
    new_body = reindent_wizard(body, wiz)
    header = (
        f'"""\nModule: {module_name}\n'
        f'Free function extracted from BagoReplMenuMixin.{wiz}.\n'
        f'Public: run(repl) -> bool\n"""\n\n'
        f'from __future__ import annotations\n'
        f'from typing import TYPE_CHECKING\n\n'
        f'import renderer as R\n\n'
        f'if TYPE_CHECKING:\n    from repl import BagoREPL\n\n\n'
    )
    target.write_text(header + new_body + "\n", encoding="utf-8")
    print(f"  wrote: {target.name}")
    spans.append((s, s + len(body)))

# Replace the wizard methods in repl_menu.py with delegators.
spans.sort(reverse=True)
for s, e in spans:
    text = text[:s] + text[e:]

# Insert thin delegators before the class ends.
class_marker = "class _SafeFileHistory"
class_pos = text.find(class_marker)
if class_pos < 0:
    class_pos = len(text)

delegators = []
for wiz in wizards:
    fn_name = wiz[len("_"):]  # e.g. "switch_wizard"
    mod_name = "repl_wizard_" + wiz[len("_"):].removesuffix("_wizard")
    delegators.append(
        f"    def {wiz}(self) -> bool:\n"
        f"        from {mod_name} import run as _wiz_run\n"
        f"        return _wiz_run(self)\n"
    )

text = text[:class_pos] + "\n".join(delegators) + "\n" + text[class_pos:]
P.write_text(text, encoding="utf-8")
print(f"  trimmed: {P.name}")