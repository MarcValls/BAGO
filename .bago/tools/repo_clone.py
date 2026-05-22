#!/usr/bin/env python3
"""Compatibility shim for repo clone commands."""
from repo import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from repo import main as _main
    raise SystemExit(_main(["clone", *sys.argv[1:]]))
