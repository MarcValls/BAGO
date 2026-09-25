from __future__ import annotations

import json

import pytest

from context_compressor import Layer, LayerStore, MessageNode


def test_layer_store_defers_creation_and_persists_through_state_writer(tmp_path):
    store = LayerStore(tmp_path)
    assert not (tmp_path / ".bago" / "state").exists()

    store.save_layers(
        [Layer(layer_id=1, user=MessageNode("user", "hello", 1))],
        "session-1",
    )

    path = tmp_path / ".bago" / "state" / "layers" / "session-1_layers.jsonl"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "layer_id": 1,
        "user": {"role": "user", "content": "hello", "layer_id": 1, "good": False, "metadata": {}},
        "assistant": None,
        "system": None,
        "summary": "",
        "compressed": False,
    }
    assert store.load_layers("session-1")[0].user.content == "hello"


def test_layer_store_rejects_path_like_session_identity_before_write(tmp_path):
    store = LayerStore(tmp_path)

    with pytest.raises(ValueError, match="session id"):
        store.save_layers([], "../outside")

    assert not (tmp_path / "outside_layers.jsonl").exists()
    assert not (tmp_path / ".bago" / "state").exists()
