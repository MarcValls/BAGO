"""Normalize all .py files in bago_core/, tests/, tools/, docs/ to UTF-8
(no BOM) + LF line endings.

Python 3 standard. Eliminates git warnings about CRLF/LF mixing.
Replaces Spanish accented letters and em-dashes in comments with ASCII
equivalents to keep the repo editor-friendly.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGETS = [
    REPO_ROOT / "bago_core",
    REPO_ROOT / "tests",
    REPO_ROOT / "tools",
]

# Substitutions for non-ASCII characters in source files. Applied to
# comments, docstrings, and string literals; safe because the BAGO
# codebase uses ASCII English for user-facing strings.
SUBS: dict[str, str] = {
    "\u00e1": "a", "\u00e9": "e", "\u00ed": "i", "\u00f3": "o", "\u00fa": "u",
    "\u00c1": "A", "\u00c9": "E", "\u00cd": "I", "\u00d3": "O", "\u00da": "U",
    "\u00f1": "n", "\u00d1": "N",
    "\u2014": "--",  # em-dash
    "\u2013": "-",   # en-dash
    "\u2026": "...",
    "\u2192": "->", "\u2190": "<-",
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u2502": "|", "\u2500": "-", "\u2514": "+", "\u251c": "+",
    "\u00ba": "o", "\u00aa": "a",
}

def normalize(path: Path) -> tuple[bool, str]:
    """Returns (changed, summary)."""
    raw = path.read_bytes()
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    text = raw.decode("utf-8", errors="replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    original = text
    for k, v in SUBS.items():
        text = text.replace(k, v)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if text != original:
        path.write_bytes(text.encode("utf-8"))
        return True, "rewrote"
    return False, "clean"

def iter_targets() -> list[Path]:
    found: list[Path] = []
    for target in TARGETS:
        if target.exists():
            found.extend(target.rglob("*.py"))
    return found

def main() -> int:
    changed = 0
    total = 0
    for path in iter_targets():
        total += 1
        was_changed, summary = normalize(path)
        if was_changed:
            changed += 1
            print(f"  CHANGED  {path.relative_to(REPO_ROOT)}")
    print(f"\nnormalized {changed}/{total} files")
    return 0

if __name__ == "__main__":
    sys.exit(main())
