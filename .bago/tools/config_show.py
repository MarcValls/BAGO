#!/usr/bin/env python3
"""Compatibility shim for config show."""
from config import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from config import main as _main
    raise SystemExit(_main(["show", *sys.argv[1:]]))
