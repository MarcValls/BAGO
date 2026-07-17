"""Inspect non-ASCII characters and line endings in the modified files."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FILES = [
    "bago_core/launcher.py",
    "bago_core/node_control.py",
    "bago_core/node_control_render.py",
    "bago_core/node_control_ssot.py",
    "bago_core/node_control_translator.py",
    "bago_core/parsers.py",
    "bago_core/parsers_sections.py",
]

def inspect(path: Path) -> None:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    non_ascii = sorted({c for c in text if ord(c) > 127})
    crlf = text.count("\r\n")
    lf_only = text.count("\n") - crlf
    # BOM check
    has_bom = raw[:3] == b"\xef\xbb\xbf"
    print(f"{path.name}:")
    print(f"  non-ASCII chars: {len(non_ascii)} unique {''.join(non_ascii)!r}")
    print(f"  CRLF: {crlf}, LF-only: {lf_only}")
    print(f"  UTF-8 BOM: {has_bom}")
    print(f"  size: {len(raw)} bytes")

def main() -> int:
    for f in FILES:
        p = REPO_ROOT / f
        if p.exists():
            inspect(p)
        else:
            print(f"MISSING: {f}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
