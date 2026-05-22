#!/usr/bin/env python3
"""Compatibility shim for env diagnostics."""
from env import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from env import main as _main
    raise SystemExit(_main(["check", *sys.argv[1:]]))
