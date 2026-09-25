from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / ".bago" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))


def test_active_model_path_is_pure_and_writer_creates_parent_via_gateway(tmp_path, monkeypatch) -> None:
    providers = importlib.import_module("handlers_providers")
    state_paths = importlib.import_module("bago_core.user_state_paths")
    state_root = tmp_path / "user-state"
    monkeypatch.setattr(state_paths, "state_root", lambda: state_root)

    target = providers._active_models_path("ollama-local")
    assert target == state_root / "active_models" / "ollama-local.json"
    assert not target.parent.exists()

    providers._save_active_models("ollama-local", ["zeta", "alpha", "zeta"])

    assert json.loads(target.read_text(encoding="utf-8")) == ["alpha", "zeta"]


@pytest.mark.parametrize("provider_id", ["ollama_local", "ollama/local", "ollama-local/.."])
def test_active_model_paths_reject_noncanonical_provider_identity(provider_id: str) -> None:
    providers = importlib.import_module("handlers_providers")

    with pytest.raises(ValueError, match="not canonical"):
        providers._active_models_path(provider_id)
    with pytest.raises(ValueError, match="not canonical"):
        providers._active_models_read_paths(provider_id)
