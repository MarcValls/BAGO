"""bago_core.cli — entrypoint for console_scripts.

Imports the embedded launcher and delegates to its main().
Works in repo mode (editable) and package mode (wheel).
"""
from __future__ import annotations

import sys

from bago_core import __version__


def main() -> None:
    """Import bago_core.launcher and call its main()."""
    if len(sys.argv) > 1 and sys.argv[1] in {"--version", "-V"}:
        print(f"bago {__version__}")
        return

    from bago_core import launcher
    launcher.main()


if __name__ == "__main__":
    main()
