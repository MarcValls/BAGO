#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim for repo context guard commands."""
from repo import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from repo import main as _main
    raise SystemExit(_main(["guard", *sys.argv[1:]]))
