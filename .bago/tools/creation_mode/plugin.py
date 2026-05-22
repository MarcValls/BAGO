"""creation_mode.plugin — Interfaz para integración con BAGO.

Expone entrypoints que BAGO puede llamar sin saber nada de argparse.
"""
from __future__ import annotations

from .engine import render_once, run_interactive


def bago_entrypoint(**kwargs) -> int:
    """Entrypoint genérico para BAGO launcher."""
    tab = kwargs.get("tab", "cambios")
    layer = kwargs.get("layer", "")
    sublayer = kwargs.get("sublayer", "")
    once = kwargs.get("once", False)
    if once:
        render_once(tab, layer, sublayer)
        return 0
    return run_interactive(tab, layer, sublayer)


def bago_create_once(tab: str = "cambios", layer: str = "", sublayer: str = "") -> None:
    """Render único para plugins que solo necesitan pintar."""
    render_once(tab, layer, sublayer)
