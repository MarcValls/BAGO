"""Heal repl_<area>.py modules that still have methods inside TYPE_CHECKING.

The buggy modularizer extracted method bodies and wrote them inside
`if TYPE_CHECKING:`. For runtime use, we need them at module level, indented
to 0 spaces, with `self` renamed to `repl`.
"""
import re
from pathlib import Path

CHAT = Path(r"C:\Program Files\BAGO\.bago\chat")


def reindent_method_to_module_function(body: str, method_name: str, fn_name: str) -> str:
    """Pull a method out of `if TYPE_CHECKING:` and re-indent it to module level."""
    lines = body.splitlines()
    out: list[str] = []
    in_def = False
    method_indent = None
    skip_container = False
    container_indent = None

    for line in lines:
        stripped = line.lstrip()
        if not in_def:
            if stripped.startswith("def " + method_name):
                in_def = True
                method_indent = len(line) - len(stripped)
                rest = stripped[len("def "):]
                rest = re.sub(
                    r"^" + re.escape(method_name) + r"\(self(,|\))",
                    fn_name + r"(repl\1", rest, count=1,
                )
                out.append("def " + rest)
                continue
            if stripped.startswith(("if ", "for ", "while ", "with ", "try", "elif ", "else:", "except", "finally:")):
                container_indent = len(line) - len(stripped)
                skip_container = True
                continue
            if line == "" or stripped.startswith("#"):
                out.append(line)
                continue
            if container_indent is None:
                out.append(line)
        else:
            if line == "":
                out.append("")
                continue
            leading = len(line) - len(line.lstrip())
            if leading < method_indent:
                in_def = False
                method_indent = None
                out.append(line)
                continue
            new_indent = max(0, leading - method_indent)
            out.append(" " * new_indent + line.lstrip())
    return "\n".join(out)


def heal_module(path: Path, methods_to_extract: list, body_marker_re: str):
    text = path.read_text(encoding="utf-8")
    if not body_marker_re.search(text):
        print(f"  {path.name}: no body markers found, skipping")
        return False

    # Find the `if TYPE_CHECKING:` block.
    type_checking_idx = text.find("if TYPE_CHECKING:")
    if type_checking_idx < 0:
        print(f"  {path.name}: no TYPE_CHECKING block")
        return False
    # Find the end of that block: next line at column 0 that's not empty/comment.
    lines = text.splitlines()
    tc_line_idx = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("if TYPE_CHECKING"):
            tc_line_idx = i
            break
    if tc_line_idx is None:
        return False
    # Find end: first line at column 0 after tc_line_idx that is non-empty and
    # not part of an indented block.
    end_idx = len(lines)
    base_indent = len(lines[tc_line_idx]) - len(lines[tc_line_idx].lstrip())
    for j in range(tc_line_idx + 1, len(lines)):
        ln = lines[j]
        if ln.strip() == "":
            continue
        leading = len(ln) - len(ln.lstrip())
        if leading <= base_indent:
            end_idx = j
            break
    # Extract the indented body and rewrite each method.
    block_lines = lines[tc_line_idx + 1:end_idx]
    block_text = "\n".join(block_lines)
    new_block_parts: list[str] = []
    used_names: set = set()
    for method_name in methods_to_extract:
        # Find the def line for this method inside the block.
        m = re.search(rf"^    def {re.escape(method_name)}\(", block_text, re.MULTILINE)
        if not m:
            continue
        # Slice from this def until next def or class at indent <= 4.
        start = m.start()
        rest = block_text[start:]
        end_m = re.search(r"\n    (def |class )", rest[len("    def " + method_name + "("):])
        body = rest[: end_m.start() + 1] if end_m else rest
        fn_name = method_name.lstrip("_")
        rewritten = reindent_method_to_module_function(body, method_name, fn_name)
        new_block_parts.append("\n" + rewritten.rstrip() + "\n")
        used_names.add(method_name)
    # If there are defs in the block we don't have in the explicit list, still extract them.
    leftover_defs = re.findall(r"^    def (\w+)\(", block_text, re.MULTILINE)
    for leftover in leftover_defs:
        if leftover in used_names or leftover.startswith("__"):
            continue
        m = re.search(rf"^    def {re.escape(leftover)}\(", block_text, re.MULTILINE)
        if not m:
            continue
        start = m.start()
        rest = block_text[start:]
        end_m = re.search(r"\n    (def |class )", rest[len("    def " + leftover + "("):])
        body = rest[: end_m.start() + 1] if end_m else rest
        fn_name = leftover.lstrip("_")
        rewritten = reindent_method_to_module_function(body, leftover, fn_name)
        new_block_parts.append("\n" + rewritten.rstrip() + "\n")
        used_names.add(leftover)

    if not new_block_parts:
        print(f"  {path.name}: no defs found inside TYPE_CHECKING block")
        return False

    # Replace the TYPE_CHECKING block with the rewritten module-level functions.
    new_block = "".join(new_block_parts)
    head = lines[:tc_line_idx]
    tail = lines[end_idx:]
    new_lines = head + [new_block] + tail
    new_text = "\n".join(new_lines)
    path.write_text(new_text, encoding="utf-8")
    print(f"  {path.name}: healed, {len(used_names)} fn(s) moved to module level")
    return True


# Modules and their expected method names.
HEAL_PLAN = {
    "repl_banner.py": ["_print_banner"],
    "repl_status.py": ["_print_status", "_auto_evolve_startup", "_maybe_show_welcome"],
    "repl_prompt.py": [
        "_print_chat_prompt", "_prompt", "_handle_pasted_block",
        "_use_prompt_toolkit", "_read_main_input", "_timed_input",
    ],
    "repl_navigation.py": [
        "_navigate", "_config_wizard", "_interactive_startup",
        "_print_init_warnings", "_setup_readline",
    ],
}

for mod_name, methods in HEAL_PLAN.items():
    path = CHAT / mod_name
    if not path.exists():
        print(f"  {mod_name}: missing, skip")
        continue
    heal_module(path, methods, re.compile(r"def\s+\w+\("))

print("done")