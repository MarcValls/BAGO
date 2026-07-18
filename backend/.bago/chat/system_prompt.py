#!/usr/bin/env python3
"""

_CREATED_VERSION = "4.0.0"  # Versión en que fue creado este archivo
system_prompt.py — BAGO 4.1.5 Neutral System Prompt

Prompt de sistema sin gates artificiales.
El modelo actúa con sus capacidades nativas.
Solo se define identidad, contexto de sesión y formato de respuesta.
"""

from __future__ import annotations

import json
from pathlib import Path


_MANIFEST_PATH = Path(__file__).resolve().parent / "system_prompt_manifest.json"


def _resolve_manifest_source(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (_MANIFEST_PATH.parent / path).resolve()


def _load_manifest() -> dict:
    raw = _MANIFEST_PATH.read_text(encoding="utf-8")
    manifest = json.loads(raw)
    if not isinstance(manifest, dict):
        raise ValueError("system_prompt manifest must be a JSON object")
    return manifest


def validate_system_prompt_contract(prompt: str, manifest: dict | None = None) -> None:
    manifest = manifest or _load_manifest()
    validation = manifest.get("validation") or {}
    required_phrases = list(validation.get("required_phrases") or [])
    missing = [phrase for phrase in required_phrases if phrase not in prompt]
    if missing:
        raise ValueError(f"system prompt missing required RC4 phrases: {missing}")

    if "state, evidence, change, validation, next step" not in prompt:
        raise ValueError("system prompt missing RC4 output order")


def get_system_prompt() -> str:
    manifest = _load_manifest()
    parts: list[str] = []
    for source in manifest.get("sources") or []:
        if not isinstance(source, dict):
            continue
        source_path = _resolve_manifest_source(str(source.get("path", "")))
        try:
            content = source_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n").strip()
        except OSError:
            continue
        if content:
            parts.append(content)

    if not parts:
        raise FileNotFoundError("No se pudo construir el system prompt de BAGO")

    prompt = "\n\n".join(parts)
    validate_system_prompt_contract(prompt, manifest)
    return prompt
