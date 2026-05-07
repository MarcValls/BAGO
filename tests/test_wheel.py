"""test_wheel.py — Wheel packaging contract tests (v3.3 P1).

Tests what MUST work vs what is a known limitation.

EDITABLE INSTALL (pip install -e .):  ✅ SUPPORTED — gated by CI
WHEEL INSTALL    (pip install bago):  ⚠️ NOT YET SUPPORTED — documented limitation
                                         Tracked: issue #2 (v3.3 milestone)

Architecture note:
  bago_core.cli delegates to the repo-root ``bago`` launcher script.
  This works for editable installs where site-packages == repo root.
  A self-contained wheel requires bundling the launcher and tool modules
  inside the package — scoped for a future structural release (post-v3.3).

Run:
    pytest tests/test_wheel.py -v
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).resolve().parent.parent
PYPROJECT   = REPO_ROOT / "pyproject.toml"
BAGO_CORE   = REPO_ROOT / "bago_core"
BAGO_LAUNCHER = REPO_ROOT / "bago"


# ── T1: package structure ──────────────────────────────────────────────────────

def test_bago_core_package_exists():
    """bago_core/ must be a proper Python package with __init__.py."""
    assert (BAGO_CORE / "__init__.py").exists(), \
        "bago_core/__init__.py missing — package is not importable"


def test_bago_core_cli_exists():
    """bago_core/cli.py must exist and define main()."""
    cli = BAGO_CORE / "cli.py"
    assert cli.exists(), "bago_core/cli.py missing"
    source = cli.read_text(encoding="utf-8")
    assert "def main(" in source, "bago_core/cli.py must define main()"


def test_bago_core_importable():
    """bago_core must import without error."""
    mod = importlib.import_module("bago_core")
    assert mod is not None


def test_bago_core_version_defined():
    """bago_core.__version__ must be a non-empty string."""
    import bago_core
    assert hasattr(bago_core, "__version__"), "bago_core.__version__ not defined"
    assert isinstance(bago_core.__version__, str) and bago_core.__version__, \
        "bago_core.__version__ must be a non-empty string"


def test_version_matches_pyproject():
    """bago_core.__version__ must match the version in pyproject.toml."""
    import bago_core

    pyproject_text = PYPROJECT.read_text(encoding="utf-8")
    # Extract version = "X.Y.Z" from pyproject.toml (no extra dependency needed)
    for line in pyproject_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("version") and "=" in stripped and not stripped.startswith("#"):
            _, _, raw = stripped.partition("=")
            pyproject_version = raw.strip().strip('"').strip("'")
            break
    else:
        pytest.fail("Could not parse version from pyproject.toml")

    assert bago_core.__version__ == pyproject_version, (
        f"Version mismatch: bago_core.__version__={bago_core.__version__!r} "
        f"!= pyproject.toml version={pyproject_version!r}"
    )


# ── T2: entry-point bridge ─────────────────────────────────────────────────────

def test_launcher_script_exists():
    """The repo-root 'bago' launcher script must exist (editable install contract)."""
    assert BAGO_LAUNCHER.exists(), (
        "repo-root 'bago' launcher script missing — "
        "editable install (pip install -e .) requires this file"
    )


def test_launcher_is_python():
    """The bago launcher must be valid Python (compiles without error)."""
    import py_compile
    try:
        py_compile.compile(str(BAGO_LAUNCHER), doraise=True)
    except py_compile.PyCompileError as e:
        pytest.fail(f"bago launcher has syntax error: {e}")


def test_cli_find_launcher_succeeds_in_editable():
    """_find_bago_launcher() must succeed when running from the repo root (editable install)."""
    # This test proves the editable install path works.
    # It will PASS in CI (editable install) and in local dev.
    # It would FAIL in a wheel-only install — that is the known limitation.
    from bago_core.cli import _find_bago_launcher
    launcher = _find_bago_launcher()
    assert launcher.exists(), f"_find_bago_launcher() returned non-existent path: {launcher}"
    assert launcher.name == "bago", f"Expected 'bago' script, got: {launcher.name}"


def test_cli_main_is_callable():
    """bago_core.cli.main must be a callable."""
    from bago_core import cli
    assert callable(cli.main), "bago_core.cli.main is not callable"


@pytest.mark.parametrize("flag", ["--version", "-V"])
def test_cli_version_flag_does_not_require_launcher(flag, monkeypatch, capsys):
    """`bago --version` / `bago -V` must work even without repo-root launcher."""
    import bago_core
    import bago_core.cli as cli
    import importlib.util

    monkeypatch.setattr(sys, "argv", ["bago", flag])

    def _unexpected_launcher_lookup():
        raise AssertionError("_find_bago_launcher() should not be called for version flags")

    def _unexpected_spec_lookup(*_args, **_kwargs):
        raise AssertionError("spec_from_file_location() should not be called for version flags")

    monkeypatch.setattr(cli, "_find_bago_launcher", _unexpected_launcher_lookup)
    monkeypatch.setattr(importlib.util, "spec_from_file_location", _unexpected_spec_lookup)
    cli.main()

    assert capsys.readouterr().out.strip() == f"bago {bago_core.__version__}"


# ── T3: pyproject.toml contract ───────────────────────────────────────────────

def test_pyproject_has_console_scripts():
    """pyproject.toml must declare bago = bago_core.cli:main entry point."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'bago = "bago_core.cli:main"' in text or \
           "bago = 'bago_core.cli:main'" in text, \
        "pyproject.toml must declare: bago = \"bago_core.cli:main\" under [project.scripts]"


def test_pyproject_requires_python():
    """pyproject.toml must declare requires-python."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "requires-python" in text, \
        "pyproject.toml must declare requires-python"


def test_pyproject_has_build_system():
    """pyproject.toml must declare a [build-system] table."""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "[build-system]" in text, \
        "pyproject.toml must have a [build-system] table"


# ── T4: known limitation documented ──────────────────────────────────────────

def test_known_limitation_wheel_only_install_documented():
    """
    KNOWN LIMITATION: non-editable wheel install is not yet supported.

    This test documents the limitation — it does NOT attempt to test a
    non-editable install (that would require a subprocess + clean venv).

    The architectural reason: bago_core.cli resolves the launcher as
    here.parent / 'bago', which works for editable installs (where
    here.parent == repo root) but fails for wheel installs (where
    here.parent == site-packages).

    Fix scoped for post-v3.3: bundle launcher + tools inside bago_core,
    use importlib.resources for tool resolution.
    """
    from bago_core.cli import _find_bago_launcher
    import bago_core.cli as cli_mod
    source = Path(cli_mod.__file__).read_text(encoding="utf-8")
    assert "Ensure you installed with" in source or \
           "pip install -e" in source or \
           "editable" in source.lower(), (
        "bago_core/cli.py must document the editable-only limitation "
        "so future developers understand the constraint."
    )
