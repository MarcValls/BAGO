#!/usr/bin/env python3
"""ollama_discovery.py - helpers para descubrir modelos Ollama.

La fuente primaria sigue siendo la API local de Ollama. Si el daemon no
responde, el helper cae a una inspeccion del filesystem para reconocer los
modelos ya instalados en disco.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def _candidate_model_roots() -> list[Path]:
    roots: list[Path] = []
    env_root = os.environ.get("OLLAMA_MODELS", "").strip()
    if env_root:
        roots.append(Path(env_root).expanduser())

    home = Path.home()
    roots.extend(
        [
            home / ".ollama" / "models",
            home / ".ollama",
            home / ".bago" / ".models",
            home / ".bago",
        ]
    )

    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _path_to_model_name(manifest_root: Path, manifest_file: Path) -> str | None:
    try:
        rel = manifest_file.relative_to(manifest_root)
    except ValueError:
        return None

    parts = rel.parts
    if "manifests" in parts:
        tail = parts[parts.index("manifests") + 1 :]
    else:
        tail = parts
    if len(tail) < 2:
        return None

    family = tail[-2].strip()
    tag = tail[-1].strip()
    if tag.endswith(".json"):
        tag = tag[:-5].strip()
    if not family or not tag:
        return None
    return f"{family}:{tag}"


def _discover_models_from_disk() -> list[str]:
    names: list[str] = []
    for root in _candidate_model_roots():
        if not root.exists():
            continue
        manifest_roots = []
        direct = root / "manifests"
        nested = root / "models" / "manifests"
        if direct.exists():
            manifest_roots.append(direct)
        if nested.exists() and nested != direct:
            manifest_roots.append(nested)

        for manifest_root in manifest_roots:
            for manifest_file in manifest_root.rglob("*"):
                if not manifest_file.is_file():
                    continue
                model_name = _path_to_model_name(manifest_root, manifest_file)
                if model_name:
                    names.append(model_name)

    return list(dict.fromkeys(names))


def _discover_models_from_api(base_url: str) -> list[str]:
    try:
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return []

    names: list[str] = []
    for model in data.get("models", []):
        name = model.get("name") or model.get("model") or ""
        if name:
            names.append(str(name))
    return names


def discover_ollama_model_names(
    base_url: str | None = None,
    extra_roots: list[str] | None = None,
) -> list[str]:
    """Devuelve modelos Ollama detectados por API local o por disco.

    Args:
        base_url:    URL base de Ollama (ej. http://127.0.0.1:11434).
        extra_roots: Rutas adicionales al directorio de modelos, tomadas
                     de la configuración del usuario (config ollama.models_path).
                     Se insertan antes de los candidatos por defecto para que
                     tengan prioridad.
    """
    names: list[str] = []
    if base_url:
        names.extend(_discover_models_from_api(base_url))

    # Inject extra roots before defaults so user-configured paths take priority
    if extra_roots:
        saved_env = os.environ.get("OLLAMA_MODELS", "")
        # Temporarily prepend them via the env var logic by walking them directly
        for raw_root in extra_roots:
            root = Path(raw_root).expanduser()
            if not root.exists():
                continue
            for sub in (root / "manifests", root / "models" / "manifests"):
                if not sub.exists():
                    continue
                for manifest_file in sub.rglob("*"):
                    if not manifest_file.is_file():
                        continue
                    name = _path_to_model_name(sub, manifest_file)
                    if name:
                        names.append(name)

    names.extend(_discover_models_from_disk())
    return list(dict.fromkeys(name for name in names if name))
