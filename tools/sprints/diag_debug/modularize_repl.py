"""Modularize repl.py to the max.

After this script runs:
  repl.py              - < 300 lines: loop, command dispatch, __init__
  repl_chat.py         - chat with LLM (existing)
  repl_banner.py       - banner, version, welcome
  repl_status.py       - status, autoevolve, maybe_welcome
  repl_prompt.py       - prompt, input, multiline, paste
  repl_navigation.py   - TUI wizards (navigate, config, interactive_startup, readline)

Everything in repl.py that is a mixin helper for a single responsibility
moves out. repl.py keeps:
  - BagoREPL class skeleton (__init__, run, command routing)
  - thin delegators for the moved methods (each one calls the module's fn)
"""
import re
from pathlib import Path

CHAT = Path(r"C:\Program Files\BAGO\.bago\chat")
REPL = CHAT / "repl.py"

# First, gather each method's source by reading repl.py.
text = REPL.read_text(encoding="utf-8")

def extract_method(text, name):
    """Extract a method (def name(self, ...): ...) up to next def or class."""
    pat = re.compile(r"    def " + re.escape(name) + r"\b", re.MULTILINE)
    m = pat.search(text)
    if not m:
        return None, None
    start = m.start()
    # Find end: next "    def " or "class " at column 4.
    rest = text[start + 4:]
    end_m = re.search(r"\n    (def |class )", rest)
    if end_m:
        end = start + 4 + end_m.start() + 1  # include the leading \n
    else:
        end = len(text)
    return start, text[start:end].rstrip() + "\n"


def extract_class_body(text, class_name):
    """Extract the body of a class (between the class line and EOF or next class)."""
    pat = re.compile(r"^class " + re.escape(class_name) + r"\b.*:", re.MULTILINE)
    m = pat.search(text)
    if not m:
        return None, None
    start = m.start()
    rest = text[m.end():]
    # End of class is the next 'class ' at column 0 OR EOF.
    end_m = re.search(r"\nclass ", rest)
    if end_m:
        end = m.end() + end_m.start() + 1
    else:
        end = len(text)
    return start, text[start:end].rstrip() + "\n"


# Extract everything we need.
methods_to_extract = {
    "repl_banner.py": [
        "_print_banner",
    ],
    "repl_status.py": [
        "_print_status",
        "_auto_evolve_startup",
        "_maybe_show_welcome",
    ],
    "repl_prompt.py": [
        "_print_chat_prompt",
        "_prompt",
        "_handle_pasted_block",
        "_use_prompt_toolkit",
        "_read_main_input",
        "_timed_input",
    ],
    "repl_navigation.py": [
        "_navigate",
        "_config_wizard",
        "_interactive_startup",
        "_print_init_warnings",
        "_setup_readline",
    ],
    "repl_history.py": [
        "_SafeFileHistory",
    ],
}

extracted = {mod: [] for mod in methods_to_extract}
extracted_spans = []  # (start, end) for slicing repl.py

for mod, names in methods_to_extract.items():
    for name in names:
        if name == "_SafeFileHistory":
            start, body = extract_class_body(text, name)
        else:
            start, body = extract_method(text, name)
        if start is None:
            print(f"WARN: {name} not found")
            continue
        extracted[mod].append(body)
        extracted_spans.append((start, end := start + len(body)))

# Sort spans descending so we can splice without messing up earlier indices.
extracted_spans.sort(reverse=True)
for start, end in extracted_spans:
    text = text[:start] + text[end:]

# In the slimmed-down repl.py, replace each moved method with a thin delegator.
# We need to know the function signature for each one. We reconstruct from the
# extracted bodies (parse the first line of each).
for mod, bodies in extracted.items():
    for body in bodies:
        first_line = body.split("\n", 1)[0]
        m = re.match(r"    (def |class )(\w+)(\(.*\)):?", first_line)
        if not m:
            continue
        kind, name, sig = m.group(1), m.group(2), m.group(3)
        if kind == "class ":
            continue  # classes handled below
        delegator = f"    def {name}{sig}:\n        from .{mod[:-3]} import {name} as _impl\n        return _impl(self{', ' + ', '.join(['*a', '**kw'])} if False else None)\n"
        # That's wrong for variadic; do it properly per method.
        # We'll do explicit signatures below.

# Explicit delegator signatures (params must match originals).
delegators = {
    "_print_banner": "    def _print_banner(self) -> None:\n        from .repl_banner import print_banner\n        print_banner(self)\n",
    "_print_status": "    def _print_status(self) -> None:\n        from .repl_status import print_status\n        print_status(self)\n",
    "_auto_evolve_startup": "    def _auto_evolve_startup(self) -> None:\n        from .repl_status import auto_evolve_startup\n        auto_evolve_startup(self)\n",
    "_maybe_show_welcome": "    def _maybe_show_welcome(self) -> None:\n        from .repl_status import maybe_show_welcome\n        maybe_show_welcome(self)\n",
    "_print_chat_prompt": "    def _print_chat_prompt(self) -> None:\n        from .repl_prompt import print_chat_prompt\n        print_chat_prompt(self)\n",
    "_prompt": "    def _prompt(self) -> str:\n        from .repl_prompt import prompt\n        return prompt(self)\n",
    "_handle_pasted_block": "    def _handle_pasted_block(self, text: str) -> bool:\n        from .repl_prompt import handle_pasted_block\n        return handle_pasted_block(self, text)\n",
    "_use_prompt_toolkit": "    def _use_prompt_toolkit(self) -> bool:\n        from .repl_prompt import use_prompt_toolkit\n        return use_prompt_toolkit(self)\n",
    "_read_main_input": "    def _read_main_input(self, prompt: str) -> str:\n        from .repl_prompt import read_main_input\n        return read_main_input(self, prompt)\n",
    "_timed_input": "    def _timed_input(self, prompt: str, timeout: int = 60):\n        from .repl_prompt import timed_input\n        return timed_input(self, prompt, timeout)\n",
    "_navigate": "    def _navigate(self, title, labels, hint=None):\n        from .repl_navigation import navigate\n        return navigate(self, title, labels, hint)\n",
    "_config_wizard": "    def _config_wizard(self) -> bool:\n        from .repl_navigation import config_wizard\n        return config_wizard(self)\n",
    "_interactive_startup": "    def _interactive_startup(self) -> None:\n        from .repl_navigation import interactive_startup\n        interactive_startup(self)\n",
    "_print_init_warnings": "    def _print_init_warnings(self) -> None:\n        from .repl_navigation import print_init_warnings\n        print_init_warnings(self)\n",
    "_setup_readline": "    def _setup_readline(self) -> None:\n        from .repl_navigation import setup_readline\n        setup_readline(self)\n",
}

# Splice delegators back in, preserving original order. We don't have the
# original order, so insert all delegators at the end of the BagoREPL class
# body (just before the next class definition).
# Find the line "class _SafeFileHistory" position.
class_marker = "class _SafeFileHistory"
class_pos = text.find(class_marker)
if class_pos < 0:
    class_pos = len(text)

insert = "\n".join(delegators.values()) + "\n"
text = text[:class_pos] + insert + text[class_pos:]

REPL.write_text(text, encoding="utf-8")
print(f"slimmed {REPL}")

# Now write the per-module files with the extracted bodies.
def transform_body(body, fn_name):
    """Drop the 'self' from method def when moving to a free function."""
    # 'def name(self, ...)' -> 'def name(repl, ...)' but we use 'self' as-is
    # because the modules call _impl(self, ...).
    return body


for mod, bodies in extracted.items():
    target = CHAT / f"{mod}"
    # Build the new file from scratch.
    lines = []
    lines.append(f'"""\nModule: {mod}\nResponsibility: {mod.replace("repl_", "").replace(".py", "")}.\n"""\n')
    lines.append("from __future__ import annotations\n")
    lines.append("from typing import TYPE_CHECKING\n")
    lines.append("if TYPE_CHECKING:\n    from repl import BagoREPL\n")
    for body in bodies:
        lines.append("\n" + body.rstrip() + "\n")
    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {target}")

print("DONE")