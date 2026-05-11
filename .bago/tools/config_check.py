#!/usr/bin/env python3
"""Compatibility shim for the merged config tool."""
from config import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from config import main as _main
    raise SystemExit(_main(sys.argv[1:]))
