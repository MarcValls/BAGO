"""Contrato de salida limpia para la UI base de BAGO."""
from __future__ import annotations

from pathlib import Path


def test_ui_base_does_not_force_terminal_unconditionally():
    ui_base = Path(__file__).resolve().parents[1] / "bago" / "ui_base.py"
    text = ui_base.read_text(encoding="utf-8")

    assert "_enable_win_vt" in text
    assert "Console(force_terminal=sys.stdout.isatty() and _VT_OK" in text
    assert "force_terminal=True" not in text
