"""Disponibilidad real de modelos por provider."""

from __future__ import annotations


_OLLAMA_MODEL_CACHE: list[str] | None = None


def rough_model_size_score(name: str) -> int:
    n = name.lower()
    if any(x in n for x in ("0.5b", "1b", "mini")):
        return 1
    if any(x in n for x in ("2b", "3b")):
        return 2
    if any(x in n for x in ("7b", "8b")):
        return 3
    if any(x in n for x in ("13b", "14b")):
        return 4
    if any(x in n for x in ("30b", "32b", "34b")):
        return 5
    if any(x in n for x in ("70b", "72b", "123b", "480b", "671b", "1t")):
        return 6
    return 3


def installed_ollama_models() -> list[str]:
    global _OLLAMA_MODEL_CACHE
    if _OLLAMA_MODEL_CACHE is not None:
        return _OLLAMA_MODEL_CACHE
    try:
        from .providers import ollama_probe

        probe = ollama_probe(timeout=0.8)
        _OLLAMA_MODEL_CACHE = list(probe.get("models", [])) if probe.get("running") else []
    except Exception:
        _OLLAMA_MODEL_CACHE = []
    return _OLLAMA_MODEL_CACHE


def available_model_items(prov_name: str, prov_data: dict) -> list[tuple[str, dict]]:
    models = list((prov_data or {}).get("models", {}).items())
    if prov_name != "ollama-local":
        return models

    installed = installed_ollama_models()
    if not installed:
        return []

    installed_set = set(installed)
    out = [
        (mn, md)
        for mn, md in models
        if md.get("wire_name", mn) in installed_set or mn in installed_set
    ]
    known_wires = {md.get("wire_name", mn) for mn, md in out}
    for raw in installed:
        if raw not in known_wires:
            out.append((raw, {"wire_name": raw, "best_for": "ollama_installed", "cost": "free"}))
    return out
