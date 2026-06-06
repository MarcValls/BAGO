#!/usr/bin/env python3
"""bago_core/cli_installs.py -- facade for the install scanner.

This file is a re-export facade (FASE 6.4 split). The actual logic now lives
in three sibling modules:

  - :mod:`bago_core.cli_installs_facts`     -- filesystem facts (pid alive,
    sig short, version, tag, supervisor state)
  - :mod:`bago_core.cli_installs_discovery` -- classify & scan known
    locations + user-selected roles
  - :mod:`bago_core.cli_installs_summary`   -- aggregate counters
  - :mod:`bago_core.cli_installs_cli`       -- argparse + main

`python -m bago_core.cli_installs` continues to work and produces the same
JSON output. The launcher (`bago list-installs`) imports `main` from this
facade.
"""
from __future__ import annotations

from bago_core.cli_installs_cli import main
from bago_core.cli_installs_discovery import (
    EXTRA_HINTS,
    KNOWN_LOCATIONS,
    _classify,
    _expand,
    _scan,
)
from bago_core.cli_installs_facts import (
    pid_alive,
    read_tag,
    read_version,
    short_sig,
    supervisor_state,
)
from bago_core.cli_installs_summary import summary

__all__ = [
    "EXTRA_HINTS",
    "KNOWN_LOCATIONS",
    "_classify",
    "_expand",
    "_scan",
    "main",
    "pid_alive",
    "read_tag",
    "read_version",
    "short_sig",
    "summary",
    "supervisor_state",
]


if __name__ == "__main__":
    raise SystemExit(main())
