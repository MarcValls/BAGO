"""bago_core.cli — entrypoint for console_scripts.

Supports:
  bago --version          → version del bootstrapper
  bago install            → instala BAGO desde GitHub
  bago install --list     → lista releases
  bago install --version X → instala version especifica
  bago <cmd>              → delega al launcher (repo mode o active install)

Note: editable install (pip install -e) is recommended for development.
Ensure you installed with pip install -e if you intend to use the repo launcher.
"""
from __future__ import annotations

import sys
from pathlib import Path

from bago_core import __version__


def _active_install_path() -> Path | None:
    """Return path to active BAGO installation in ~/.bago/active/ if it exists."""
    marker = Path.home() / ".bago" / "active_version.txt"
    active = Path.home() / ".bago" / "active"
    if marker.exists() and active.exists() and (active / "bago").exists():
        return active
    return None




def _find_bago_launcher() -> Path | None:
    """Locate the 'bago' launcher script in repo or active install."""
    repo = Path(__file__).resolve().parents[1]
    cand = repo / "bago"
    if cand.exists():
        return cand
    active = _active_install_path()
    if active:
        return active / "bago"
    return None
def main() -> None:
    args = sys.argv[1:]

    # --version shortcut (no launcher needed)
    if args and args[0] in {"--version", "-V"}:
        print(f"bago {__version__}")
        return

    # install / upgrade / list → installer module (no .bago/ needed)
    if args and args[0] in {"install", "upgrade", "list"}:
        from bago_core import installer
        # Re-route: upgrade = install --upgrade
        if args[0] == "upgrade":
            sys.argv[1] = "install"
            sys.argv.insert(2, "--upgrade")
        if args[0] == "list":
            sys.argv[1] = "install"
            sys.argv.insert(2, "--list")
        sys.exit(installer.main())

    # If no active install and no local .bago/, show helpful message
    active = _active_install_path()
    has_local_bago = (Path.cwd() / ".bago" / "pack.json").exists()
    package_root = Path(__file__).resolve().parents[1]
    has_package_bago = (package_root / ".bago" / "pack.json").exists() or (package_root / ".bago" / "tools").exists()
    if not active and not has_local_bago and not has_package_bago:
        print(
            "BAGO no esta instalado en este directorio ni como paquete global.\n"
            "\n"
            "Opciones:\n"
            "  bago install              → instalar la ultima version desde GitHub\n"
            "  bago install --version X  → instalar version especifica\n"
            "  bago install --list       → ver releases disponibles\n"
            "  cd <repo-con-.bago>       → usar BAGO en modo repo\n"
        )
        sys.exit(1)

    # Delegate to launcher
    from bago_core import launcher
    launcher.main()


if __name__ == "__main__":
    main()
