#!/usr/bin/env python3
"""verify_release.py
Canonical release gate entry point for BAGO.

This wrapper preserves the historical `verify_release_463.py` script while
giving active docs and automation a clean, version-agnostic name.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verify_release_463 import (  # noqa: E402,F401
    DISPLAY_VERSION,
    EXE_NAME,
    ZIP_NAME,
    _run_tests,
    main as _compat_main,
    run_checks,
)


def main(argv: list[str] | None = None) -> int:
    return _compat_main(argv, script_name="verify_release.py")


if __name__ == "__main__":
    raise SystemExit(main())
