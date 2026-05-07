"""bago_core.cli — entrypoint bridge for console_scripts.

Resolves the repo-root ``bago`` launcher and delegates to its main().
Works regardless of where pip installed the package.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path

from bago_core import __version__


def _find_bago_launcher() -> Path:
    """Locate the bago launcher script (repo root/bago)."""
    # When installed editable: this file is <repo>/bago_core/cli.py
    # When installed normally:  look for the launcher relative to the package
    here = Path(__file__).resolve().parent  # bago_core/
    candidates = [
        here.parent / "bago",           # editable install (repo root)
        here / ".." / "bago",           # another relative path
    ]
    for p in candidates:
        resolved = p.resolve()
        if resolved.exists():
            return resolved
    raise FileNotFoundError(
        "Cannot find 'bago' launcher. "
        "Ensure you installed with `pip install -e .` from the repo root."
    )


def main() -> None:
    """Load the bago launcher module and call its main()."""
    if len(sys.argv) > 1 and sys.argv[1] in {"--version", "-V"}:
        print(f"bago {__version__}")
        return

    launcher = _find_bago_launcher()
    spec = importlib.util.spec_from_file_location(
        "bago_launcher",
        launcher,
        submodule_search_locations=[],
    )
    if spec is None:
        # Fallback: force a SourceFileLoader for extensionless scripts
        loader = importlib.machinery.SourceFileLoader("bago_launcher", str(launcher))
        spec = importlib.util.spec_from_loader("bago_launcher", loader)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load bago launcher from {launcher}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    mod.main()


if __name__ == "__main__":
    main()
