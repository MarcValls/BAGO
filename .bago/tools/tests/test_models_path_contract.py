"""Contratos para la ruta externa de modelos Ollama."""

from __future__ import annotations

import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from bago.ollama_models import ensure_ollama_models_env, resolve_ollama_models_dir


def test_resolve_ollama_models_dir_prefers_external_env(tmp_path, monkeypatch):
    target = tmp_path / "external" / ".models"
    target.mkdir(parents=True)
    monkeypatch.setenv("OLLAMA_MODELS", str(target))

    resolved = resolve_ollama_models_dir(root_paths=[tmp_path / "unused"])

    assert resolved == target.resolve()


def test_resolve_ollama_models_dir_ignores_framework_env(tmp_path, monkeypatch):
    framework = tmp_path / "framework" / ".models"
    framework.mkdir(parents=True)
    framework_root = framework.parent

    external = tmp_path / "pendrive" / ".models"
    (external / "blobs").mkdir(parents=True)
    (external / "manifests").mkdir(parents=True)

    import bago.ollama_models as models_mod

    monkeypatch.setattr(models_mod, "BAGO_DIR", framework_root)
    monkeypatch.setattr(models_mod, "BAGO_REPO_ROOT", framework_root / "repo")
    monkeypatch.setenv("OLLAMA_MODELS", str(framework))

    resolved = resolve_ollama_models_dir(root_paths=[framework_root, external.parent])

    assert resolved == external.resolve()


def test_ensure_ollama_models_env_sets_variable(tmp_path, monkeypatch):
    external = tmp_path / "disk" / "models"
    (external / "blobs").mkdir(parents=True)
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)

    resolved = ensure_ollama_models_env(root_paths=[external.parent])

    assert resolved == external.resolve()
    assert os.environ["OLLAMA_MODELS"] == str(external.resolve())
