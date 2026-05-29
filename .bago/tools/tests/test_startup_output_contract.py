"""Contrato de salida limpia en el arranque de BAGO."""
from __future__ import annotations

from pathlib import Path


def test_splash_does_not_force_terminal_colors_unconditionally():
    splash = Path(__file__).resolve().parents[1] / "bago_splash.py"
    text = splash.read_text(encoding="utf-8")

    assert "Console(force_terminal=sys.stdout.isatty()" in text
    assert "force_terminal=True" not in text


def test_banner_keeps_plain_fallback_when_color_disabled():
    banner = Path(__file__).resolve().parents[1] / "bago_banner.py"
    text = banner.read_text(encoding="utf-8")

    assert "USE_COLOR" in text
    assert "if not USE_COLOR" in text

