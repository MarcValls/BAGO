"""Disponibilidad real de modelos por provider."""

from __future__ import annotations

from .codex_auth import resolve_openai_credentials


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


def _model_service_name(prov_name: str, *, route: str = "", auth_mode: str = "") -> str:
    prov = (prov_name or "").strip().lower()
    if prov == "ollama-local":
        return "ollama-native"
    if prov == "ollama-cloud":
        return "ollama-cloud-api"
    if prov == "copilot":
        return "github-copilot-api"
    if prov == "github-models":
        return "github-models-api"
    if prov in ("codex", "openai"):
        if route == "openai-api" or auth_mode == "api_key":
            return "openai-api"
        return "codex-cli"
    if prov:
        return f"{prov}-api"
    return "unknown"


def available_model_routes(prov_name: str, prov_data: dict) -> list[dict]:
    """Return rich route records for the models exposed by a provider."""
    models = list((prov_data or {}).get("models", {}).items())
    if not models:
        return []

    prov = (prov_name or "").strip().lower()
    records: list[dict] = []

    if prov == "ollama-local":
        installed = set(installed_ollama_models())
        if not installed:
            return []
        for mn, md in models:
            wire = md.get("wire_name", mn)
            if wire in installed or mn in installed:
                records.append({
                    "provider": prov_name,
                    "model": mn,
                    "wire_name": wire,
                    "service": "ollama-native",
                    "route": "ollama-native",
                    "backend": "ollama",
                    "available": True,
                    "best_for": md.get("best_for", ""),
                    "cost": md.get("cost", ""),
                })
        known_wires = {rec["wire_name"] for rec in records}
        for raw in installed:
            if raw not in known_wires:
                records.append({
                    "provider": prov_name,
                    "model": raw,
                    "wire_name": raw,
                    "service": "ollama-native",
                    "route": "ollama-native",
                    "backend": "ollama",
                    "available": True,
                    "best_for": "ollama_installed",
                    "cost": "free",
                })
        return records

    if prov in ("codex", "openai"):
        creds = resolve_openai_credentials()
        if not creds.get("oauth_token"):
            return []
        try:
            from .providers import resolve_codex_route_candidates
        except Exception:
            return []

        for mn, md in models:
            wire = md.get("wire_name", mn)
            for candidate in resolve_codex_route_candidates(wire):
                records.append({
                    "provider": prov_name,
                    "model": mn,
                    "wire_name": wire,
                    "service": candidate.get("service", ""),
                    "route": candidate.get("route", ""),
                    "backend": candidate.get("backend", "litellm"),
                    "available": True,
                    "auth_mode": candidate.get("auth_mode", ""),
                    "fallback": candidate.get("fallback", False),
                    "best_for": md.get("best_for", ""),
                    "cost": md.get("cost", ""),
                })
        return records

    for mn, md in models:
        wire = md.get("wire_name", mn)
        records.append({
            "provider": prov_name,
            "model": mn,
            "wire_name": wire,
            "service": _model_service_name(prov_name),
            "route": _model_service_name(prov_name),
            "backend": "litellm",
            "available": True,
            "best_for": md.get("best_for", ""),
            "cost": md.get("cost", ""),
        })
    return records


def available_model_items(prov_name: str, prov_data: dict) -> list[tuple[str, dict]]:
    records = available_model_routes(prov_name, prov_data)
    if not records:
        return []
    chosen: dict[str, dict] = {}
    for rec in records:
        mn = rec["model"]
        current = chosen.get(mn)
        if current is None:
            chosen[mn] = dict(rec)
            continue
        if current.get("route") == "openai-api" and rec.get("route") == "codex-cli":
            chosen[mn] = dict(rec)
    return [(mn, md) for mn, md in chosen.items()]
