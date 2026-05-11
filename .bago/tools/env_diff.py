#!/usr/bin/env python3
"""Compatibility shim for env diff."""
from env import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from env import main as _main
    raise SystemExit(_main(["diff", *sys.argv[1:]]))
