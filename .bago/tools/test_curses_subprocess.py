#!/usr/bin/env python3
"""Test curses -> subprocess interactivity."""
import curses
import subprocess
import sys

def _loop(stdscr):
    stdscr.addstr(0, 0, "Press any key to run launcher.py next...")
    stdscr.refresh()
    stdscr.getch()

curses.wrapper(_loop)
print("\n  ▶ Ejecutando...\n")
subprocess.run([sys.executable, "C:\\bago_true\\bago_core\\launcher.py", "next"])
print("\n  Done.")
