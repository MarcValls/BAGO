"""Split repl_menu.py further: extract _credential_wizard_provider."""
import re
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\repl_menu.py")
text = P.read_text(encoding="utf-8")

# Extract _credential_wizard_provider method.
def extract_method(text: str, name: str) -> tuple:
    pat = re.compile(r"    def " + re.escape(name) + r"\b.*?\n", re.DOTALL)
    m = pat.search(text)
    if not m:
        return None, None
    start = m.start()
    rest = text[start + 4:]
    end_m = re.search(r"\n    (def |class )", rest)
    if end_m:
        end = start + 4 + end_m.start() + 1
    else:
        end = len(text)
    return start, text[start:end].rstrip()


def reindent_wizard(body: str, method_name: str) -> str:
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
                rest = stripped[len("def "):]
                # Convert `_foo(self, X, Y)` -> `foo(repl, X, Y)`.
                rest = re.sub(r"^" + re.escape(method_name) + r"\(self(,|\))",
                              method_name[len("_"):] + r"(repl\1", rest, count=1)
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


s, body = extract_method(text, "_credential_wizard_provider")
if s is None:
    print("not found")
else:
    target = P.parent / "repl_wizard_credential_provider.py"
    new_body = reindent_wizard(body, "_credential_wizard_provider")
    header = (
        '"""\nModule: repl_wizard_credential_provider\n'
        'Free function extracted from BagoReplMenuMixin._credential_wizard_provider.\n'
        'Public: run(repl, provider, silent=False) -> bool\n"""\n\n'
        'from __future__ import annotations\n'
        'from typing import TYPE_CHECKING\n\n'
        'import renderer as R\n\n'
        'if TYPE_CHECKING:\n    from repl import BagoREPL\n\n\n'
    )
    target.write_text(header + new_body + "\n", encoding="utf-8")
    print(f"wrote: {target.name}")

    # Replace in repl_menu.py with a delegator.
    end_m = re.search(r"\n    (def |class )", body)
    body_full = body + "\n"  # match what was there
    text = text[:s] + text[s + len(body):]
    # Insert the delegator where the method used to be.
    delegator = (
        "    def _credential_wizard_provider(self, provider: str, silent: bool = False) -> bool:\n"
        "        from repl_wizard_credential_provider import run as _wiz_run\n"
        "        return _wiz_run(self, provider, silent)\n"
    )
    text = text[:s] + delegator + text[s:]
    P.write_text(text, encoding="utf-8")
    print(f"trimmed: {P.name}")