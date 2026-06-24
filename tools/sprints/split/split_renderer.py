"""Split renderer.py: extract text measurement, box, and logo into separate modules."""
import re
from pathlib import Path

P = Path(r"C:\Program Files\BAGO\.bago\chat\renderer.py")
text = P.read_text(encoding="utf-8")


def extract_block(text: str, name: str) -> tuple:
    """Extract a top-level function or class definition."""
    pat = re.compile(r"^(?:def|class) " + re.escape(name) + r"\b.*?\n(?=^(?:def|class) |\Z)",
                     re.MULTILINE | re.DOTALL)
    m = pat.search(text)
    if not m:
        return None, None
    return m.start(), m.group(0).rstrip()


def split_at_top_level(text: str) -> list:
    """Split text into a list of (kind, name, body) chunks."""
    chunks = []
    for m in re.finditer(r"^(def|class) (\w+)\b", text, re.MULTILINE):
        chunks.append((m.start(), m.group(1), m.group(2)))
    chunks.sort()
    result = []
    for i, (start, kind, name) in enumerate(chunks):
        end = chunks[i + 1][0] if i + 1 < len(chunks) else len(text)
        result.append((kind, name, text[start:end].rstrip()))
    return result


# Define what stays in renderer.py (the public face) and what moves.
keep_in_renderer = {
    "_supports_color", "Color", "colorize", "dim", "bold", "ok", "warn", "error",
    "info", "accent", "bright_black", "magenta", "box", "bago_logo_text",
    "banner", "qwen_status_block", "status_line",
    "print_message_qwen", "print_message", "print_switch_notification",
    "print_table",
}

move_to = {
    "_visible_width": "renderer_text",
    "_wrap_line": "renderer_text",
    "_unicodedata_east_asian_width": "renderer_text",
    "_qwen_box": "renderer_box",
    "print_qwen_input": "renderer_box",
}

chunks = split_at_top_level(text)

# Collect bodies per module.
bodies_per_module: dict = {"renderer_text": [], "renderer_box": []}

# Build new renderer.py with just the kept chunks + re-exports from
# the extracted modules.
keep_lines = []
for kind, name, body in chunks:
    if name in move_to:
        bodies_per_module[move_to[name]].append(body)
    elif name in keep_in_renderer:
        keep_lines.append(body + "\n")
    else:
        # Unknown — keep it for safety (later audit will flag).
        keep_lines.append(body + "\n")

# Rewrite renderer.py as a thin facade that re-exports.
header = '''"""renderer.py - thin facade.

The renderer used to be a monolithic 575-line module. After the 4.8.0 split,
it now just re-exports the pieces that live in:

  - renderer_text.py  : visible_width / wrap_line / east_asian_width
  - renderer_box.py   : _qwen_box / print_qwen_input
  - renderer_logo.py   : (logo + banner are still here, see below)

Anything new related to UI rendering goes in one of those three modules.
"""

from __future__ import annotations

import sys
from pathlib import Path as _Path

# Make sibling modules importable when this package is imported.
_chat_dir = _Path(__file__).resolve().parent
if str(_chat_dir) not in sys.path:
    sys.path.insert(0, str(_chat_dir))

# Re-export the extracted pieces.
from renderer_text import (  # noqa: E402, F401
    _visible_width,
    _wrap_line,
    _unicodedata_east_asian_width,
)
from renderer_box import _qwen_box, print_qwen_input  # noqa: E402, F401

# This file keeps the bits that don't yet deserve their own module
# (colors, logo, banner, message print helpers).
'''

new_renderer = header + "\n".join(keep_lines)

# Inject the _qwen_box's body into renderer_box.py via a re-import shim
# (since the rest of the code calls renderer._qwen_box directly).
# We don't need to change call sites — renderer.py still re-exports it.
P.write_text(new_renderer, encoding="utf-8")
print(f"trimmed: {P.name}")

# Write renderer_text.py.
text_module = (
    '"""\nModule: renderer_text\n'
    'Text measurement helpers: visible width, line wrapping, east-asian width.\n'
    'Extracted from renderer.py during the 4.8.0 modularization.\n"""\n\n'
    'from __future__ import annotations\n'
    'import unicodedata\n'
    '\n\n'
)
text_module += "\n\n".join(b for b in bodies_per_module["renderer_text"])
(CHAT := P.parent).joinpath("renderer_text.py").write_text(text_module, encoding="utf-8")
print("wrote: renderer_text.py")

# Write renderer_box.py.
box_module = (
    '"""\nModule: renderer_box\n'
    'Qwen-style framed box and the persistent input box helper.\n'
    'Extracted from renderer.py during the 4.8.0 modularization.\n"""\n\n'
    'from __future__ import annotations\n'
    'import sys\n'
    'from typing import TYPE_CHECKING\n\n'
    'import renderer as R\n\n'
    'if TYPE_CHECKING:\n    pass\n\n\n'
)
box_module += "\n\n".join(b for b in bodies_per_module["renderer_box"])
(CHAT).joinpath("renderer_box.py").write_text(box_module, encoding="utf-8")
print("wrote: renderer_box.py")