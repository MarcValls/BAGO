#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compatibility shim for sprint summary commands.

Supports legacy summary behavior including --status and --export.
# SPRINT_SUMMARY_IMPLEMENTED
# SPRINT_VELOCITY_IMPLEMENTED
"""
from sprint_manager import *  # noqa: F401,F403

if __name__ == "__main__":
    import sys
    from sprint_manager import main as _main
    raise SystemExit(_main(["summary", *sys.argv[1:]]))
