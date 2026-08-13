"""Small syntax helpers shared by the tree audit scripts."""

from __future__ import annotations

import re


HOOK_RE = re.compile(r"\buse(?:Effect|Memo|Callback)\s*\(")


def extract_balanced(text: str, start: int, opening: str, closing: str) -> str:
    open_index = text.find(opening, start)
    if open_index < 0:
        return ""
    depth = 0
    quote = ""
    escaped = False
    line_comment = False
    block_comment = False
    index = open_index
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "/" and next_char == "/":
            line_comment = True
            index += 1
        elif char == "/" and next_char == "*":
            block_comment = True
            index += 1
        elif char in "'\"`":
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
        index += 1
    return ""


def extract_hook_call(text: str, start: int) -> str:
    return extract_balanced(text, start, "(", ")")


def split_hook_call(call: str) -> tuple[str, str] | None:
    open_index = call.find("(")
    if open_index < 0 or not call.endswith(")"):
        return None
    inner = call[open_index + 1:-1]
    depths = {"(": 0, "[": 0, "{": 0}
    pairs = {")": "(", "]": "[", "}": "{"}
    quote = ""
    escaped = False
    line_comment = False
    block_comment = False
    commas: list[int] = []
    index = 0
    while index < len(inner):
        char = inner[index]
        next_char = inner[index + 1] if index + 1 < len(inner) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 1
        elif quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "/" and next_char == "/":
            line_comment = True
            index += 1
        elif char == "/" and next_char == "*":
            block_comment = True
            index += 1
        elif char in "'\"`":
            quote = char
        elif char in depths:
            depths[char] += 1
        elif char in pairs:
            depths[pairs[char]] = max(0, depths[pairs[char]] - 1)
        elif char == "," and not any(depths.values()):
            commas.append(index)
        index += 1
    if not commas:
        return None
    separator = commas[-1]
    body = inner[:separator].strip()
    deps = inner[separator + 1:].strip()
    if not (deps.startswith("[") and deps.endswith("]")):
        return None
    return body, deps[1:-1].strip()


def iter_hook_calls(text: str):
    for match in HOOK_RE.finditer(text):
        call = extract_hook_call(text, match.start())
        parts = split_hook_call(call) if call else None
        if call and parts:
            yield match.start(), match.group(0).split("(", 1)[0], call, parts[0], parts[1]


def mask_literals_and_comments(text: str) -> str:
    result = list(text)
    quote = ""
    escaped = False
    line_comment = False
    block_comment = False
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
            else:
                result[index] = " "
        elif block_comment:
            result[index] = " "
            if char == "*" and next_char == "/":
                result[index + 1] = " "
                block_comment = False
                index += 1
        elif quote:
            result[index] = " "
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
        elif char == "/" and next_char == "/":
            result[index] = result[index + 1] = " "
            line_comment = True
            index += 1
        elif char == "/" and next_char == "*":
            result[index] = result[index + 1] = " "
            block_comment = True
            index += 1
        elif char in "'\"`":
            result[index] = " "
            quote = char
        index += 1
    return "".join(result)


def find_named_callable(text: str, name: str, before: int) -> str:
    matches = list(re.finditer(rf"\bconst\s+{re.escape(name)}\s*=", text[:before]))
    if not matches:
        return ""
    start = matches[-1].start()
    assignment = text[matches[-1].end():before].lstrip()
    assignment_start = matches[-1].end() + len(text[matches[-1].end():before]) - len(assignment)
    if assignment.startswith("useCallback"):
        return extract_hook_call(text, assignment_start)
    arrow = assignment.find("=>")
    if arrow < 0:
        return ""
    body_start = assignment_start + arrow + 2
    return extract_balanced(text, body_start, "{", "}")
