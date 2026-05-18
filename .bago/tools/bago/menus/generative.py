"""
menus/generative.py — Selector del modo generativo de BAGO.

Cinco modos que controlan qué providers/modelos puede usar el orquestador
en cada turno de la espiral:

  offline  — sin LLM calls (solo lógica local)
  eco      — modelos pequeños y rápidos (ollama-local, modelos eco)
  standard — comportamiento equilibrado (default)
  full     — modelos de máxima capacidad (cloud, grandes)
  auto     — BAGO elige en cada turno de la espiral el nivel adecuado
             según complejidad, contexto y providers disponibles
"""

from ..ui import _menu_pick, pi

# (key, description_corta, description_larga)
_GENERATIVE_MODES = [
    ("offline",  "Sin LLM  — solo lógica local, sin llamadas a modelos"),
    ("eco",      "Eco      — modelos pequeños y rápidos (ollama-local, eco)"),
    ("standard", "Standard — equilibrado, comportamiento por defecto"),
    ("full",     "Full     — máxima capacidad (cloud, modelos grandes)"),
    ("auto",     "Auto     — BAGO decide en cada turno: offline/eco/standard/full"),
]


def _cmd_generative(session):
    """Selector del modo generativo — offline · eco · standard · full · auto."""
    current = session.orch_mode

    entries = []
    for key, desc in _GENERATIVE_MODES:
        marker = "  [bold green]<<[/bold green]" if key == current else ""
        entries.append((key, f"{desc}{marker}"))

    sel = _menu_pick(
        "BAGO / Modo Generativo",
        f"Modo actual: [cyan]{current}[/cyan]   —   selecciona el nivel de generacion:",
        entries,
    )
    if sel is None:
        return

    session.orch_mode = sel
    labels = dict(_GENERATIVE_MODES)
    pi(f"Modo generativo: [bold cyan]{sel}[/bold cyan]  —  {labels[sel]}")
